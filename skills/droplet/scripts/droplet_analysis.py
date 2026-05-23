"""
液滴動力學分析 CLI
用法: python scripts/droplet_analysis.py --velocity 10 --diameter 0.2 --density 998 --tension 72.8
"""
import argparse
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fluidsim_skills.droplet import analyse_droplet, weber_number, ohnesorge_number


def main():
    parser = argparse.ArgumentParser(description='液滴 Weber/Ohnesorge 數與破碎模式分析')
    parser.add_argument('--velocity', type=float, required=True, help='液滴速度 (m/s)')
    parser.add_argument('--diameter', type=float, required=True, help='液滴直徑 (mm)')
    parser.add_argument('--density', type=float, default=998.2, help='液體密度 (kg/m³)')
    parser.add_argument('--tension', type=float, default=72.8, help='表面張力 (mN/m)')
    parser.add_argument('--viscosity', type=float, default=1.002e-3, help='動力黏度 (Pa·s)')
    args = parser.parse_args()

    result = analyse_droplet(
        velocity=args.velocity,
        diameter_mm=args.diameter,
        surface_tension_mN=args.tension,
        density=args.density,
        dynamic_viscosity=args.viscosity,
    )

    regime_map = {
        'intact': '完整液滴',
        'stretching_breakup': '袋式/拉伸破碎',
        'catastrophic_breakup': '劇烈霧化',
    }

    print(f"\n液滴動力學分析")
    print(f"{'═'*44}")
    print(f"  液滴速度:    {args.velocity:.2f} m/s")
    print(f"  液滴直徑:    {args.diameter:.3f} mm")
    print(f"  表面張力:    {args.tension:.1f} mN/m")
    print(f"  密度:        {args.density:.1f} kg/m³")
    print(f"{'─'*44}")
    print(f"  Weber 數 We: {result.weber_number:.2f}")
    print(f"  Ohnesorge Oh:{result.ohnesorge_number:.4f}")
    print(f"  破碎模式:    {regime_map.get(result.regime, result.regime)}")
    print(f"  說明:        {result.regime_description}")
    print(f"  臨界流速:    {result.critical_velocity:.2f} m/s（破碎起始點）")
    print(f"{'═'*44}")


if __name__ == '__main__':
    main()
