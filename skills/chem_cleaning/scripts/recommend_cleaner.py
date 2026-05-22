"""
清潔劑自動推薦 CLI
用法: python scripts/recommend_cleaner.py --contamination grease_heavy --fin-material aluminum
"""
import argparse
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fluidsim_skills.chemistry import recommend_cleaner, CONTAMINATION_DB


def main():
    parser = argparse.ArgumentParser(description='自動推薦最佳清潔劑與操作條件')
    parser.add_argument('--contamination', type=str, required=True,
                        choices=list(CONTAMINATION_DB.keys()), help='污垢類型')
    parser.add_argument('--fin-material', type=str, default='aluminum',
                        choices=['aluminum', 'copper'], help='翅片材質')
    parser.add_argument('--fin-spacing', type=float, default=1.2, help='翅片間距 mm')
    parser.add_argument('--target', type=float, default=0.80, help='目標溶解分率 0~1')
    parser.add_argument('--temp', type=float, default=25.0, help='環境溫度 °C')
    args = parser.parse_args()

    report = recommend_cleaner(
        contamination_key=args.contamination,
        fin_material=args.fin_material,
        fin_spacing_mm=args.fin_spacing,
        target_effectiveness=args.target,
        temperature_C=args.temp,
    )

    eff_icon = {'優': '★★★★', '良': '★★★☆', '可': '★★☆☆', '差': '★☆☆☆'}

    print(f"\n清潔劑推薦報告")
    print(f"{'═'*52}")
    print(f"  污垢類型:     {report.contamination}")
    print(f"  翅片材質:     {args.fin_material} ({'鋁' if args.fin_material=='aluminum' else '銅'}翅片)")
    print(f"{'─'*52}")
    print(f"[推薦清潔劑]")
    print(f"  清潔劑:       {report.recommended_cleaner}")
    print(f"  使用濃度:     {report.concentration_pct:.1f}% (v/v)")
    print(f"  接觸時間:     {report.contact_time_min:.0f} 分鐘")
    print(f"  預期效果:     {report.combined_effectiveness}  {eff_icon.get(report.combined_effectiveness,'')}")
    print(f"  溶解分率:     {report.dissolved_fraction*100:.1f}%")
    print(f"{'─'*52}")
    print(f"[表面力學]")
    print(f"  清潔液表面張力: {report.surface_tension_mN:.1f} mN/m")
    print(f"  接觸角:         {report.contact_angle_deg:.1f}°")
    print(f"{'─'*52}")

    if report.warnings:
        print(f"[注意事項]")
        for w in report.warnings:
            print(f"  {w}")
        print(f"{'─'*52}")

    print(f"[清潔作業程序]")
    for step in report.procedure:
        print(f"  {step}")

    if report.alternatives:
        print(f"{'─'*52}")
        print(f"[替代方案]")
        for alt in report.alternatives:
            print(f"  • {alt}")

    print(f"{'═'*52}")


if __name__ == '__main__':
    main()
