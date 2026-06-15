"""
端到端整機效能預估報告（Direction #2）：用文獻校準 + 不確定度，對推薦材料跑完整
design_tmg，輸出帶誤差條的整機 P/V、η，並套 D12 現實折減。

執行：python scripts/calibrated_device_report.py [--temp 47]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from alloy_engine.thermomagnetic.uncertainty import device_performance_with_uncertainty


MATERIALS = [
    ("La(Fe,Si)13H", 47.0),       # 推薦主力（可氫化調 Tc）
    ("(Mn,Fe)2(P,Si)", 27.0),     # 無稀土備援
    ("Gd (純釓)", 21.0),           # 二階校準基準
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-samples", type=int, default=2000)
    args = ap.parse_args()

    print("═" * 80)
    print(" 端到端整機效能預估（文獻校準 ΔS/w + ±12% 不確定度傳播）")
    print("═" * 80)
    print(f"{'材料':<16}{'工作°C':>7}{'P/V 理想 kW/m³':>18}{'現實(÷10)':>11}{'η/η_C %':>14}")
    print("-" * 80)
    for mat, T in MATERIALS:
        r = device_performance_with_uncertainty(mat, T, n_samples=args.n_samples)
        print(f"{mat:<16}{T:>7.0f}"
              f"{r.power_W_m3_mean/1e3:>10.0f} ± {r.power_W_m3_std/1e3:<5.0f}"
              f"{r.power_realistic_W_m3/1e3:>11.0f}"
              f"{r.eta_rel_carnot_mean*100:>9.2f} ± {r.eta_rel_carnot_std*100:<4.2f}")
    print("-" * 80)
    print(" 解讀：")
    print("  • 誤差條 ~±12% 來自文獻散布：P/V 來自 ΔM（功率僅依 ΔM），η 來自 ΔM 與 ΔS。")
    print("  • 『理想』為 design_tmg 上界；『現實』套 D12 量化的 ~10× 折減。")
    print("  • La-Fe-Si 與 Gd 因高 κ → 高循環頻率 → 高 P/V；一階材料 ΔS 大但 κ 低。")
    print("═" * 80)


if __name__ == "__main__":
    main()
