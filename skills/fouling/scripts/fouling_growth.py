"""
積垢成長分析 CLI
用法: python scripts/fouling_growth.py --time 2000 --environment ac_indoor_unit --U-clean 50
"""
import argparse
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fluidsim_skills.fouling import analyse_fouling, FOULING_RESISTANCE_DB


def main():
    parser = argparse.ArgumentParser(description='Kern-Seaton 積垢成長分析')
    parser.add_argument('--time', type=float, required=True, help='已運行時數 (h)')
    parser.add_argument('--environment', type=str, default='ac_indoor_unit',
                        choices=list(FOULING_RESISTANCE_DB.keys()), help='環境類型')
    parser.add_argument('--U-clean', type=float, default=50.0, help='乾淨換熱係數 (W/m²·K)')
    parser.add_argument('--target-loss', type=float, default=10.0, help='清潔門檻效率損失 (%)')
    args = parser.parse_args()

    report = analyse_fouling(
        elapsed_hours=args.time,
        environment=args.environment,
        U_clean=args.U_clean,
        target_loss_pct=args.target_loss,
    )

    db = FOULING_RESISTANCE_DB[args.environment]

    print(f"\n積垢分析報告")
    print(f"{'═'*50}")
    for note in report.notes:
        print(f"  {note}")
    print(f"  運行時數:    {report.elapsed_hours:.0f} h")
    print(f"{'─'*50}")
    print(f"  當前積垢熱阻:  {report.current_Rf:.3e} m²·K/W")
    print(f"  漸近積垢熱阻:  {report.asymptotic_Rf:.3e} m²·K/W")
    print(f"  積垢飽和度:    {report.current_Rf/report.asymptotic_Rf*100:.1f}%")
    print(f"  效率損失:      {report.efficiency_penalty_pct:.2f}%")
    if report.time_to_threshold_h > 0:
        print(f"  距清潔門檻:    {report.time_to_threshold_h:.0f} h")
    else:
        print(f"  距清潔門檻:    已超標，請立即清潔")
    print(f"{'─'*50}")
    print(f"  建議: {report.recommendation}")
    print(f"{'═'*50}")


if __name__ == '__main__':
    main()
