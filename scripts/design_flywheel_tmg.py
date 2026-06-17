"""參數化「可評估」飛輪式熱磁發電機設計模型。

把材料 → 整機方程（generator_design.design_tmg）→ 幾何 → 總功率/質量/電壓/BOM 串成
單一可評估模型：改任何尺寸即重算效能。並輸出 CAD 尺寸 JSON（docs/flywheel_design.json）
供 cad_flywheel_tmg.py 生成 STEP/STL。

材料熱物性 ρ/Cp/κ 由 properties.py（成分式）算；ΔM/ΔS 取自 GA 結果（預設 350°C 飛輪最佳合金）。
磁體與結構質量為工程估算（能量法 / 經驗係數），需 FEA 細化——已標註。

用法：
  python scripts/design_flywheel_tmg.py            # 預設 350°C 設計點
  python scripts/design_flywheel_tmg.py --target-tc 150 --formula Fe32Co19Al17Cr14 --delta-m 0.389
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import torch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from alloy_engine.models.real_br import parse_formula
from alloy_engine.thermomagnetic.properties import (
    density_estimate, cp_estimate_specific, thermal_conductivity_estimate,
)
from alloy_engine.thermomagnetic.generator_design import design_tmg, MU_0

# 磁體性質（BH_max J/m³, 密度 kg/m³, 最高工作溫度 °C）
MAGNETS = {
    "NdFeB-SH": dict(Br=1.17, BHmax=300e3, rho=7500, tmax=150),
    "NdFeB-EH": dict(Br=1.12, BHmax=270e3, rho=7500, tmax=200),
    "SmCo-2:17": dict(Br=1.05, BHmax=200e3, rho=8400, tmax=350),
}
RHO_STEEL = 7850.0


def pick_magnet(t_hot_c: float, override: str | None) -> str:
    if override:
        return override
    if t_hot_c <= 145:
        return "NdFeB-SH"
    if t_hot_c <= 195:
        return "NdFeB-EH"
    return "SmCo-2:17"


def main() -> None:
    p = argparse.ArgumentParser(description="飛輪式 TMG 參數化設計")
    # 工作點 / 材料
    p.add_argument("--target-tc", type=float, default=350.0, help="目標 Tc / 工作溫度 °C")
    p.add_argument("--dt-half", type=float, default=30.0, help="循環半溫差 K（swing=2×）")
    p.add_argument("--formula", type=str, default="Fe31Co23Ni17Al14", help="合金（GA 飛輪最佳）")
    p.add_argument("--delta-m", type=float, default=0.365, help="循環極化變化 ΔJ (T)，取自 GA")
    p.add_argument("--delta-s", type=float, default=5.0, help="磁熵變 ΔS_M (J/kg·K)")
    # 磁路
    p.add_argument("--b-gap", type=float, default=1.2, help="氣隙磁場 B_app (T)")
    p.add_argument("--magnet", type=str, default=None, choices=list(MAGNETS), help="磁體（預設依溫度自選）")
    p.add_argument("--utilization", type=float, default=0.40)
    p.add_argument("--regeneration", type=float, default=0.90)
    # 幾何
    p.add_argument("--wheel-od", type=float, default=320.0, help="轉子外徑 mm")
    p.add_argument("--hub-od", type=float, default=120.0, help="活性環內徑 mm")
    p.add_argument("--shaft-bore", type=float, default=30.0, help="軸孔徑 mm")
    p.add_argument("--stack-height", type=float, default=50.0, help="疊片軸向高度 mm")
    p.add_argument("--plate-thickness", type=float, default=0.5, help="單片厚 mm")
    p.add_argument("--fill", type=float, default=0.5, help="活性材料填充率（其餘為回熱流道/間隙）")
    p.add_argument("--n-segments", type=int, default=24, help="周向扇區（疊片組）數")
    p.add_argument("--n-field-zones", type=int, default=2, help="磁場循環/轉（hot-cold pole pairs）")
    p.add_argument("--field-span-deg", type=float, default=60.0, help="單磁體角跨度 °")
    p.add_argument("--gap-mm", type=float, default=2.0, help="磁體氣隙 mm（含板）")
    p.add_argument("--n-turns", type=int, default=400)
    p.add_argument("--out", type=Path, default=Path("docs/flywheel_design.json"))
    args = p.parse_args()

    dev = torch.device("cpu")
    comp = parse_formula(args.formula)
    if comp is None:
        raise SystemExit(f"無法解析配方（含元素空間外元素？）：{args.formula}")
    ct = torch.tensor(comp, dtype=torch.float32, device=dev).unsqueeze(0)
    rho = float(density_estimate(ct)[0])
    cp = float(cp_estimate_specific(ct)[0])
    kappa = float(thermal_conductivity_estimate(ct)[0])

    t_cold = args.target_tc - args.dt_half
    t_hot = args.target_tc + args.dt_half
    plate_t_m = args.plate_thickness * 1e-3

    # ── 幾何體積（SI） ──
    D, d, H = args.wheel_od * 1e-3, args.hub_od * 1e-3, args.stack_height * 1e-3
    A_ann = math.pi / 4.0 * (D ** 2 - d ** 2)          # 活性環截面積 m²
    V_envelope = A_ann * H                               # 活性環包絡體積 m³
    V_material = V_envelope * args.fill                  # 真材料體積 m³
    radial_width = (D - d) / 2.0                         # 活性環徑向寬 m
    core_area = H * radial_width                         # 單磁區磁通截面 m²（估）

    # ── 整機方程（per-volume），core_area 給感應電壓 ──
    rep = design_tmg(
        T_cold_C=t_cold, T_hot_C=t_hot, delta_M_T=args.delta_m,
        rho=rho, cp_specific=cp, kappa=kappa, delta_S_M=args.delta_s,
        B_applied_T=args.b_gap, cycle_utilization=args.utilization,
        regenerator_effectiveness=args.regeneration,
        plate_thickness_m=plate_t_m, n_turns=args.n_turns, core_area_m2=core_area,
    )

    # ── 尺度化到整機 ──
    P_total = rep.power_density_W_m3 * V_material        # W（材料體積尺度）
    f = rep.f_Hz
    rpm = 60.0 * f / max(args.n_field_zones, 1)          # 轉速（每轉 n_field_zones 次循環）
    n_plates_per_seg = max(int(round((H) / plate_t_m * args.fill)), 1)
    n_plates_total = n_plates_per_seg * args.n_segments

    # ── 磁體尺寸（能量法估算） ──
    mag = MAGNETS[pick_magnet(t_hot, args.magnet)]
    field_fraction = args.n_field_zones * args.field_span_deg / 360.0
    V_gap_field = field_fraction * A_ann * (args.gap_mm * 1e-3)              # 場域氣隙體積 m³
    E_gap = (args.b_gap ** 2) / (2.0 * MU_0) * V_gap_field                   # 氣隙磁能 J
    V_magnet = 2.0 * E_gap / mag["BHmax"]                                    # ×2 含回路/效率
    m_magnet = V_magnet * mag["rho"]
    ro_ri = math.exp(args.b_gap / mag["Br"])                                # Halbach 估：ro/ri

    # ── 質量 / 慣量 ──
    m_material = V_material * rho
    m_rotor_struct = RHO_STEEL * (math.pi / 4.0 * (D ** 2 - (args.shaft_bore * 1e-3) ** 2)) * H * 0.35
    m_rotor = m_material + m_rotor_struct
    R = D / 2.0
    I_rotor = 0.5 * m_rotor * R ** 2
    omega = 2.0 * math.pi * rpm / 60.0
    E_flywheel = 0.5 * I_rotor * omega ** 2
    m_total = m_rotor + m_magnet

    P_per_kg = P_total / max(m_total, 1e-9)

    # ── 設計尺寸（給 CAD） ──
    dims = dict(
        meta=dict(target_tc_C=args.target_tc, formula=args.formula, magnet=pick_magnet(t_hot, args.magnet)),
        wheel_OD_mm=args.wheel_od, hub_OD_mm=args.hub_od, shaft_bore_mm=args.shaft_bore,
        stack_height_mm=args.stack_height, plate_thickness_mm=args.plate_thickness,
        n_segments=args.n_segments, n_plates_total=n_plates_total, fill=args.fill,
        gap_mm=args.gap_mm, field_span_deg=args.field_span_deg, n_field_zones=args.n_field_zones,
        magnet_ro_over_ri=round(ro_ri, 3), magnet_radial_mm=round(radial_width * 1e3, 1),
        shaft_len_mm=args.stack_height + 120.0, flywheel_OD_mm=args.hub_od - 10,
        flywheel_thickness_mm=40.0,
    )
    perf = dict(
        material=dict(rho=round(rho, 1), cp=round(cp, 1), kappa=round(kappa, 2)),
        delta_M_T=args.delta_m, B_gap_T=args.b_gap, f_Hz=round(f, 3), rpm=round(rpm, 1),
        eta_material_pct=round(rep.eta_material * 100, 3), eta_carnot_pct=round(rep.eta_carnot * 100, 2),
        eta_rel_carnot_pct=round(rep.eta_relative_carnot * 100, 1),
        power_density_W_m3=round(rep.power_density_W_m3, 1), P_total_W=round(P_total, 1),
        V_rms=round(rep.v_rms_volts, 2),
        V_material_cm3=round(V_material * 1e6, 1), m_material_kg=round(m_material, 2),
        m_magnet_kg=round(m_magnet, 2), m_total_kg=round(m_total, 2),
        P_per_kg_W=round(P_per_kg, 2), I_rotor_kgm2=round(I_rotor, 4),
        E_flywheel_J=round(E_flywheel, 1),
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(dict(dims=dims, perf=perf), ensure_ascii=False, indent=1))
    Path("/tmp/flywheel_design.json").write_text(json.dumps(dict(dims=dims, perf=perf), ensure_ascii=False))

    # ── 設計表 ──
    print("═" * 56)
    print(f"  飛輪式 TMG 設計點：{args.target_tc:.0f}°C  |  {args.formula}  |  磁體 {dims['meta']['magnet']}")
    print("═" * 56)
    print(f"  材料  ρ={rho:.0f} kg/m³  Cp={cp:.0f} J/kgK  κ={kappa:.1f} W/mK")
    print(f"  工作  {t_cold:.0f}→{t_hot:.0f}°C (ΔT={t_hot-t_cold:.0f}K)  B_gap={args.b_gap} T  ε={args.regeneration}")
    print("─" * 56 + "\n  幾何")
    print(f"   轉子 OD/ID/軸孔 = {args.wheel_od:.0f}/{args.hub_od:.0f}/{args.shaft_bore:.0f} mm  疊高={args.stack_height:.0f} mm")
    print(f"   片厚={args.plate_thickness} mm  扇區={args.n_segments}  總片數≈{n_plates_total}  填充={args.fill}")
    print(f"   磁體 ro/ri≈{ro_ri:.2f}  徑向≈{radial_width*1e3:.0f} mm  場區={field_fraction*100:.0f}% (n_zones={args.n_field_zones})")
    print("─" * 56 + "\n  效能")
    print(f"   循環頻率 f = {f:.2f} Hz  →  轉速 ≈ {rpm:.0f} rpm")
    print(f"   材料效率 η = {rep.eta_material*100:.3f} %   (卡諾 {rep.eta_carnot*100:.1f}% → 相對 {rep.eta_relative_carnot*100:.0f}%)")
    print(f"   功率密度 = {rep.power_density_W_m3:,.0f} W/m³  →  整機 P ≈ {P_total:.0f} W")
    print(f"   感應電壓 V_rms ≈ {rep.v_rms_volts:.1f} V (N={args.n_turns})")
    print("─" * 56 + "\n  質量 / BOM")
    print(f"   活性材料 {m_material:.1f} kg ({V_material*1e6:.0f} cm³)  磁體 {m_magnet:.1f} kg ({dims['meta']['magnet']})")
    print(f"   轉子結構 {m_rotor_struct:.1f} kg  →  總質量 ≈ {m_total:.1f} kg   比功率 {P_per_kg:.1f} W/kg")
    print(f"   飛輪慣量 I={I_rotor:.3f} kg·m²  儲能 {E_flywheel:.0f} J @ {rpm:.0f} rpm")
    print("═" * 56)
    print(f"  ⚠ 磁體/結構質量為能量法/經驗估算；P、η 為整機模型上界（相對比較）。")
    print(f"  CAD 尺寸已寫入 {args.out}")


if __name__ == "__main__":
    main()
