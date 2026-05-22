"""
溶解動力學計算 CLI
用法: python scripts/dissolution_calc.py --contamination grease_light --cleaner alkaline_mild --conc 2.0 --time 10
"""
import argparse
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fluidsim_skills.chemistry import (
    noyes_whitney_dissolution, surface_forces,
    CONTAMINATION_DB, CLEANER_DB
)


def main():
    parser = argparse.ArgumentParser(description='溶解動力學計算（Noyes-Whitney）')
    parser.add_argument('--contamination', type=str, required=True,
                        choices=list(CONTAMINATION_DB.keys()), help='污垢類型')
    parser.add_argument('--cleaner', type=str, required=True,
                        choices=list(CLEANER_DB.keys()), help='清潔劑類型')
    parser.add_argument('--conc', type=float, required=True, help='清潔劑濃度 %%')
    parser.add_argument('--time', type=float, required=True, help='接觸時間 (分鐘)')
    parser.add_argument('--temp', type=float, default=25.0, help='溫度 °C')
    parser.add_argument('--fin-spacing', type=float, default=1.2, help='翅片間距 mm')
    parser.add_argument('--flow-velocity', type=float, default=1.5, help='清潔水流速 m/s')
    args = parser.parse_args()

    result = noyes_whitney_dissolution(
        args.contamination, args.time, args.cleaner, args.conc, args.temp
    )
    forces = surface_forces(args.cleaner, args.conc, args.flow_velocity, args.fin_spacing)

    eff_label = '✓ 有效' if result.effective else '✗ 效果不足'

    print(f"\n化學溶解動力學分析")
    print(f"{'═'*50}")
    print(f"[污垢]  {result.contamination_type}")
    print(f"[清潔劑] {result.cleaner_name}  {args.conc:.1f}%")
    print(f"[條件]  {args.time:.0f} 分鐘接觸，{args.temp:.0f}°C")
    print(f"{'─'*50}")
    print(f"溶解動力學（Noyes-Whitney）：")
    print(f"  溶解分率:      {result.dissolved_fraction*100:.1f}%")
    print(f"  剩餘污垢:      {result.remaining_mass_pct:.1f}%")
    print(f"  效果評估:      {eff_label}")
    print(f"{'─'*50}")
    print(f"表面力學：")
    print(f"  清潔液表面張力: {forces.surface_tension_mN:.1f} mN/m  (純水 72.8 mN/m)")
    print(f"  接觸角:         {forces.contact_angle_deg:.1f}°  (越小越好，代表鋪展性佳)")
    print(f"  鋪展係數:       {forces.spreading_coefficient:.2f}  (正值代表可自發鋪展)")
    print(f"  翅片剪切應力:   {forces.shear_stress_Pa:.1f} Pa")
    print(f"  滑動力:         {forces.sliding_force_N_per_m2:.1f} N/m²")
    print(f"{'═'*50}")


if __name__ == '__main__':
    main()
