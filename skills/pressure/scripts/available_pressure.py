"""
噴嘴前可用壓力計算 CLI
用法: python scripts/available_pressure.py --supply 3.5 --pipe-d 9.5 --length 5 --flowrate 8
"""
import argparse
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fluidsim_skills.pressure import available_nozzle_pressure, pressure_drop


def main():
    parser = argparse.ArgumentParser(description='計算噴嘴前可用壓力')
    parser.add_argument('--supply', type=float, required=True, help='水源供應壓力 (bar)')
    parser.add_argument('--pipe-d', type=float, required=True, help='管道內徑 (mm)')
    parser.add_argument('--length', type=float, required=True, help='管道長度 (m)')
    parser.add_argument('--flowrate', type=float, required=True, help='流量 (L/min)')
    parser.add_argument('--temp', type=float, default=20.0, help='水溫 (°C)')
    parser.add_argument('--fittings-k', type=float, default=2.0, help='配件損失係數總和')
    args = parser.parse_args()

    pipe_d = args.pipe_d / 1000
    result = pressure_drop(
        diameter=pipe_d,
        length=args.length,
        flowrate_lpm=args.flowrate,
        temperature_C=args.temp,
        minor_loss_K=args.fittings_k,
    )
    nozzle_p = args.supply - result.total_loss_bar

    print(f"\n噴嘴前壓力分析")
    print(f"{'═'*40}")
    print(f"  水源壓力:    {args.supply:.2f} bar")
    print(f"  管路壓損:  - {result.total_loss_bar:.4f} bar")
    print(f"  ─────────────────────────────────")
    print(f"  噴嘴前壓力:  {max(nozzle_p, 0):.3f} bar")
    print(f"{'─'*40}")
    if nozzle_p < 1.5:
        print(f"  ⚠ 壓力不足，建議使用加壓泵或縮短管路")
    elif nozzle_p < 2.5:
        print(f"  → 適合輕度清潔（搭配清潔劑效果更佳）")
    elif nozzle_p < 5.0:
        print(f"  → 適合一般蒸發器翅片清潔")
    else:
        print(f"  → 高壓清潔，注意避免翅片變形")
    print(f"{'═'*40}")


if __name__ == '__main__':
    main()
