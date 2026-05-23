"""
清潔週期計算 CLI
用法: python scripts/cleaning_schedule.py --environment ac_indoor_unit --U-clean 50 --target-loss 10
"""
import argparse
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fluidsim_skills.fouling import cleaning_interval, FOULING_RESISTANCE_DB


def main():
    parser = argparse.ArgumentParser(description='基於積垢模型計算建議清潔週期')
    parser.add_argument('--environment', type=str, default='ac_indoor_unit',
                        choices=list(FOULING_RESISTANCE_DB.keys()), help='環境類型')
    parser.add_argument('--U-clean', type=float, default=50.0, help='乾淨換熱係數 (W/m²·K)')
    parser.add_argument('--target-loss', type=float, default=10.0, help='清潔門檻效率損失 (%)')
    args = parser.parse_args()

    db = FOULING_RESISTANCE_DB[args.environment]
    t = cleaning_interval(
        U_clean=args.U_clean,
        asymptotic_Rf=db['Rf_star'],
        fouling_rate_constant=db['Kf'],
        target_efficiency_loss_pct=args.target_loss,
    )

    print(f"\n清潔週期分析")
    print(f"{'═'*50}")
    print(f"  環境:         {db['description']}")
    print(f"  乾淨換熱係數: {args.U_clean:.0f} W/m²·K")
    print(f"  清潔門檻:     {args.target_loss:.0f}% 效率損失")
    print(f"{'─'*50}")
    if t == float('inf'):
        print(f"  結論: 積垢永遠不會達到 {args.target_loss:.0f}% 效率損失門檻")
        print(f"        （漸近積垢熱阻不足以造成此損失）")
    else:
        print(f"  建議清潔週期: {t:.0f} 小時")
        print(f"                約 {t/24:.0f} 天 / {t/8760:.2f} 年")
        if t < 500:
            print(f"  → 積垢快，建議每月檢查")
        elif t < 3000:
            print(f"  → 建議每年清潔")
        else:
            print(f"  → 積垢緩慢，每 2–3 年清潔一次即可")
    print(f"{'═'*50}")

    print(f"\n所有環境類型清潔週期比較：")
    print(f"  {'環境':<20} {'週期(h)':>10} {'週期(年)':>10}")
    print(f"  {'─'*42}")
    for env_key, env_data in FOULING_RESISTANCE_DB.items():
        t_env = cleaning_interval(args.U_clean, env_data['Rf_star'],
                                   env_data['Kf'], args.target_loss)
        t_str = f"{t_env:.0f}" if t_env < float('inf') else "∞"
        yr_str = f"{t_env/8760:.2f}" if t_env < float('inf') else "∞"
        marker = ' ◀' if env_key == args.environment else ''
        print(f"  {env_key:<20} {t_str:>10} {yr_str:>10}{marker}")


if __name__ == '__main__':
    main()
