"""
Dittus-Boelter 對流換熱係數計算 CLI
用法: python scripts/fouling_htc.py --velocity 1.5 --diameter 9.5 --temp 25
"""
import argparse
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fluidsim_skills.thermal import dittus_boelter_h
from fluidsim_skills.fluid import reynolds_number, water_properties, flow_regime


def main():
    parser = argparse.ArgumentParser(description='Dittus-Boelter 對流換熱係數')
    parser.add_argument('--velocity', type=float, required=True, help='管內流速 (m/s)')
    parser.add_argument('--diameter', type=float, required=True, help='管道內徑 (mm)')
    parser.add_argument('--temp', type=float, default=25.0, help='流體溫度 (°C)')
    parser.add_argument('--cooling', action='store_true', help='流體被冷卻（預設為加熱模式）')
    args = parser.parse_args()

    d_m = args.diameter / 1000
    props = water_properties(args.temp)
    Re = reynolds_number(d_m, args.velocity, props.kinematic_viscosity)
    regime = flow_regime(Re)
    h = dittus_boelter_h(args.velocity, d_m, args.temp, heating=not args.cooling)

    if Re < 10000:
        note = f"⚠ Re={Re:.0f} < 10000，Dittus-Boelter 超出適用範圍（建議 Re > 10000）"
    else:
        note = f"✓ Re={Re:.0f}，{regime}"

    print(f"\nDittus-Boelter 對流換熱係數")
    print(f"{'═'*42}")
    print(f"  管徑:        {args.diameter:.1f} mm")
    print(f"  流速:        {args.velocity:.2f} m/s")
    print(f"  溫度:        {args.temp:.1f} °C")
    print(f"  模式:        {'加熱' if not args.cooling else '冷卻'}")
    print(f"{'─'*42}")
    print(f"  雷諾數:      {Re:.0f}")
    print(f"  換熱係數 h:  {h:.1f} W/m²·K")
    print(f"  {note}")
    print(f"{'═'*42}")


if __name__ == '__main__':
    main()
