"""
多壓力方案比較 CLI
用法: python scripts/compare_scenarios.py \
        --equipment "分離式 2HP" --width 900 --height 200 \
        --contamination grease_light \
        --pressure-range "1.5,2.0,3.0,4.0,6.0,8.0"
"""
import argparse
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fluidsim_skills.cleaning import design_cleaning_system
from fluidsim_skills.droplet import spray_droplet_size
from fluidsim_skills.chemistry import recommend_cleaner, CONTAMINATION_DB

EQUIPMENT_PRESETS = {
    'split-0.75hp': (600, 160),
    'split-1hp':    (700, 170),
    'split-1.5hp':  (800, 180),
    'split-2hp':    (900, 200),
    'split-2.5hp':  (1000, 200),
    'split-3hp':    (1100, 220),
}


def main():
    parser = argparse.ArgumentParser(description='多壓力方案比較')
    parser.add_argument('--equipment', type=str, default='冷氣蒸發器')
    parser.add_argument('--type', type=str, default=None, choices=list(EQUIPMENT_PRESETS.keys()))
    parser.add_argument('--width', type=float, default=None)
    parser.add_argument('--height', type=float, default=None)
    parser.add_argument('--contamination', type=str, default='grease_light',
                        choices=list(CONTAMINATION_DB.keys()))
    parser.add_argument('--fin-material', type=str, default='aluminum')
    parser.add_argument('--pressure-range', type=str, default='1.5,2.0,3.0,4.0,6.0,8.0',
                        help='逗號分隔的壓力值列表 (bar)')
    parser.add_argument('--fin-spacing', type=float, default=1.5)
    args = parser.parse_args()

    width, height = args.width, args.height
    if (width is None or height is None) and args.type in EQUIPMENT_PRESETS:
        w, h = EQUIPMENT_PRESETS[args.type]
        width = width or w
        height = height or h
    width = width or 800
    height = height or 180

    pressures = [float(p.strip()) for p in args.pressure_range.split(',')]

    # 化學方案（與壓力無關，計算一次）
    chem = recommend_cleaner(
        contamination_key=args.contamination,
        fin_material=args.fin_material,
        fin_spacing_mm=args.fin_spacing,
    )

    cont_name = CONTAMINATION_DB[args.contamination]['name']

    print(f"\n多壓力方案比較：{args.equipment}")
    print(f"污垢：{cont_name}　　翅片：{width:.0f}×{height:.0f} mm")
    print(f"清潔劑：{chem.recommended_cleaner} {chem.concentration_pct:.1f}%")
    print()

    # 表頭
    col = '{:>8}'
    header = (
        f"{'壓力(bar)':>10} "
        f"{'噴嘴壓(bar)':>12} "
        f"{'孔徑(mm)':>10} "
        f"{'流量(L/min)':>12} "
        f"{'衝擊(kPa)':>10} "
        f"{'SMD(μm)':>9} "
        f"{'用水(L)':>8} "
        f"{'時間(min)':>10} "
        f"{'翅片安全':>8}"
    )
    print(header)
    print('─' * len(header))

    for p in pressures:
        try:
            r = design_cleaning_system(
                equipment_name=args.equipment,
                evaporator_width_mm=width,
                evaporator_height_mm=height,
                supply_pressure_bar=p,
            )
            smd = spray_droplet_size(
                pressure_bar=r.nozzle_pressure_bar,
                orifice_diameter_mm=r.nozzle.orifice_diameter_mm,
                surface_tension_mN=chem.surface_tension_mN,
            )
            # 翅片安全評估
            kpa = r.nozzle.impact_pressure_kpa
            if kpa > 50:
                safety = '⚠ 超限'
            elif kpa > 20:
                safety = '✓ 佳'
            elif kpa > 10:
                safety = '✓ 可'
            else:
                safety = '→ 偏低'

            print(
                f"{p:>10.1f} "
                f"{r.nozzle_pressure_bar:>12.2f} "
                f"{r.nozzle.orifice_diameter_mm:>10.1f} "
                f"{r.nozzle.flowrate_lpm:>12.2f} "
                f"{kpa:>10.1f} "
                f"{smd:>9.0f} "
                f"{r.water_used_L:>8.1f} "
                f"{r.estimated_cleaning_time_min:>10.0f} "
                f"{safety:>8}"
            )
        except Exception as e:
            print(f"{p:>10.1f}  {'ERROR: ' + str(e)}")

    print()
    print(f"建議清潔劑：{chem.recommended_cleaner}，濃度 {chem.concentration_pct:.1f}%，"
          f"靜置 {chem.contact_time_min:.0f} 分鐘，預期溶解效率 {chem.dissolved_fraction*100:.0f}%")
    print(f"翅片安全衝擊上限：鋁翅片 50 kPa / 銅翅片 100 kPa")


if __name__ == '__main__':
    main()
