"""
D3：用 Materials Project 真實 DFT 磁化，評估本引擎合成 Br 的可信度。

Br 是 delta_M（整機磁功）的來源，故其可信度直接決定功率密度預測。本腳本對
一組已知鐵磁體查 MP 的體積歸一磁化（μB/Å³），換算成飽和極化 Br (T)，與
surrogate 預測的 Br 對標——即 Tc 對標（nemad_eval）的「磁化版」。

技術：raw HTTPS（免裝 mp-api / pymatgen）。
金鑰：由 external/.mp_key 或環境變數 MP_API_KEY 取得（git-ignored，不 commit）。
單位：Br [T] = 11.654 × M_vol [μB/Å³]（μ₀·μB/Å³ → Tesla）。

執行：python scripts/mp_magnetization_eval.py
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alloy_engine.config import CHECKPOINT_DIR, DEFAULT_DEVICE
from alloy_engine.data.elements import ELEMENTS, NUM_ELEMENTS
from alloy_engine.models.surrogate import SurrogateBundle
from alloy_engine.thermomagnetic.magnetization_correction import saturation_to_working

MP_API = "https://api.materialsproject.org/materials/summary/"
MU_B_VOL_TO_TESLA = 11.654   # T per (μB/Å³)：μ₀·μ_B / Å³
T_WORK_K = 300.0             # 對標的工作溫度（室溫）

# 對標集：(名稱, MP 化學式, 原子分率組成, 文獻 Tc[K])
# Tc 來源：標準鐵磁體文獻值，用於把 MP 的 0K 飽和值修正到工作溫度（D3）。
BENCHMARKS = {
    "Fe":      ("Fe",     {"Fe": 1.0},                1043.0),
    "Co":      ("Co",     {"Co": 1.0},                1388.0),
    "Ni":      ("Ni",     {"Ni": 1.0},                 627.0),
    "Gd":      ("Gd",     {"Gd": 1.0},                 293.0),
    "FeCo":    ("FeCo",   {"Fe": 0.5, "Co": 0.5},     1250.0),
    "Fe3Si":   ("Fe3Si",  {"Fe": 0.75, "Si": 0.25},    840.0),
    "Ni3Fe":   ("Ni3Fe",  {"Ni": 0.75, "Fe": 0.25},    870.0),
    "Co3Fe":   ("Co3Fe",  {"Co": 0.75, "Fe": 0.25},   1200.0),
}


def get_key() -> str:
    k = os.environ.get("MP_API_KEY")
    if not k:
        p = Path(__file__).resolve().parent.parent / "external" / ".mp_key"
        if p.exists():
            k = p.read_text().strip()
    if not k:
        raise RuntimeError(
            "找不到 MP API key：設環境變數 MP_API_KEY 或放 external/.mp_key（git-ignored）"
        )
    return k


def mp_br_tesla(formula: str, key: str) -> float | None:
    """查 MP，回傳該化學式 FM 基態（最高體積磁化）對應的 Br (T)；查無回 None。"""
    url = MP_API + "?" + urllib.parse.urlencode({
        "formula": formula,
        "_fields": "material_id,formula_pretty,total_magnetization_normalized_vol,"
                   "ordering,energy_above_hull",
        "_limit": 50,
    })
    req = urllib.request.Request(url, headers={"X-API-KEY": key, "User-Agent": "curl/8"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read()).get("data", [])
    vols = [d.get("total_magnetization_normalized_vol") or 0.0 for d in data]
    if not vols or max(vols) <= 0:
        return None
    return MU_B_VOL_TO_TESLA * max(vols)   # 取最高磁化的多形體（FM 基態代理）


def comp_vector(frac: dict[str, float]) -> torch.Tensor:
    v = torch.zeros(1, NUM_ELEMENTS)
    for el, x in frac.items():
        v[0, ELEMENTS.index(el)] = x
    return v


def main() -> None:
    key = get_key()
    bundle = SurrogateBundle.load(CHECKPOINT_DIR / "bundle.pt", device=DEFAULT_DEVICE)

    print("═" * 78)
    print(" D3 — 合成 Br vs Materials Project 真實 DFT 磁化（含溫度修正）")
    print("═" * 78)
    print(f" 工作溫度 T = {T_WORK_K:.0f}K；MP 為 0K 飽和 → 以平均場 m(T/Tc) 修正到工作溫度")
    print("-" * 78)
    print(f"{'材料':<8}{'Tc(K)':>7}{'MP 0K(T)':>11}{'MP@300K':>11}"
          f"{'代理 Br':>10}{'raw誤差':>10}{'修正誤差':>10}")
    print("-" * 78)

    mp_raw, mp_corr, pred_list = [], [], []
    for name, (formula, frac, tc) in BENCHMARKS.items():
        try:
            br_mp = mp_br_tesla(formula, key)
        except Exception as e:
            print(f"{name:<8}  MP 查詢失敗：{str(e)[:40]}")
            continue
        if br_mp is None:
            print(f"{name:<8}{'(無磁性資料)':>30}")
            continue
        br_mp_T = saturation_to_working(br_mp, T_WORK_K, tc)  # 0K → 工作溫度
        br_pred = float(bundle.predict_properties(comp_vector(frac))["Br"])
        mp_raw.append(br_mp); mp_corr.append(br_mp_T); pred_list.append(br_pred)
        print(f"{name:<8}{tc:>7.0f}{br_mp:>11.2f}{br_mp_T:>11.2f}"
              f"{br_pred:>10.2f}{br_pred - br_mp:>+10.2f}{br_pred - br_mp_T:>+10.2f}")

    print("-" * 78)

    def _stats(ref):
        ref_a, pr_a = np.array(ref), np.array(pred_list)
        mae = np.mean(np.abs(pr_a - ref_a))
        bias = np.mean(pr_a - ref_a)
        ss_res = np.sum((pr_a - ref_a) ** 2)
        ss_tot = np.sum((ref_a - ref_a.mean()) ** 2) + 1e-9
        return mae, bias, 1 - ss_res / ss_tot

    if len(pred_list) >= 2:
        mae0, bias0, r20 = _stats(mp_raw)
        mae1, bias1, r21 = _stats(mp_corr)
        print(f" 對 MP 0K（raw）      ：n={len(pred_list)}  MAE={mae0:.2f}T  "
              f"bias={bias0:+.2f}T  R²={r20:.3f}")
        print(f" 對 MP@{T_WORK_K:.0f}K（溫度修正）：n={len(pred_list)}  MAE={mae1:.2f}T  "
              f"bias={bias1:+.2f}T  R²={r21:.3f}")
        print(" 註：修正把 MP 的 0K 飽和降到工作溫度，與合成 Br 同溫可比；")
        print("     若修正後 bias 顯著縮小，表示原 -0.50T 偏差多源於 0K-vs-室溫，而非模型系統性低估。")
    print("═" * 78)


if __name__ == "__main__":
    main()
