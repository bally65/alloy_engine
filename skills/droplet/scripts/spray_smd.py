"""
壓力噴嘴 Sauter 平均直徑（SMD）估算 CLI
用法: python scripts/spray_smd.py --pressure 3.0 --orifice 2.0 --tension 30
"""
import argparse
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fluidsim_skills.droplet import spray_droplet_size


def main():
    parser = argparse.ArgumentParser(description='壓力噴嘴 SMD 估算（Hiroyasu-Arai）')
    parser.add_argument('--pressure', type=float, required=True, help='噴嘴前壓力 (bar)')
    parser.add_argument('--orifice', type=float, required=True, help='噴嘴孔徑 (mm)')
    parser.add_argument('--tension', type=float, default=72.8, help='表面張力 (mN/m)')
    parser.add_argument('--density', type=float, default=998.2, help='液體密度 (kg/m³)')
    args = parser.parse_args()

    smd = spray_droplet_size(
        pressure_bar=args.pressure,
        orifice_diameter_mm=args.orifice,
        surface_tension_mN=args.tension,
        density=args.density,
    )

    if smd < 100:
        quality = '霧化極細，適合薄膜均勻覆蓋'
    elif smd < 300:
        quality = '適合翅片縫隙穿透清潔'
    elif smd < 600:
        quality = '液滴較大，穿透力強但均勻性較差'
    else:
        quality = '液滴過大，建議提高壓力或縮小孔徑'

    print(f"\n壓力噴嘴 SMD 估算")
    print(f"{'═'*42}")
    print(f"  噴嘴壓力:    {args.pressure:.2f} bar")
    print(f"  噴嘴孔徑:    {args.orifice:.2f} mm")
    print(f"  表面張力:    {args.tension:.1f} mN/m")
    print(f"  液體密度:    {args.density:.1f} kg/m³")
    print(f"{'─'*42}")
    print(f"  SMD:         {smd:.1f} μm")
    print(f"  霧化品質:    {quality}")
    print(f"{'═'*42}")


if __name__ == '__main__':
    main()
