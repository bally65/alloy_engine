"""
冷氣清潔全域決策報告
整合所有物理模組：流體力學、化學溶解、毛細滲透、翅片熱效率、液滴動力學、積垢預測

用法:
  python scripts/comprehensive_report.py \\
    --equipment "日立 RAS-28NK" --type split-2hp \\
    --contamination grease_light --supply 3.0 \\
    --elapsed-hours 2000 --output report.md
"""
import argparse
import sys
import os
from datetime import date
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fluidsim_skills.cleaning import design_cleaning_system
from fluidsim_skills.chemistry import recommend_cleaner, corrosion_risk, rinse_analysis, CONTAMINATION_DB
from fluidsim_skills.capillary import analyse_fin_penetration
from fluidsim_skills.thermal import fin_efficiency_from_kappa
from fluidsim_skills.droplet import spray_droplet_size, weber_number, droplet_regime
from fluidsim_skills.fouling import analyse_fouling, fouling_penalty, FOULING_RESISTANCE_DB
from fluidsim_skills.airflow import analyse_airflow
from fluidsim_skills.roi import energy_roi
from fluidsim_skills.fluid import flowrate_to_velocity, reynolds_number, flow_regime, water_properties

EQUIPMENT_PRESETS = {
    'split-0.75hp': (600, 160, 1.5),
    'split-1hp':    (700, 170, 1.5),
    'split-1.5hp':  (800, 180, 1.5),
    'split-2hp':    (900, 200, 1.5),
    'split-2.5hp':  (1000, 200, 1.5),
    'split-3hp':    (1100, 220, 1.5),
    'window-1hp':   (550, 200, 1.2),
    'window-1.5hp': (650, 220, 1.2),
}

_STATUS = {True: '✓ 是', False: '✗ 否'}


def _bar(value: float, max_val: float, width: int = 16) -> str:
    filled = int(round(value / max_val * width))
    filled = max(0, min(width, filled))
    return '█' * filled + '░' * (width - filled)


