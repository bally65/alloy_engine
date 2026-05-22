"""
化學清潔 + 物理清潔整合報告
用法: python scripts/full_chem_report.py --contamination grease_light --supply 3.0 --width 750 --height 200
"""
import argparse
import sys
import os
from datetime import date
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fluidsim_skills.chemistry import recommend_cleaner, CONTAMINATION_DB
from fluidsim_skills.cleaning import design_cleaning_system


def main():
    parser = argparse.ArgumentParser(description='化學+物理清潔整合設計報告')
    parser.add_argument('--equipment', type=str, default='冷氣蒸發器', help='設備名稱')
    parser.add_argument('--contamination', type=str, required=True,
                        choices=list(CONTAMINATION_DB.keys()), help='污垢類型')
    parser.add_argument('--fin-material', type=str, default='aluminum',
                        choices=['aluminum', 'copper'])
    parser.add_argument('--supply', type=float, required=True, help='水源壓力 bar')
    parser.add_argument('--width', type=float, default=800, help='蒸發器寬度 mm')
    parser.add_argument('--height', type=float, default=180, help='蒸發器高度 mm')
    parser.add_argument('--fin-spacing', type=float, default=1.2, help='翅片間距 mm')
    parser.add_argument('--output', type=str, default=None, help='輸出 markdown 檔案')
    args = parser.parse_args()

    chem = recommend_cleaner(
        contamination_key=args.contamination,
        fin_material=args.fin_material,
        fin_spacing_mm=args.fin_spacing,
    )
    phys = design_cleaning_system(
        equipment_name=args.equipment,
        evaporator_width_mm=args.width,
        evaporator_height_mm=args.height,
        supply_pressure_bar=args.supply,
    )

    eff_icon = {'優': '★★★★', '良': '★★★☆', '可': '★★☆☆', '差': '★☆☆☆'}

    lines = [
        f"# 冷氣清潔完整設計報告（化學 + 物理）",
        f"",
        f"**設備**：{args.equipment}　**日期**：{date.today()}",
        f"",
        f"---",
        f"",
        f"## 一、污垢分析",
        f"",
        f"| 項目 | 說明 |",
        f"|------|------|",
        f"| 污垢類型 | {chem.contamination} |",
        f"| 翅片材質 | {'鋁翅片' if args.fin_material=='aluminum' else '銅翅片'} |",
        f"| 翅片間距 | {args.fin_spacing} mm |",
        f"",
        f"## 二、化學清潔方案",
        f"",
        f"| 項目 | 數值 |",
        f"|------|------|",
        f"| 推薦清潔劑 | {chem.recommended_cleaner} |",
        f"| 使用濃度 | {chem.concentration_pct:.1f}% (v/v) |",
        f"| 接觸時間 | {chem.contact_time_min:.0f} 分鐘 |",
        f"| 預期溶解效果 | {chem.combined_effectiveness} {eff_icon.get(chem.combined_effectiveness,'')} ({chem.dissolved_fraction*100:.1f}%) |",
        f"| 清潔液表面張力 | {chem.surface_tension_mN:.1f} mN/m |",
        f"| 翅片接觸角 | {chem.contact_angle_deg:.1f}° |",
        f"",
        f"## 三、物理清潔方案（水壓沖洗）",
        f"",
        f"| 項目 | 數值 |",
        f"|------|------|",
        f"| 水源壓力 | {phys.supply_pressure_bar:.1f} bar |",
        f"| 噴嘴前壓力 | {phys.nozzle_pressure_bar:.2f} bar |",
        f"| 推薦噴嘴孔徑 | {phys.nozzle.orifice_diameter_mm:.1f} mm |",
        f"| 操作流量 | {phys.nozzle.flowrate_lpm:.2f} L/min |",
        f"| 翅片衝擊力 | {phys.nozzle.impact_force_N:.2f} N |",
        f"| 翅片衝擊壓力 | {phys.nozzle.impact_pressure_kpa:.1f} kPa |",
        f"",
        f"## 四、完整清潔作業程序",
        f"",
        f"**階段一：施藥**",
    ]
    for step in chem.procedure[:3]:
        lines.append(f"{step}")
    lines += [
        f"",
        f"**階段二：水洗**",
    ]
    for step in phys.procedure[2:]:
        lines.append(f"{step}")
    lines.append("")

    all_warnings = chem.warnings + phys.warnings
    if all_warnings:
        lines += ["## 五、注意事項", ""]
        for w in all_warnings:
            lines.append(f"- ⚠ {w}")
        lines.append("")

    if chem.alternatives:
        lines += ["## 六、替代清潔劑", ""]
        for alt in chem.alternatives:
            lines.append(f"- {alt}")
        lines.append("")

    lines += [
        "---",
        f"*由 alloy_engine/skills/chem_cleaning 自動生成*",
    ]

    report_text = "\n".join(lines)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(report_text)
        print(f"報告已儲存至: {args.output}")
    else:
        print(report_text)


if __name__ == '__main__':
    main()
