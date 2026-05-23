"""
噴嘴流量與衝擊力計算 CLI
用法: python scripts/nozzle_calc.py --pressure 2.8 --orifice 2.0 --distance 150 --angle 25
"""
import argparse
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fluidsim_skills.cleaning import nozzle_impact_force, nozzle_flowrate


def main():
    parser = argparse.ArgumentParser(description='噴嘴流量與衝擊力計算')
    parser.add_argument('--pressure', type=float, required=True, help='噴嘴前壓力 (bar)')
    parser.add_argument('--orifice', type=float, required=True, help='噴嘴孔徑 (mm)')
    parser.add_argument('--distance', type=float, default=150.0, help='噴嘴到目標距離 mm')
    parser.add_argument('--angle', type=float, default=15.0, help='噴霧全角 (度)')
    parser.add_argument('--cd', type=float, default=0.65, help='流量係數 Cd')
    args = parser.parse_args()

    result = nozzle_impact_force(
        pressure_bar=args.pressure,
        orifice_diameter_mm=args.orifice,
        distance_mm=args.distance,
        spray_angle_deg=args.angle,
        discharge_coeff=args.cd,
    )

    # 翅片安全評估
    if result.impact_pressure_kpa > 100:
        safety = "⚠ 高衝擊壓力，注意銅翅片變形風險"
    elif result.impact_pressure_kpa > 50:
        safety = "⚠ 注意鋁翅片變形風險，建議加大距離"
    elif result.impact_pressure_kpa > 15:
        safety = "✓ 適合蒸發器翅片清潔"
    else:
        safety = "→ 衝擊壓力偏低，對深層污垢效果有限"

    print(f"\n噴嘴計算結果")
    print(f"{'═'*42}")
    print(f"  孔徑:        {result.orifice_diameter_mm:.1f} mm")
    print(f"  壓力:        {args.pressure:.2f} bar")
    print(f"  流量係數:    {args.cd:.2f}")
    print(f"{'─'*42}")
    print(f"  流量:        {result.flowrate_lpm:.3f} L/min")
    print(f"  噴出流速:    {result.exit_velocity:.2f} m/s")
    print(f"  衝擊力:      {result.impact_force_N:.3f} N")
    print(f"  衝擊壓力:    {result.impact_pressure_kpa:.2f} kPa")
    print(f"  覆蓋寬度:    {result.coverage_width_mm:.1f} mm（@ {args.distance:.0f}mm）")
    print(f"{'─'*42}")
    print(f"  翅片安全:    {safety}")
    print(f"{'═'*42}")


if __name__ == '__main__':
    main()
