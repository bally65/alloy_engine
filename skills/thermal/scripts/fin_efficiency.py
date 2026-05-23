"""
翅片效率計算 CLI（接受 alloy_engine κ 輸出）
用法: python scripts/fin_efficiency.py --height 15 --thickness 0.1 --kappa 205 --h-conv 30
"""
import argparse
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fluidsim_skills.thermal import fin_efficiency_from_kappa


def main():
    parser = argparse.ArgumentParser(description='矩形直翅片效率計算')
    parser.add_argument('--height', type=float, required=True, help='翅片高度 (mm)')
    parser.add_argument('--thickness', type=float, required=True, help='翅片厚度 (mm)')
    parser.add_argument('--kappa', type=float, required=True, help='熱傳導率 κ (W/m·K)')
    parser.add_argument('--h-conv', type=float, default=30.0, help='對流係數 h (W/m²·K)')
    args = parser.parse_args()

    report = fin_efficiency_from_kappa(
        fin_height_mm=args.height,
        fin_thickness_mm=args.thickness,
        kappa_W_mK=args.kappa,
        h_conv=args.h_conv,
    )

    eta_pct = report.fin_efficiency * 100

    if report.fin_efficiency > 0.95:
        grade = '優秀'
    elif report.fin_efficiency > 0.85:
        grade = '良好'
    elif report.fin_efficiency > 0.70:
        grade = '可接受'
    else:
        grade = '偏低，建議改善'

    print(f"\n翅片熱效率分析")
    print(f"{'═'*42}")
    print(f"  翅片高度:    {report.fin_height_mm:.1f} mm")
    print(f"  翅片厚度:    {report.fin_thickness_mm:.2f} mm")
    print(f"  熱傳導率 κ:  {report.thermal_conductivity:.1f} W/m·K")
    print(f"  對流係數 h:  {report.h_conv:.1f} W/m²·K")
    print(f"{'─'*42}")
    print(f"  翅片參數 m:  {report.m_parameter:.2f} m⁻¹")
    print(f"  翅片效率 η:  {eta_pct:.2f}%  ({grade})")
    print(f"  vs 標準鋁:   {report.heat_transfer_improvement}")
    for note in report.notes:
        print(f"  → {note}")
    print(f"{'═'*42}")


if __name__ == '__main__':
    main()
