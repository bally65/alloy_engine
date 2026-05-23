"""
翅片毛細滲透完整分析 CLI
用法: python scripts/fin_penetration.py --spacing 2.0 --height 15 --tension 30 --angle 25 --viscosity 0.001
"""
import argparse
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fluidsim_skills.capillary import analyse_fin_penetration, lucas_washburn_penetration


def main():
    parser = argparse.ArgumentParser(description='翅片縫隙毛細滲透分析')
    parser.add_argument('--spacing', type=float, required=True, help='翅片間距 (mm)')
    parser.add_argument('--height', type=float, required=True, help='翅片高度 (mm)')
    parser.add_argument('--tension', type=float, required=True, help='表面張力 (mN/m)')
    parser.add_argument('--angle', type=float, required=True, help='接觸角 (°)')
    parser.add_argument('--viscosity', type=float, default=1.0e-3, help='動力黏度 (Pa·s)')
    parser.add_argument('--name', type=str, default='清潔液', help='清潔液名稱')
    args = parser.parse_args()

    report = analyse_fin_penetration(
        fin_spacing_mm=args.spacing,
        fin_height_mm=args.height,
        surface_tension_mN=args.tension,
        contact_angle_deg=args.angle,
        dynamic_viscosity=args.viscosity,
        cleaner_name=args.name,
    )

    depth_10s = lucas_washburn_penetration(args.tension, args.angle,
                                            args.spacing / 2, args.viscosity, 10.0)
    depth_60s = lucas_washburn_penetration(args.tension, args.angle,
                                            args.spacing / 2, args.viscosity, 60.0)

    t_full = report.time_to_full_penetration_s
    t_half = report.time_to_half_penetration_s

    print(f"\n翅片毛細滲透分析：{report.cleaner_name}")
    print(f"{'═'*50}")
    print(f"  翅片間距:    {report.fin_spacing_mm:.1f} mm")
    print(f"  翅片高度:    {report.fin_height_mm:.1f} mm")
    print(f"  表面張力:    {report.surface_tension_mN:.1f} mN/m")
    print(f"  接觸角:      {report.contact_angle_deg:.1f}°")
    print(f"{'─'*50}")
    print(f"  毛細壓力:    {report.capillary_pressure_pa:+.2f} Pa")
    print(f"  10 秒滲透深: {depth_10s:.2f} mm")
    print(f"  60 秒滲透深: {depth_60s:.2f} mm")
    print(f"  滲透至 1/2:  {t_half:.1f} s" if t_half > 0 else "  滲透至 1/2:  無法自發滲透")
    print(f"  滲透至底部:  {t_full:.1f} s" if t_full > 0 else "  滲透至底部:  無法自發滲透")
    print(f"  對比純水:    {report.vs_water}")
    print(f"{'─'*50}")
    print(f"  建議: {report.recommendation}")
    print(f"{'═'*50}")


if __name__ == '__main__':
    main()
