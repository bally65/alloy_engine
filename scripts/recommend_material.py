"""
端到端材料推薦 capstone：給工作溫度/場強，輸出最佳磁熱材料 + 校準物理 + 成本。
整合 literature_mce（文獻/成本/w）→ 一個可執行決策。

執行：
  python scripts/recommend_material.py                       # 預設 80°C 廢熱、2T
  python scripts/recommend_material.py --temp 150 --field 1.5 --rare-earth-free
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from alloy_engine.thermomagnetic.recommend import recommend_material


def main() -> None:
    ap = argparse.ArgumentParser(description="端到端磁熱材料推薦")
    ap.add_argument("--temp", type=float, default=80.0, help="工作溫度 °C（預設 80）")
    ap.add_argument("--field", type=float, default=2.0, help="可用磁場 T（預設 2）")
    ap.add_argument("--rare-earth-free", action="store_true", help="偏好無稀土材料")
    args = ap.parse_args()

    recs = recommend_material(args.temp, field_T=args.field,
                              prefer_rare_earth_free=args.rare_earth_free)
    print("═" * 78)
    print(f" 材料推薦：工作溫度 {args.temp:g}°C  ·  場強 {args.field:g}T"
          f"{'  ·  偏好無稀土' if args.rare_earth_free else ''}")
    print("═" * 78)
    print(f"{'排名':<4}{'材料':<16}{'分數':>7}{'Tc對齊':>8}{'ΔS@場':>8}"
          f"{'w(K)':>7}{'成本$/kg':>10}")
    print("-" * 78)
    for i, r in enumerate(recs, 1):
        print(f"{i:<4}{r.name:<16}{r.score:>7.2f}{r.tc_match:>8.2f}"
              f"{r.dS_at_field:>8.1f}{r.w_K:>7.1f}{r.cost_usd_kg:>10.1f}")
    print("-" * 78)
    best = recs[0]
    print(f" 推薦：{best.name}")
    print(f"   理由：{best.rationale}")
    print(f"   一階銳度 w≈{best.w_K:.1f}K（文獻 FWHM 校準，回填 D5）")
    print("═" * 78)
    print(" 註：分數整合 Tc 對齊 × ΔS(場) / √成本 × 無稀土偏好；數值為文獻代表值。")


if __name__ == "__main__":
    main()
