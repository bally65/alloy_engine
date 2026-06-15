"""
建立真實 Br 訓練資料集：從 Materials Project 抓本元素空間的鐵磁(FM)化合物 DFT 磁化。
================================================================================

Br 此前為合成（對真實 MP 磁化 R²≈0，無預測力）。本腳本抓真實資料以訓練可預測的
Br baseline（見 train_br_mp_baseline.py），是 Tc(NEMAD) 故事的「磁化版」。

按 chemsys 查詢本 14 元素空間內的金屬間化合物（避免被氧化物等淹沒），保留
ordering=FM 且體積磁化>0 者，取最穩定多形體。輸出 external/mp_fm_dataset.json
（git-ignored）。需 MP API key（external/.mp_key 或 MP_API_KEY）。

執行：python scripts/build_mp_magnetization_dataset.py
"""
from __future__ import annotations

import itertools
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from alloy_engine.data.elements import ELEMENTS

API = "https://api.materialsproject.org/materials/summary/"
OUT = Path("external/mp_fm_dataset.json")
MAG_DRIVERS = {"Fe", "Co", "Ni", "Mn", "Gd"}   # 磁性主族（系統至少含其一才可能 FM）


def get_key() -> str:
    k = os.environ.get("MP_API_KEY")
    if not k:
        p = Path("external/.mp_key")
        if p.exists():
            k = p.read_text().strip()
    if not k:
        raise RuntimeError("找不到 MP API key（external/.mp_key 或 MP_API_KEY）")
    return k


def _query(params: dict, key: str) -> list:
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"X-API-KEY": key, "User-Agent": "curl/8"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read()).get("data", [])


def build() -> list:
    key = get_key()
    ours = set(ELEMENTS)
    # 所有含 ≥1 磁性主族的 2-/3-元素系統（放寬後 ~335 系統；FiM 因磁矩抵消難預測而排除，
    # 只保留 FM——實測 FM-only 擴張 R² 0.56→0.60、MAE 0.33→0.26T）。
    systems = set()
    for k in (2, 3):
        for combo in itertools.combinations(ELEMENTS, k):
            if set(combo) & MAG_DRIVERS:
                systems.add("-".join(sorted(combo)))

    rows: dict[str, list] = {}
    fields = ("material_id,formula_pretty,elements,"
              "total_magnetization_normalized_vol,ordering,energy_above_hull")
    for s in sorted(systems):
        try:
            data = _query({"chemsys": s, "_fields": fields, "_limit": 200}, key)
        except Exception:
            continue
        for x in data:
            mag = x.get("total_magnetization_normalized_vol") or 0.0
            if mag > 0 and x.get("ordering") == "FM" and set(x["elements"]) <= ours:
                f = x["formula_pretty"]
                eah = x.get("energy_above_hull") or 9.0
                if f not in rows or eah < rows[f][2]:
                    rows[f] = (f, round(mag, 5), round(eah, 3))
    out = list(rows.values())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out))
    print(f"已抓 {len(out)} 個 FM 化合物（本元素空間內）→ {OUT}")
    return out


if __name__ == "__main__":
    build()
