"""
毛細壓力計算 CLI
用法: python scripts/capillary_pressure.py --tension 30 --angle 25 --spacing 1.0
"""
import argparse
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fluidsim_skills.capillary import capillary_pressure, capillary_rise_height


def main():
    parser = argparse.ArgumentParser(description='Laplace-Young 毛細壓力計算')
    parser.add_argument('--tension', type=float, required=True, help='表面張力 (mN/m)')
    parser.add_argument('--angle', type=float, required=True, help='接觸角 (°)')
    parser.add_argument('--spacing', type=float, required=True, help='翅片半間距 (mm)')
    parser.add_argument('--density', type=float, default=998.2, help='液體密度 (kg/m³)')
    args = parser.parse_args()

    pc = capillary_pressure(args.tension, args.angle, args.spacing)
    h = capillary_rise_height(args.tension, args.angle, args.spacing, args.density)

    status = '可自發滲入 ✓' if pc > 0 else ('無法自發滲入 ✗' if pc < 0 else '臨界（θ=90°）')

    print(f"\n毛細壓力計算結果")
    print(f"{'═'*42}")
    print(f"  表面張力:    {args.tension:.1f} mN/m")
    print(f"  接觸角:      {args.angle:.1f}°")
    print(f"  翅片半間距:  {args.spacing:.2f} mm")
    print(f"{'─'*42}")
    print(f"  毛細壓力:    {pc:+.2f} Pa")
    print(f"  毛細上升高:  {h:+.1f} mm")
    print(f"  自發滲透:    {status}")
    print(f"{'═'*42}")


if __name__ == '__main__':
    main()
