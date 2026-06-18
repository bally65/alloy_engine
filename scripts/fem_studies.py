"""FEM 研究：(1) per-scenario（25/150/350/500°C）磁路場；(2) 磁體幾何（長度/氣隙）掃描
→ 漏磁/B_gap → 優化磁體形狀（知反點）。重用 fem_magnetics.solve_field。

輸出 docs/fem_optimization.png + docs/fem_studies.json。
用法：python scripts/fem_studies.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as _fm
for _fn in ["PingFang TC", "Heiti TC", "Arial Unicode MS", "STHeiti"]:
    if any(_fn in f.name for f in _fm.fontManager.ttflist):
        plt.rcParams["font.sans-serif"] = [_fn]; break
plt.rcParams["axes.unicode_minus"] = False

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from alloy_engine.thermomagnetic.magnetic_circuit import GRADES, br_at, pick_grade
from scripts.fem_magnetics import solve_field

SCEN = [25, 150, 350, 500]


def per_scenario() -> list[dict]:
    rows = []
    for tc in SCEN:
        t_mag = min(tc - 30, 300.0)               # 磁體置冷側 + 熱隔離 ≤300°C
        gk = pick_grade(t_mag)
        br = br_at(GRADES[gk], t_mag)
        r = solve_field(br, gap_mm=4.0, magnet_len_mm=12.0, nonlinear=True)
        rows.append(dict(scenario_C=tc, magnet_T=round(t_mag), grade=GRADES[gk].name,
                         Br_T=round(br, 3), B_gap_T=r["B_gap_T"], leakage=r["leakage"], n_iter=r["n_iter"]))
    return rows


def geometry_sweep() -> dict:
    Lm = [6, 9, 12, 16, 20, 26, 32]
    gaps = [2, 3, 4, 6, 8]
    br = br_at(GRADES["SmCo-2:17"], 300.0)        # 350°C 代表
    by_len = [solve_field(br, gap_mm=4.0, magnet_len_mm=L) for L in Lm]
    by_gap = [solve_field(br, gap_mm=g, magnet_len_mm=12.0) for g in gaps]
    # 磁體形狀優化：B_gap 對磁長的知反點（邊際增益 <10% 視為飽和）
    Bg = [r["B_gap_T"] for r in by_len]
    knee_i = len(Lm) - 1
    for i in range(1, len(Lm)):
        if (Bg[i] - Bg[i-1]) / max(Bg[i-1], 1e-9) < 0.06:
            knee_i = i; break
    return dict(Lm=Lm, by_len=by_len, gaps=gaps, by_gap=by_gap, knee_len=Lm[knee_i],
                knee_Bgap=Bg[knee_i], br=br)


def main() -> None:
    scen = per_scenario()
    sw = geometry_sweep()

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 5))
    Bl = [r["B_gap_T"] for r in sw["by_len"]]; Ll = [r["leakage"] for r in sw["by_len"]]
    a1.plot(sw["Lm"], Bl, "o-", color="#1f77b4", label="B_gap (T)")
    a1.axvline(sw["knee_len"], ls="--", color="crimson", alpha=0.7, label=f"knee Lm={sw['knee_len']}mm")
    a1b = a1.twinx(); a1b.plot(sw["Lm"], Ll, "s--", color="#2a9d8f", alpha=0.7)
    a1b.set_ylabel("leakage factor", color="#2a9d8f")
    a1.set_xlabel("magnet length Lm (mm)"); a1.set_ylabel("B_gap (T)", color="#1f77b4")
    a1.set_title("磁體長度掃描（gap=4mm）：B_gap 知反點 + 漏磁"); a1.legend(loc="lower right"); a1.grid(alpha=0.3)

    Bg2 = [r["B_gap_T"] for r in sw["by_gap"]]; Lg2 = [r["leakage"] for r in sw["by_gap"]]
    a2.plot(sw["gaps"], Bg2, "o-", color="#9467bd", label="B_gap (T)")
    a2b = a2.twinx(); a2b.plot(sw["gaps"], Lg2, "s--", color="#e76f51", alpha=0.7)
    a2b.set_ylabel("leakage factor", color="#e76f51")
    a2.set_xlabel("air gap (mm)"); a2.set_ylabel("B_gap (T)", color="#9467bd")
    a2.set_title("氣隙掃描（Lm=12mm）：越小越強、漏磁越低"); a2.legend(loc="upper right"); a2.grid(alpha=0.3)
    fig.suptitle("FEM 磁體幾何優化（scikit-fem, SmCo@300°C）", fontsize=12, weight="bold")
    plt.tight_layout(); plt.savefig("docs/fem_optimization.png", dpi=150, bbox_inches="tight")

    strip = lambda r: {k: v for k, v in r.items() if not k.startswith("_")}
    out = dict(per_scenario=scen,
               sweep_len=[dict(Lm=L, **strip(r)) for L, r in zip(sw["Lm"], sw["by_len"])],
               sweep_gap=[dict(gap=g, **strip(r)) for g, r in zip(sw["gaps"], sw["by_gap"])],
               recommended=dict(knee_magnet_len_mm=sw["knee_len"], knee_B_gap_T=round(sw["knee_Bgap"], 3),
                                note="磁長超過知反點後 B_gap 增益<6%/步 → 多加磁體不划算；氣隙取機械可行最小"))
    Path("docs/fem_studies.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))

    print("per-scenario FEM (nonlinear):")
    print(f"  {'情境°C':<8}{'磁體溫':<7}{'grade':<16}{'Br(T)':>7}{'B_gap':>8}{'leak':>7}")
    for r in scen:
        print(f"  {r['scenario_C']:<8}{r['magnet_T']:<7}{r['grade']:<16}{r['Br_T']:>7}{r['B_gap_T']:>8}{r['leakage']:>7}")
    print(f"\n磁體形狀優化：B_gap 知反點 Lm={sw['knee_len']}mm（B_gap={sw['knee_Bgap']:.3f}T）")
    print(f"  → 超過此磁長增益<6%/步；氣隙越小越好（見 docs/fem_optimization.png）")


if __name__ == "__main__":
    main()
