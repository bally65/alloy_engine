"""
最低成本材料分析（文獻數據驅動，無儀器）。

用 literature_mce 的文獻 ΔS_M 與元素價格代理，算各磁熱材料的「效能/成本」，
找出以最低成本組合出所需效能的材料，並對標裝置需求。

執行：python scripts/lowest_cost_material.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from alloy_engine.thermomagnetic import literature_mce as lm


def main() -> None:
    print("═" * 74)
    print(" 最低成本磁熱材料分析（文獻 ΔS_M + 元素價格代理）")
    print("═" * 74)
    print(f"{'材料':<16}{'Tc(K)':>7}{'ΔS@2T':>8}{'階':>5}{'磁滯':>14}"
          f"{'成本$/kg':>11}{'ΔS/成本':>9}")
    print("-" * 74)
    for name, ds, cost, fom in lm.rank_by_value_per_cost():
        m = lm.get(name)
        print(f"{name:<16}{m.Tc_K:>7.0f}{ds:>8.1f}{m.order:>5}{m.hysteresis:>14}"
              f"{cost:>11.1f}{fom:>9.1f}")
    print("-" * 74)

    ranked = lm.rank_by_value_per_cost()
    best = ranked[0]
    ref_free = [r for r in ranked if lm.get(r[0]).rare_earth_free]
    print(f" 最佳效能/成本：{best[0]}（ΔS/成本 {best[3]:.1f}，${best[2]:.1f}/kg）")
    if ref_free:
        rf = ref_free[0]
        print(f" 最低供應鏈風險（無稀土）：{rf[0]}（ΔS/成本 {rf[3]:.1f}，${rf[2]:.1f}/kg）")
    print()
    print(" 建議（最低成本可行方案）：")
    print("  • 主力：La(Fe,Si)13H — ΔS/成本最高、Tc 可氫化調至廢熱/室溫帶。")
    print("  • 備援：(Mn,Fe)2(P,Si) — 完全無稀土、成本最穩、巨磁熱；磁滯可摻雜調低。")
    print("  • 避免：Gd5Si2Ge2 — Ge 使成本 ~$224/kg（×150 於上述），僅作學術對照。")
    print("  • Gd 僅作量測校準基準（二階、無磁滯、文獻最完整），非量產材料。")
    print("═" * 74)
    print(" 註：成本為元素價格代理的相對量級（非報價）；ΔS_M 為文獻代表值（成分/場強相依）。")


if __name__ == "__main__":
    main()
