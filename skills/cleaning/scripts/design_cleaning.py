"""
冷氣清潔系統完整設計 CLI
用法: python scripts/design_cleaning.py --equipment "日立RAS-28NK" --width 750 --height 200 --supply 3.0
"""
import argparse
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fluidsim_skills.cleaning import design_cleaning_system


def main():
    parser = argparse.ArgumentParser(description='冷氣清潔系統設計')
    parser.add_argument('--equipment', type=str, required=True, help='冷氣設備名稱/型號')
    parser.add_argument('--width', type=float, required=True, help='蒸發器寬度 (mm)')
    parser.add_argument('--height', type=float, required=True, help='蒸發器高度 (mm)')
    parser.add_argument('--supply', type=float, required=True, help='水源供應壓力 (bar)')
    parser.add_argument('--pipe-d', type=float, default=9.5, help='清潔管路內徑 mm（預設 9.5mm = 3/8"）')
    parser.add_argument('--pipe-length', type=float, default=3.0, help='管路長度 m（預設 3m）')
    parser.add_argument('--distance', type=float, default=150.0, help='噴嘴到翅片距離 mm（預設 150mm）')
    parser.add_argument('--temp', type=float, default=20.0, help='水溫 °C（預設 20°C）')
    args = parser.parse_args()

    report = design_cleaning_system(
        equipment_name=args.equipment,
        evaporator_width_mm=args.width,
        evaporator_height_mm=args.height,
        supply_pressure_bar=args.supply,
        pipe_diameter_mm=args.pipe_d,
        pipe_length_m=args.pipe_length,
        target_distance_mm=args.distance,
        temperature_C=args.temp,
    )

    print(f"\n{'═'*55}")
    print(f"  冷氣清潔系統設計報告")
    print(f"  設備：{report.equipment}")
    print(f"{'═'*55}")

    print(f"\n[壓力分析]")
    print(f"  水源壓力:      {report.supply_pressure_bar:.2f} bar")
    print(f"  管路壓損:    - {report.pipe_loss_bar:.3f} bar")
    print(f"  噴嘴前壓力:    {report.nozzle_pressure_bar:.2f} bar")

    print(f"\n[噴嘴規格]")
    n = report.nozzle
    print(f"  推薦孔徑:      {n.orifice_diameter_mm:.1f} mm")
    print(f"  噴霧角度:      {n.spray_angle_deg:.0f}°")
    print(f"  流量:          {n.flowrate_lpm:.2f} L/min")
    print(f"  噴出流速:      {n.exit_velocity:.1f} m/s")
    print(f"  衝擊力:        {n.impact_force_N:.2f} N")
    print(f"  衝擊壓力:      {n.impact_pressure_kpa:.1f} kPa")
    print(f"  覆蓋寬度:      {n.coverage_width_mm:.0f} mm（距離 {report.recommended_distance_mm:.0f}mm）")

    print(f"\n[清潔參數]")
    print(f"  預計清潔時間:  {report.estimated_cleaning_time_min:.0f} 分鐘")

    if report.warnings:
        print(f"\n[注意事項]")
        for w in report.warnings:
            print(f"  ⚠ {w}")

    print(f"\n[清潔作業程序]")
    for step in report.procedure:
        print(f"  {step}")

    print(f"\n{'═'*55}")


if __name__ == '__main__':
    main()
