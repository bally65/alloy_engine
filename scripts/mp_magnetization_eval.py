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

MP_API = "https://api.materialsproject.org/materials/summary/"
MU_B_VOL_TO_TESLA = 11.654   # T per (μB/Å³)：μ₀·μ_B / Å³

# 對標集：(名稱, MP 化學式, 原子分率組成)
BENCHMARKS = {
    "Fe":      ("Fe",     {"Fe": 1.0}),
    "Co":      ("Co",     {"Co": 1.0}),
    "Ni":      ("Ni",     {"Ni": 1.0}),
    "Gd":      ("Gd",     {"Gd": 1.0}),
    "FeCo":    ("FeCo",   {"Fe": 0.5, "Co": 0.5}),
    "Fe3Si":   ("Fe3Si",  {"Fe": 0.75, "Si": 0.25}),
    "Ni3Fe":   ("Ni3Fe",  {"Ni": 0.75, "Fe": 0.25}),
    "Co3Fe":   ("Co3Fe",  {"Co": 0.75, "Fe": 0.25}),
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

    print("═" * 64)
    print(" D3 — 合成 Br vs Materials Project 真實 DFT 磁化")
    print("═" * 64)
    print(f"{'材料':<10}{'MP Br(T)':>12}{'代理 Br(T)':>14}{'誤差(T)':>12}")
    print("-" * 64)

    mp_list, pred_list = [], []
    for name, (formula, frac) in BENCHMARKS.items():
        try:
            br_mp = mp_br_tesla(formula, key)
        except Exception as e:
            print(f"{name:<10}  MP 查詢失敗：{str(e)[:40]}")
            continue
        if br_mp is None:
            print(f"{name:<10}{'(無磁性資料)':>26}")
            continue
        br_pred = float(bundle.predict_properties(comp_vector(frac))["Br"])
        mp_list.append(br_mp); pred_list.append(br_pred)
        print(f"{name:<10}{br_mp:>12.2f}{br_pred:>14.2f}{br_pred - br_mp:>+12.2f}")

    print("-" * 64)
    if len(mp_list) >= 2:
        mp_a, pr_a = np.array(mp_list), np.array(pred_list)
        mae = np.mean(np.abs(pr_a - mp_a))
        bias = np.mean(pr_a - mp_a)
        ss_res = np.sum((pr_a - mp_a) ** 2)
        ss_tot = np.sum((mp_a - mp_a.mean()) ** 2) + 1e-9
        r2 = 1 - ss_res / ss_tot
        print(f" n={len(mp_list)}  MAE={mae:.2f} T  bias={bias:+.2f} T  R²={r2:.3f}")
        print(" 註：MP 為 0K DFT 飽和極化；代理 Br 含室溫/合成校準，"
              "故系統性偏差屬預期，重點看排序與量級。")
    print("═" * 64)


if __name__ == "__main__":
    main()
