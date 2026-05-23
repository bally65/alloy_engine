"""
清潔前後壓降與風量改善比較 CLI
用法: python scripts/cleaning_benefit.py \
        --velocity 1.5 --pitch 1.8 --height 25 \
        --elapsed 2000 --environment ac_indoor_unit
"""
import argparse
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fluidsim_skills.airflow import analyse_airflow
from fluidsim_skills.fouling import kern_seaton_fouling, FOULING_RESISTANCE_DB

_DEPOSIT_MAP = {
    'ac_indoor_unit':  'dust',
    'ac_outdoor_unit': 'dust',
    'city_water':      'scale',
    'coastal_air':     'dust',
    'industrial_air':  'grease',
    'kitchen_exhaust': 'grease',
}


def main():
    parser = argparse.ArgumentParser(description='清潔前後空氣側效能改善比較')
    parser.add_argument('--velocity',    type=float, required=True, help='面風速 (m/s)')
    parser.add_argument('--pitch',       type=float, default=1.8,   help='翅片間距 (mm)')
    parser.add_argument('--height',      type=float, default=25.0,  help='翅片深度 (mm)')
    parser.add_argument('--thickness',   type=float, default=0.1,   help='翅片厚度 (mm)')
    parser.add_argument('--elapsed',     type=float, required=True, help='已運行時數 (h)')
    parser.add_argument('--environment', type=str,   default='ac_indoor_unit',
                        choices=list(FOULING_RESISTANCE_DB.keys()))
    parser.add_argument('--temp',        type=float, default=25.0,  help='空氣溫度 (°C)')
    args = parser.parse_args()

    db = FOULING_RESISTANCE_DB[args.environment]
    Rf_current = kern_seaton_fouling(args.elapsed, db['Rf_star'], db['Kf'])
    deposit = _DEPOSIT_MAP.get(args.environment, 'dust')

    before = analyse_airflow(args.velocity, args.pitch, args.height,
                              args.thickness, Rf_current, deposit, args.temp)
    after  = analyse_airflow(args.velocity, args.pitch, args.height,
                              args.thickness, 0.0, deposit, args.temp)

    dp_recover = before.pressure_drop_fouled_pa - after.pressure_drop_clean_pa
    flow_recover = before.airflow_reduction_pct
    power_save = before.power_increase_pct

    print(f"\n清潔效益分析：{db['description']}")
    print(f"已運行 {args.elapsed:.0f} 小時，積垢熱阻 {Rf_current:.3e} m²·K/W")
    print(f"{'═'*52}")
    print(f"  {'項目':<20} {'清潔前':>12} {'清潔後':>12} {'改善':>8}")
    print(f"  {'─'*50}")
    print(f"  {'積垢層厚度 (μm/側)':<20} {before.fouling_layer_um:>12.1f} {'0.0':>12} "
          f"{'−'+f'{before.fouling_layer_um:.1f}':>8}")
    print(f"  {'有效間隙 (mm)':<20} {before.effective_gap_mm:>12.3f} "
          f"{before.effective_gap_mm + 2*before.fouling_layer_um*1e-3:>12.3f} "
          f"{'':>8}")
    print(f"  {'空氣側壓降 (Pa)':<20} {before.pressure_drop_fouled_pa:>12.2f} "
          f"{after.pressure_drop_clean_pa:>12.2f} "
          f"{'-'+f'{dp_recover:.2f}':>8}")
    print(f"  {'壓降增幅 (%)':<20} {before.pressure_increase_pct:>12.1f} {'0.0':>12} "
          f"{'−'+f'{before.pressure_increase_pct:.1f}':>8}")
    print(f"  {'風量衰退 (%)':<20} {flow_recover:>12.1f} {'0.0':>12} "
          f"{'恢復'+f'{flow_recover:.1f}%':>8}")
    print(f"  {'額外風機功率 (%)':<20} {power_save:>12.1f} {'0.0':>12} "
          f"{'節省'+f'{power_save:.1f}%':>8}")
    print(f"{'─'*52}")
    print(f"  清潔後: {after.recommendation}")
    print(f"{'═'*52}")


if __name__ == '__main__':
    main()
