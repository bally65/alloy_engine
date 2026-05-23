"""
空氣側壓降與積垢風量衰退分析 CLI
用法: python scripts/airflow_analysis.py \
        --velocity 1.5 --pitch 1.8 --height 25 --thickness 0.1 \
        --Rf 1.4e-4 --deposit dust
"""
import argparse
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fluidsim_skills.airflow import analyse_airflow, air_properties


def main():
    parser = argparse.ArgumentParser(description='翅片空氣側壓降與積垢風量衰退分析')
    parser.add_argument('--velocity',   type=float, required=True, help='面風速 (m/s)')
    parser.add_argument('--pitch',      type=float, required=True, help='翅片間距 (mm)')
    parser.add_argument('--height',     type=float, required=True, help='翅片深度（氣流方向）(mm)')
    parser.add_argument('--thickness',  type=float, default=0.1,   help='翅片厚度 (mm)')
    parser.add_argument('--Rf',         type=float, default=0.0,   help='積垢熱阻 (m²·K/W)')
    parser.add_argument('--deposit',    type=str,   default='dust',
                        choices=['dust', 'grease', 'biofilm', 'scale'], help='積垢類型')
    parser.add_argument('--temp',       type=float, default=25.0,  help='空氣溫度 (°C)')
    args = parser.parse_args()

    result = analyse_airflow(
        face_velocity_ms=args.velocity,
        fin_pitch_mm=args.pitch,
        fin_height_mm=args.height,
        fin_thickness_mm=args.thickness,
        Rf_current=args.Rf,
        deposit_type=args.deposit,
        temperature_C=args.temp,
    )

    props = air_properties(args.temp)

    def bar(val, max_val, width=16):
        filled = max(0, min(width, int(round(val / max_val * width))))
        return '█' * filled + '░' * (width - filled)

    print(f"\n空氣側壓降與積垢分析")
    print(f"{'═'*50}")
    print(f"  面風速:       {result.face_velocity_ms:.2f} m/s")
    print(f"  翅片間距:     {args.pitch:.2f} mm（有效間隙 {args.pitch - args.thickness:.2f} mm）")
    print(f"  翅片深度:     {args.height:.1f} mm")
    print(f"  空氣溫度:     {args.temp:.1f} °C（密度 {props.density:.3f} kg/m³）")
    print(f"{'─'*50}")
    print(f"  最小截面風速: {result.max_velocity_ms:.2f} m/s")
    print(f"  Re（水力徑）: {result.reynolds_number:.0f}")
    print(f"{'─'*50}")
    print(f"  乾淨翅片壓降: {result.pressure_drop_clean_pa:.2f} Pa")
    if args.Rf > 0:
        print(f"  積垢層厚度:   {result.fouling_layer_um:.1f} μm（每側）")
        print(f"  積垢後間隙:   {result.effective_gap_mm:.3f} mm")
        print(f"  積垢後壓降:   {result.pressure_drop_fouled_pa:.2f} Pa")
        print(f"  壓降增幅:     {result.pressure_increase_pct:.1f}% {bar(result.pressure_increase_pct, 50)}")
        print(f"  風量衰退:     {result.airflow_reduction_pct:.1f}% {bar(result.airflow_reduction_pct, 30)}")
        print(f"  功率增加:     {result.power_increase_pct:.1f}%")
    print(f"{'─'*50}")
    for note in result.notes:
        print(f"  ℹ {note}")
    print(f"  建議: {result.recommendation}")
    print(f"{'═'*50}")


if __name__ == '__main__':
    main()
