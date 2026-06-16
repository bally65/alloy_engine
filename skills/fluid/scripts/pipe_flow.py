"""
完整管道流動分析 CLI
用法: python scripts/pipe_flow.py --diameter 0.025 --length 10 --flowrate 15 --temp 20
"""
import argparse
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fluidsim_skills.fluid import reynolds_number, flow_regime, water_properties


def main():
    parser = argparse.ArgumentParser(description='管道流動完整分析')
    parser.add_argument('--diameter', type=float, required=True, help='管道內徑 (m)')
    parser.add_argument('--length', type=float, required=True, help='管道長度 (m)')
    parser.add_argument('--flowrate', type=float, required=True, help='體積流量 (L/min)')
    parser.add_argument('--temp', type=float, default=20.0, help='流體溫度 (°C)')
    args = parser.parse_args()

    # F-PATH：輸入驗證（diameter=0 會導致面積為 0 → 除零）
    if args.diameter <= 0:
        parser.error("--diameter 必須 > 0 (m)")
    if args.flowrate < 0:
        parser.error("--flowrate 不可為負 (L/min)")

    props = water_properties(args.temp)
    area = 3.14159265 * (args.diameter / 2) ** 2
    velocity = (args.flowrate / 1000 / 60) / area
    Re = reynolds_number(args.diameter, velocity, props.kinematic_viscosity)
    regime = flow_regime(Re)
    regime_zh = {'laminar': '層流', 'transitional': '過渡流', 'turbulent': '紊流'}

    print(f"\n管道流動分析報告")
    print(f"{'═'*45}")
    print(f"[輸入條件]")
    print(f"  管道內徑:  {args.diameter*1000:.2f} mm")
    print(f"  管道長度:  {args.length:.2f} m")
    print(f"  體積流量:  {args.flowrate:.2f} L/min")
    print(f"  流體溫度:  {args.temp:.1f} °C")
    print(f"{'─'*45}")
    print(f"[流動特性]")
    print(f"  截面積:    {area*1e6:.2f} mm²")
    print(f"  平均流速:  {velocity:.3f} m/s  ({velocity*100:.1f} cm/s)")
    print(f"  雷諾數:    {Re:.0f}")
    print(f"  流態:      {regime_zh.get(regime, regime)}")
    print(f"{'─'*45}")
    print(f"[流體性質 @ {args.temp:.0f}°C]")
    print(f"  密度:      {props.density:.2f} kg/m³")
    print(f"  動力黏度:  {props.dynamic_viscosity:.2e} Pa·s")
    print(f"  運動黏度:  {props.kinematic_viscosity:.2e} m²/s")
    print(f"{'═'*45}")
    print(f"  → 建議使用 $pressure skill 計算管路壓損")


if __name__ == '__main__':
    main()