def generate_report(args) -> str:
    # ── 尺寸解析 ──────────────────────────────────────────────────────────────
    width, height, fin_spacing = args.width, args.height, args.fin_spacing
    if (width is None or height is None) and args.type in EQUIPMENT_PRESETS:
        w, h, s = EQUIPMENT_PRESETS[args.type]
        width = width or w
        height = height or h
        fin_spacing = fin_spacing or s
    width = width or 800
    height = height or 180
    fin_spacing = fin_spacing or 1.5

    # ── 模組計算 ───────────────────────────────────────────────────────────────
    # 1. 物理清潔（噴嘴 + 管路）
    phys = design_cleaning_system(
        equipment_name=args.equipment,
        evaporator_width_mm=width,
        evaporator_height_mm=height,
        supply_pressure_bar=args.supply,
    )

    # 2. 化學清潔（清潔劑推薦 + 溶解動力學）
    chem = recommend_cleaner(
        contamination_key=args.contamination,
        fin_material=args.fin_material,
        fin_spacing_mm=fin_spacing,
    )

    # 3. 毛細滲透
    cap = analyse_fin_penetration(
        fin_spacing_mm=fin_spacing,
        fin_height_mm=args.fin_height,
        surface_tension_mN=chem.surface_tension_mN,
        contact_angle_deg=chem.contact_angle_deg,
        dynamic_viscosity=1.0e-3,
        cleaner_name=chem.recommended_cleaner,
    )

    # 4. 翅片熱效率
    kappa = 237.0 if args.fin_material == 'aluminum' else 385.0
    if args.kappa:
        kappa = args.kappa
    therm = fin_efficiency_from_kappa(
        fin_height_mm=args.fin_height,
        fin_thickness_mm=args.fin_thickness,
        kappa_W_mK=kappa,
    )

    # 5. 液滴品質
    smd = spray_droplet_size(
        pressure_bar=phys.nozzle_pressure_bar,
        orifice_diameter_mm=phys.nozzle.orifice_diameter_mm,
        surface_tension_mN=chem.surface_tension_mN,
    )
    We = weber_number(
        velocity=phys.nozzle.exit_velocity,
        diameter_m=smd * 1e-9,   # 以 SMD 作為代表液滴徑（nm→m）
        density=998.2,
        surface_tension_Nm=chem.surface_tension_mN * 1e-3,
    )
    drop_regime = droplet_regime(We, 0.01)

    # 6. 腐蝕風險（由 ChemCleaningReport 的名稱反查清潔劑 key）
    from fluidsim_skills.chemistry import CLEANER_DB as _CDB
    _cleaner_key = next(
        (k for k, v in _CDB.items() if v['name'] == chem.recommended_cleaner),
        'alkaline_mild',
    )
    corr = corrosion_risk(
        cleaner_key=_cleaner_key,
        fin_material=args.fin_material,
        contact_time_min=chem.contact_time_min,
    )

    # 7. 積垢分析
    foul = analyse_fouling(
        elapsed_hours=args.elapsed_hours,
        environment=args.environment,
        U_clean=args.U_clean,
        target_loss_pct=args.target_loss,
    )
    max_pen = fouling_penalty(FOULING_RESISTANCE_DB[args.environment]['Rf_star'], args.U_clean)

    # 8. 空氣側壓降
    _deposit_map = {
        'ac_indoor_unit': 'dust', 'ac_outdoor_unit': 'dust',
        'city_water': 'scale', 'coastal_air': 'dust',
        'industrial_air': 'grease', 'kitchen_exhaust': 'grease',
    }
    fin_type = getattr(args, 'fin_type', 'plain')
    air = analyse_airflow(
        face_velocity_ms=args.face_velocity,
        fin_pitch_mm=fin_spacing,
        fin_height_mm=args.fin_height,
        fin_thickness_mm=args.fin_thickness,
        Rf_current=foul.current_Rf,
        deposit_type=_deposit_map.get(args.environment, 'dust'),
        fin_type=fin_type,
    )

    # 9. 沖洗分析
    from fluidsim_skills.chemistry import CLEANER_DB as _CDB2
    _cleaner_data = _CDB2.get(_cleaner_key, {})
    _cleaner_ph = _cleaner_data.get('ph', 9.0)
    rinse = rinse_analysis(
        cleaner_ph=_cleaner_ph,
        cleaner_volume_L=phys.water_used_L * 0.3,   # 施藥量約清洗用水 30%
        rounds=3,
    )

    # 10. 能源 ROI
    rated_power = getattr(args, 'rated_power_kw', 0.75)
    cleaning_cost_val = getattr(args, 'cleaning_cost', 1500.0)
    roi = energy_roi(
        rated_power_kw=rated_power,
        power_increase_pct=air.power_increase_pct,
        cleaning_cost=float(cleaning_cost_val),
    )

    # 管道流態
    props = water_properties(20)
    v_pipe = flowrate_to_velocity(phys.nozzle.flowrate_lpm, args.pipe_d / 1000)
    Re_pipe = reynolds_number(args.pipe_d / 1000, v_pipe, props.kinematic_viscosity)
    regime_zh = {'laminar': '層流', 'transitional': '過渡流', 'turbulent': '紊流'}
    regime_str = regime_zh.get(flow_regime(Re_pipe), '')

    cont_info = CONTAMINATION_DB[args.contamination]
    cont_name = cont_info.get('name', args.contamination)
    eff_pct = chem.dissolved_fraction * 100

    # ── 報告文字 ───────────────────────────────────────────────────────────────
    L = []
    def s(*args_):
        L.append(' '.join(str(a) for a in args_))

    s(f"# 冷氣清潔全域決策報告")
    s(f"")
    s(f"**設備**：{args.equipment}　　**日期**：{date.today()}")
    s(f"")
    s(f"---")
    s(f"")
    s(f"## 摘要")
    s(f"")
    s(f"| 評估項目 | 結果 | 建議 |")
    s(f"|---------|------|------|")
    s(f"| 物理清潔可行性 | 噴嘴壓力 {phys.nozzle_pressure_bar:.2f} bar | "
      f"{'✓ 充足' if phys.nozzle_pressure_bar >= 1.5 else '⚠ 壓力偏低'} |")
    s(f"| 清潔劑 | {chem.recommended_cleaner} | 濃度 {chem.concentration_pct:.1f}%，接觸 {chem.contact_time_min:.0f} 分鐘 |")
    def _fmt_time(t: float) -> str:
        if t <= 0:
            return '—'
        if t < 1:
            return '< 1 秒'
        if t < 60:
            return f'{t:.0f} 秒'
        return f'{t/60:.1f} 分鐘'

    s(f"| 毛細滲透 | {'可自發滲入' if cap.capillary_pressure_pa > 0 else '需加壓滲入'} | "
      f"{'靜置 ' + _fmt_time(cap.time_to_full_penetration_s) + ' 可達底部'} |")
    s(f"| 翅片效率 | η = {therm.fin_efficiency:.1%} | "
      f"{'優秀' if therm.fin_efficiency > 0.95 else '良好' if therm.fin_efficiency > 0.85 else '可接受'} |")
    s(f"| 噴霧 SMD | {smd:.0f} μm | "
      f"{'翅片穿透佳' if 100 <= smd <= 400 else '建議調整壓力/孔徑'} |")
    s(f"| 積垢狀態 | 效率損失 {foul.efficiency_penalty_pct:.2f}% | "
      f"{'立即清潔' if foul.efficiency_penalty_pct >= args.target_loss else '正常'} |")
    s(f"| 氣流衰退 | 壓降增 {air.pressure_increase_pct:.1f}%，風量減 {air.airflow_reduction_pct:.1f}% | "
      f"{'⚠ 顯著' if air.airflow_reduction_pct > 5 else '✓ 輕微'} |")
    risk_icon = {'safe': '✓ 安全', 'low': '→ 低風險', 'medium': '⚠ 中風險', 'high': '⚠ 高風險'}
    s(f"| 腐蝕風險 | pH {corr.ph:.1f}，接觸 {corr.contact_time_min:.0f} min | "
      f"{risk_icon.get(corr.risk_level, corr.risk_level)} |")
    pb = roi.payback_months
    s(f"| 清潔 ROI | 年節省 {roi.annual_extra_kwh:.0f} kWh / {roi.annual_extra_cost:.0f} 元 | "
      f"{'< 1 月回收' if pb < 1 else f'{pb:.1f} 月回收'} |")
    s(f"| 沖洗合規 | 出水 pH ≈ {rinse.estimated_final_ph:.1f} | "
      f"{'✓ 符合排放標準' if rinse.compliant else '⚠ 需增加沖洗量'} |")
    s(f"")

    # ── 一、設備規格 ─────────────────────────────────────────────────────────
    s(f"---")
    s(f"")
    s(f"## 一、設備與清潔條件")
    s(f"")
    s(f"| 項目 | 數值 |")
    s(f"|------|------|")
    s(f"| 設備型號 | {args.equipment} |")
    s(f"| 翅片尺寸 | {width:.0f}×{height:.0f} mm，間距 {fin_spacing:.1f} mm |")
    s(f"| 翅片高度 | {args.fin_height:.0f} mm，厚度 {args.fin_thickness:.2f} mm |")
    s(f"| 材質 κ | {kappa:.0f} W/m·K ({'鋁' if kappa < 300 else '銅'}翅片) |")
    s(f"| 水源壓力 | {args.supply:.1f} bar |")
    s(f"| 污垢類型 | {args.contamination}（{cont_name}）|")
    s(f"")

    # ── 二、液壓設計 ─────────────────────────────────────────────────────────
    s(f"---")
    s(f"")
    s(f"## 二、液壓設計（Darcy-Weisbach + Torricelli）")
    s(f"")
    s(f"| 項目 | 數值 |")
    s(f"|------|------|")
    s(f"| 管路壓損 | {phys.pipe_loss_bar:.3f} bar |")
    s(f"| 噴嘴前壓力 | **{phys.nozzle_pressure_bar:.2f} bar** |")
    s(f"| 推薦孔徑 | {phys.nozzle.orifice_diameter_mm:.1f} mm |")
    s(f"| 操作流量 | {phys.nozzle.flowrate_lpm:.2f} L/min |")
    s(f"| 噴出流速 | {phys.nozzle.exit_velocity:.1f} m/s |")
    s(f"| 衝擊壓力 | {phys.nozzle.impact_pressure_kpa:.1f} kPa |")
    s(f"| 覆蓋寬度 | {phys.nozzle.coverage_width_mm:.0f} mm @ {150:.0f}mm |")
    s(f"| 管道流態 | Re={Re_pipe:.0f}（{regime_str}）|")
    s(f"| 預計清潔時間 | {phys.estimated_cleaning_time_min:.0f} 分鐘 |")
    s(f"| 預估用水量 | {phys.water_used_L:.1f} L |")
    s(f"")

    # ── 三、化學清潔 ─────────────────────────────────────────────────────────
    s(f"---")
    s(f"")
    s(f"## 三、化學清潔方案（Noyes-Whitney 溶解動力學）")
    s(f"")
    s(f"**推薦清潔劑**：{chem.recommended_cleaner}　**濃度**：{chem.concentration_pct:.1f}%　"
      f"**接觸時間**：{chem.contact_time_min:.0f} 分鐘")
    s(f"")
    s(f"| 項目 | 數值 |")
    s(f"|------|------|")
    s(f"| 表面張力 | {chem.surface_tension_mN:.1f} mN/m |")
    s(f"| 接觸角（翅片） | {chem.contact_angle_deg:.1f}° |")
    s(f"| 溶解效率 | {eff_pct:.1f}% {_bar(eff_pct, 100)} |")
    s(f"| 綜合效果 | {chem.combined_effectiveness} |")
    s(f"")
    s(f"| 腐蝕風險 | **{risk_icon.get(corr.risk_level, corr.risk_level)}** |")
    s(f"")
    if corr.risk_level in ('medium', 'high'):
        s(f"> ⚠ {corr.recommendation}")
        s(f"")
    if chem.alternatives:
        s(f"替代方案：" + "、".join(chem.alternatives))
        s(f"")

    # ── 四、毛細滲透 ─────────────────────────────────────────────────────────
    s(f"---")
    s(f"")
    s(f"## 四、毛細滲透分析（Laplace-Young + Lucas-Washburn）")
    s(f"")
    s(f"翅片間距 **{fin_spacing:.1f} mm**，清潔液需滲透翅片全深 **{args.fin_height:.0f} mm**。")
    s(f"")
    s(f"| 項目 | 數值 |")
    s(f"|------|------|")
    s(f"| 毛細壓力 | {cap.capillary_pressure_pa:+.1f} Pa |")
    s(f"| 可自發滲入 | {_STATUS[cap.capillary_pressure_pa > 0]} |")
    if cap.time_to_full_penetration_s > 0:
        s(f"| 滲透至底部 | {_fmt_time(cap.time_to_full_penetration_s)} |")
        s(f"| 滲透至 1/2 深 | {_fmt_time(cap.time_to_half_penetration_s)} |")
    s(f"| 對比純水 | {cap.vs_water} |")
    s(f"")
    s(f"> {cap.recommendation}")
    s(f"")

    # ── 五、翅片熱效率 ───────────────────────────────────────────────────────
    s(f"---")
    s(f"")
    s(f"## 五、翅片熱效率（η = tanh(mL)/(mL)）")
    s(f"")
    s(f"| 項目 | 數值 |")
    s(f"|------|------|")
    s(f"| 翅片參數 m | {therm.m_parameter:.1f} m⁻¹ |")
    s(f"| 翅片效率 η | **{therm.fin_efficiency:.1%}** {_bar(therm.fin_efficiency, 1.0)} |")
    s(f"| 對比標準鋁 | {therm.heat_transfer_improvement} |")
    for note in therm.notes:
        s(f"| 備註 | {note} |")
    s(f"")

    # ── 六、液滴動力學 ───────────────────────────────────────────────────────
    s(f"---")
    s(f"")
    s(f"## 六、噴霧液滴品質（Weber 數 + SMD）")
    s(f"")
    s(f"| 項目 | 數值 |")
    s(f"|------|------|")
    s(f"| 噴嘴出口流速 | {phys.nozzle.exit_velocity:.1f} m/s |")
    s(f"| SMD（索特平均直徑） | **{smd:.0f} μm** |")
    regimes_zh = {
        'intact': '完整液滴（不破碎）',
        'stretching_breakup': '袋式破碎（細霧）',
        'catastrophic_breakup': '劇烈霧化（微細）',
    }
    s(f"| 翅片表面破碎模式 | {regimes_zh.get(drop_regime, drop_regime)} |")
    if 100 <= smd <= 400:
        smd_eval = "最佳範圍（翅片縫隙穿透力佳）"
    elif smd < 100:
        smd_eval = "過細，飄散損失大"
    else:
        smd_eval = "偏大，建議提高壓力或縮小孔徑"
    s(f"| SMD 評估 | {smd_eval} |")
    s(f"")

    # ── 七、空氣側壓降 ───────────────────────────────────────────────────────
    s(f"---")
    s(f"")
    fin_type_zh = {'plain': '平直翅片', 'wavy': '波浪翅片', 'louvered': '百葉翅片'}
    s(f"## 七、空氣側壓降與風量衰退（矩形通道 Hagen-Poiseuille）")
    s(f"")
    s(f"翅片幾何：**{fin_type_zh.get(fin_type, fin_type)}**，面風速 **{args.face_velocity:.1f} m/s**，"
      f"翅片間距 **{fin_spacing:.1f} mm**，Re={air.reynolds_number:.0f}")
    s(f"")
    s(f"| 項目 | 乾淨翅片 | 積垢後 | 影響 |")
    s(f"|------|---------|--------|------|")
    s(f"| 積垢層厚度 | 0 μm | {air.fouling_layer_um:.1f} μm/側 | — |")
    s(f"| 有效間隙 | {fin_spacing - args.fin_thickness:.2f} mm | {air.effective_gap_mm:.3f} mm | "
      f"縮小 {(1-air.effective_gap_mm/(fin_spacing-args.fin_thickness))*100:.1f}% |")
    s(f"| 空氣側壓降 | {air.pressure_drop_clean_pa:.2f} Pa | {air.pressure_drop_fouled_pa:.2f} Pa | "
      f"+{air.pressure_increase_pct:.1f}% |")
    s(f"| 風量衰退 | 0% | **{air.airflow_reduction_pct:.1f}%** | 同等風機壓力 |")
    s(f"| 額外風機功率 | 0% | {air.power_increase_pct:.1f}% | 維持原風量 |")
    s(f"")
    s(f"> {air.recommendation}")
    s(f"")

    # ── 八、沖洗合規 ─────────────────────────────────────────────────────────
    s(f"---")
    s(f"")
    s(f"## 八、沖洗廢水合規分析")
    s(f"")
    s(f"清潔劑 pH **{rinse.cleaner_ph:.1f}**，施藥量 **{rinse.cleaner_volume_L:.1f} L**，"
      f"排放標準 pH {rinse.estimated_final_ph:.1f}（目標 6–9）")
    s(f"")
    s(f"| 項目 | 數值 |")
    s(f"|------|------|")
    s(f"| 需稀釋倍數 | {rinse.dilution_factor:.0f}× |")
    s(f"| 總沖洗水量 | **{rinse.total_rinse_L:.1f} L** |")
    s(f"| 建議沖洗輪數 | {rinse.rounds} 輪 × {rinse.volume_per_round_L:.1f} L/輪 |")
    s(f"| 出水 pH 預估 | {rinse.estimated_final_ph:.1f} |")
    s(f"| 排放合規 | {'✓ 符合（pH 6–9）' if rinse.compliant else '⚠ 不符合，增加沖洗量'} |")
    s(f"")
    s(f"> {rinse.recommendation}")
    s(f"")

    # ── 九、ROI ──────────────────────────────────────────────────────────────
    s(f"---")
    s(f"")
    s(f"## 九、能源節約與清潔投資回報（ROI）")
    s(f"")
    s(f"額定功率 **{roi.rated_power_kw:.2f} kW**，積垢功耗增幅 **{roi.power_increase_pct:.1f}%**，"
      f"年使用 **{roi.annual_hours:.0f} h**")
    s(f"")
    s(f"| 項目 | 數值 |")
    s(f"|------|------|")
    s(f"| 積垢每年多耗電 | {roi.annual_extra_kwh:.1f} kWh |")
    s(f"| 積垢每年多花費 | {roi.annual_extra_cost:.0f} 元 |")
    s(f"| 清潔費用 | {roi.cleaning_cost:.0f} 元 |")
    pb_str = f"{roi.payback_months:.1f} 個月" if roi.payback_months < 120 else "效益不顯著"
    s(f"| 費用回收期 | **{pb_str}** |")
    s(f"| CO₂ 減排量 | {roi.co2_reduction_kg:.1f} kg/年 |")
    s(f"")
    s(f"> {roi.recommendation}")
    s(f"")

    # ── 十、積垢分析 ─────────────────────────────────────────────────────────
    s(f"---")
    s(f"")
    s(f"## 十、積垢狀態分析（Kern-Seaton + TEMA）")
    s(f"")
    env_info = FOULING_RESISTANCE_DB[args.environment]
    s(f"環境：**{env_info['description']}**　　已運行：**{args.elapsed_hours:.0f} 小時**")
    s(f"")
    s(f"| 項目 | 數值 |")
    s(f"|------|------|")
    s(f"| 當前積垢熱阻 | {foul.current_Rf:.3e} m²·K/W |")
    s(f"| 漸近積垢熱阻 | {foul.asymptotic_Rf:.3e} m²·K/W |")
    s(f"| 積垢飽和度 | {foul.current_Rf/foul.asymptotic_Rf*100:.1f}% |")
    s(f"| 效率損失 | **{foul.efficiency_penalty_pct:.2f}%** {_bar(foul.efficiency_penalty_pct, args.target_loss * 2)} |")
    s(f"| 漸近最大損失 | {max_pen:.2f}%（此環境上限）|")
    if foul.time_to_threshold_h > 0:
        s(f"| 距清潔門檻 | {foul.time_to_threshold_h:.0f} 小時 |")
    s(f"")
    s(f"> {foul.recommendation}")
    s(f"")

    # ── 十一、完整作業程序 ───────────────────────────────────────────────────
    s(f"---")
    s(f"")
    s(f"## 十一、完整清潔作業程序")
    s(f"")
    s(f"### 階段一：施藥（化學清潔）")
    s(f"")
    for step in chem.procedure:
        s(step)
    s(f"")
    s(f"### 階段二：水洗（物理清潔）")
    s(f"")
    for step in phys.procedure:
        s(step)
    s(f"")

    all_warnings = chem.warnings + phys.warnings
    if all_warnings:
        s(f"### 注意事項")
        s(f"")
        for w in all_warnings:
            s(f"- ⚠ {w}")
        s(f"")

    s(f"---")
    s(f"*本報告由 alloy_engine/skills 全模組自動生成 — "
      f"流體力學 + 化學溶解 + 毛細 + 熱效率 + 液滴 + 積垢*")

    return "\n".join(L)


