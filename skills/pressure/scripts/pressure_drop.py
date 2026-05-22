"""
管路壓降計算 CLI
用法: python scripts/pressure_drop.py --diameter 9.5 --length 5 --flowrate 10 --temp 20
"""
import argparse
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fluidsim_skills.pressure import pressure_drop, FITTING_K_VALUES
from fluidsim_skills.fluid import flow_regime


def main():
    parser = argparse.ArgumentParser(description='Darcy-Weisbach 管路壓降計算')
    parser.add_argument('--diameter', type=float, required=True, help='管道內徑 (mm)')
    parser.add_argument('--length', type=float, required=True, help='管道長度 (m)')
    parser.add_argument('--flowrate', type=float, required=True, help='體積流量 (L/min)')
    parser.add_argument('--temp', type=float, default=20.0, help='流體溫度 (°C)')
    parser.add_argument('--roughness', type=float, default=1.5e-5, help='管壁粗糙度 (m)')
    parser.add_argument('--fittings-k', type=float, default=0.0,
                        help='管路配件局部損失係數總和')
    parser.add_argument('--pipe-material', type=str, default=None,
                        choices=['steel', 'copper', 'pvc'],
                        help='管材（自動設定粗糙度）')
    args = parser.parse_args()

    roughness_map = {'steel': 1.5e-5, 'copper': 1.5e-6, 'pvc': 1.5e-6}
    roughness = roughness_map.get(args.pipe_material, args.roughness)

    result = pressure_drop(
        diameter=args.diameter / 1000,
        length=args.length,
        flowrate_lpm=args.flowrate,
        temperature_C=args.temp,
        roughness_m=roughness,
        minor_loss_K=args.fittings_k,
    )

    regime_zh = {'laminar': '層流', 'transitional': '過渡流', 'turbulent': '紊流'}
    regime = flow_regime(result.reynolds)

    print(f"\n管路壓降分析報告")
    print(f"{'═'*45}")
    print(f"[輸入條件]")
    print(f"  管道內徑:  {args.diameter:.2f} mm")
    print(f"  管道長度:  {args.length:.2f} m")
    print(f"  體積流量:  {args.flowrate:.2f} L/min")
    print(f"  流體溫度:  {args.temp:.1f} °C")
    print(f"  配件損失K: {args.fittings_k:.2f}")
    print(f"{'─'*45}")
    print(f"[流動特性]")
    print(f"  平均流速:  {result.velocity:.3f} m/s")
    print(f"  雷諾數:    {result.reynolds:.0f}  ({regime_zh.get(regime, regime)})")
    print(f"  摩擦係數:  {result.friction_factor:.5f}")
    print(f"{'─'*45}")
    print(f"[壓損結果]")
    print(f"  直管摩擦損失: {result.friction_loss_pa:.1f} Pa  ({result.friction_loss_pa/1e5:.4f} bar)")
    print(f"  局部損失:     {result.minor_loss_pa:.1f} Pa  ({result.minor_loss_pa/1e5:.4f} bar)")
    print(f"  ─────────────────────────────────────────")
    print(f"  總壓損:       {result.total_loss_pa:.1f} Pa  ({result.total_loss_bar:.4f} bar)")
    print(f"{'═'*45}")


if __name__ == '__main__':
    main()
