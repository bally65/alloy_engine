"""
雷諾數計算與流態判斷 CLI
用法: python scripts/reynolds.py --diameter 0.025 --velocity 2.5 --fluid water --temp 20
"""
import argparse
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fluidsim_skills.fluid import reynolds_number, flow_regime, water_properties


def main():
    parser = argparse.ArgumentParser(description='計算雷諾數與判斷流態')
    parser.add_argument('--diameter', type=float, required=True, help='管道內徑 (m)')
    parser.add_argument('--velocity', type=float, help='平均流速 (m/s)')
    parser.add_argument('--flowrate', type=float, help='體積流量 (L/min)，與 --velocity 擇一')
    parser.add_argument('--fluid', type=str, default='water', choices=['water'], help='流體種類')
    parser.add_argument('--temp', type=float, default=20.0, help='流體溫度 (°C)')
    args = parser.parse_args()

    if args.velocity is None and args.flowrate is None:
        parser.error('需提供 --velocity 或 --flowrate 其中一個')

    props = water_properties(args.temp)

    if args.flowrate is not None:
        area = 3.14159265 * (args.diameter / 2) ** 2
        velocity = (args.flowrate / 1000 / 60) / area
    else:
        velocity = args.velocity

    Re = reynolds_number(args.diameter, velocity, props.kinematic_viscosity)
    regime = flow_regime(Re)

    regime_zh = {'laminar': '層流', 'transitional': '過渡流', 'turbulent': '紊流'}

    print(f"\n流體力學分析結果")
    print(f"{'─'*40}")
    print(f"管道內徑:   {args.diameter*1000:.2f} mm")
    print(f"平均流速:   {velocity:.3f} m/s")
    print(f"流體溫度:   {args.temp:.1f} °C")
    print(f"流體密度:   {props.density:.1f} kg/m³")
    print(f"動力黏度:   {props.dynamic_viscosity:.2e} Pa·s")
    print(f"{'─'*40}")
    print(f"雷諾數:     {Re:.0f}")
    print(f"流態:       {regime_zh.get(regime, regime)} ({regime})")
    print(f"{'─'*40}")


if __name__ == '__main__':
    main()