def main():
    parser = argparse.ArgumentParser(description='冷氣清潔全域決策報告（整合所有物理模組）')
    parser.add_argument('--equipment', type=str, default='分離式冷氣', help='設備名稱/型號')
    parser.add_argument('--type', type=str, default='split-1.5hp',
                        choices=list(EQUIPMENT_PRESETS.keys()))
    parser.add_argument('--width', type=float, default=None, help='蒸發器寬度 mm')
    parser.add_argument('--height', type=float, default=None, help='蒸發器高度 mm')
    parser.add_argument('--supply', type=float, required=True, help='水源壓力 bar')
    parser.add_argument('--contamination', type=str, default='grease_light',
                        choices=list(CONTAMINATION_DB.keys()))
    parser.add_argument('--fin-material', type=str, default='aluminum',
                        choices=['aluminum', 'copper'])
    parser.add_argument('--fin-spacing', type=float, default=None, help='翅片間距 mm')
    parser.add_argument('--fin-height', type=float, default=15.0, help='翅片高度 mm')
    parser.add_argument('--fin-thickness', type=float, default=0.1, help='翅片厚度 mm')
    parser.add_argument('--kappa', type=float, default=None, help='翅片 κ (W/m·K)，預設按材質自動選擇')
    parser.add_argument('--elapsed-hours', type=float, default=1000.0, help='上次清潔後運行時數 h')
    parser.add_argument('--environment', type=str, default='ac_indoor_unit',
                        choices=list(FOULING_RESISTANCE_DB.keys()))
    parser.add_argument('--U-clean', type=float, default=50.0, help='乾淨換熱係數 W/m²·K')
    parser.add_argument('--target-loss', type=float, default=10.0, help='清潔門檻效率損失 %')
    parser.add_argument('--pipe-d', type=float, default=9.5, help='管路內徑 mm')
    parser.add_argument('--face-velocity', type=float, default=1.5, help='蒸發器面風速 (m/s)')
    parser.add_argument('--fin-type', type=str, default='plain',
                        choices=['plain', 'wavy', 'louvered'], help='翅片幾何類型')
    parser.add_argument('--rated-power', type=float, default=0.75, help='設備額定功率 kW')
    parser.add_argument('--cleaning-cost', type=float, default=1500.0, help='清潔費用（台幣）')
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
