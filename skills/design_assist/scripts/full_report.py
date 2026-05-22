"""
完整 HVAC 清潔設計報告生成 CLI
用法: python scripts/full_report.py --equipment "日立RAS-28NK" --width 750 --height 200 --supply-pressure 3.0
"""
import argparse
import sys
import os
from datetime import date
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fluidsim_skills.cleaning import design_cleaning_system
from fluidsim_skills.fluid import flowrate_to_velocity, reynolds_number, flow_regime, water_properties

# 常見冷氣蒸發器尺寸預設值（mm）
EQUIPMENT_PRESETS = {
    'split-0.75hp': (600, 160),
    'split-1hp':    (700, 170),
    'split-1.5hp':  (800, 180),
    'split-2hp':    (900, 200),
    'split-2.5hp':  (1000, 200),
    'split-3hp':    (1100, 220),
    'window-1hp':   (550, 200),
    'window-1.5hp': (650, 220),
}


def generate_report(args) -> str:
    width = args.width
    height = args.height
    if (width is None or height is None) and args.type in EQUIPMENT_PRESETS:
        width, height = EQUIPMENT_PRESETS[args.type]
    if width is None or height is None:
        width, height = 800, 180  # 預設值

    report = design_cleaning_system(
        equipment_name=args.equipment,
        evaporator_width_mm=width,
        evaporator_height_mm=height,
        supply_pressure_bar=args.supply_pressure,
        pipe_diameter_mm=args.pipe_d,
        pipe_length_m=args.pipe_length,
        target_distance_mm=args.distance,
    )

    # 管道流態分析
    props = water_properties(20)
    v = flowrate_to_velocity(report.nozzle.flowrate_lpm, args.pipe_d / 1000)
    Re = reynolds_number(args.pipe_d / 1000, v, props.kinematic_viscosity)
    regime = {'laminar': '層流', 'transitional': '過渡流', 'turbulent': '紊流'}.get(flow_regime(Re), '')

    lines = [
        f"# 冷氣清潔系統設計報告",
        f"",
        f"**設備**：{report.equipment}",
        f"**設計日期**：{date.today()}",
        f"",
        f"---",
        f"",
        f"## 系統概述",
        f"",
        f"| 項目 | 數值 |",
        f"|------|------|",
        f"| 水源壓力 | {report.supply_pressure_bar:.1f} bar |",
        f"| 管路壓損 | {report.pipe_loss_bar:.3f} bar |",
        f"| 噴嘴前壓力 | {report.nozzle_pressure_bar:.2f} bar |",
        f"| 推薦噴嘴孔徑 | {report.nozzle.orifice_diameter_mm:.1f} mm |",
        f"| 操作流量 | {report.nozzle.flowrate_lpm:.2f} L/min |",
        f"| 噴出流速 | {report.nozzle.exit_velocity:.1f} m/s |",
        f"| 衝擊力 | {report.nozzle.impact_force_N:.2f} N |",
        f"| 衝擊壓力 | {report.nozzle.impact_pressure_kpa:.1f} kPa |",
        f"| 覆蓋寬度 | {report.nozzle.coverage_width_mm:.0f} mm |",
        f"| 預計清潔時間 | {report.estimated_cleaning_time_min:.0f} 分鐘 |",
        f"",
        f"## 流態分析",
        f"",
        f"清潔管路（{args.pipe_d:.1f}mm 內徑）在操作流量下：",
        f"- 管道流速：{v:.3f} m/s",
        f"- 雷諾數：{Re:.0f}（{regime}）",
        f"",
        f"## 清潔作業程序",
        f"",
    ]
    for step in report.procedure:
        lines.append(f"{step}")
    lines.append("")

    if report.warnings:
        lines += ["## 注意事項", ""]
        for w in report.warnings:
            lines.append(f"- ⚠ {w}")
        lines.append("")

    lines += [
        "## 設備清單建議",
        "",
        f"- 噴嘴：孔徑 {report.nozzle.orifice_diameter_mm:.1f}mm，噴霧角 {report.nozzle.spray_angle_deg:.0f}°",
        f"- 水管：內徑 {args.pipe_d:.1f}mm，長度 ≤ {args.pipe_length:.0f}m",
        "- 防水布/集水盤",
        "- 個人防護：護目鏡、防水手套",
        "",
        "---",
        f"*本報告由 alloy_engine/skills/design_assist 自動生成*",
    ]

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description='生成完整冷氣清潔設計報告')
    parser.add_argument('--equipment', type=str, required=True, help='設備名稱/型號')
    parser.add_argument('--type', type=str, default='split-1.5hp',
                        choices=list(EQUIPMENT_PRESETS.keys()),
                        help='設備類型（自動填入尺寸）')
    parser.add_argument('--width', type=float, default=None, help='蒸發器寬度 mm（可選，覆蓋型號預設）')
    parser.add_argument('--height', type=float, default=None, help='蒸發器高度 mm（可選，覆蓋型號預設）')
    parser.add_argument('--supply-pressure', type=float, required=True, help='水源壓力 bar')
    parser.add_argument('--pipe-d', type=float, default=9.5, help='管路內徑 mm')
    parser.add_argument('--pipe-length', type=float, default=3.0, help='管路長度 m')
    parser.add_argument('--distance', type=float, default=150.0, help='噴嘴到翅片距離 mm')
    parser.add_argument('--output', type=str, default=None, help='輸出 markdown 檔案路徑')
    args = parser.parse_args()

    report_text = generate_report(args)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(report_text)
        print(f"報告已儲存至: {args.output}")
    else:
        print(report_text)


if __name__ == '__main__':
    main()
