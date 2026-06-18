"""參數化「可評估」飛輪式熱磁發電機設計模型（v2：磁路 + κ 校準）。

材料 → generator_design.design_tmg（per-vol η/f/P/V_rms）→ 幾何 → 整機功率/質量/慣量/BOM，
單一可評估鏈：改任何尺寸即重算。輸出 CAD 尺寸 JSON（docs/flywheel_design.json）。

v2 升級：
- 磁體尺寸改用 thermomagnetic.magnetic_circuit.size_magnet（最大能量積 + 漏磁 + 溫度修正 Br +
  簡單氣隙 vs 聚磁/Halbach 判斷 + 退磁裕度），取代 ln() 估算。
- κ 校準：引擎以純元素線性混合高估固溶體 κ，calibrate_kappa 封頂至 alloy-class 文獻值，
  f/P 同步重評（較誠實）。--kappa 可手動覆寫。

材料熱物性 ρ/Cp 由 properties.py（成分式）算；ΔM/ΔS 取自 GA 結果。

用法：
  python scripts/design_flywheel_tmg.py
  python scripts/design_flywheel_tmg.py --target-tc 150 --formula Fe32Co19Al17Cr14 --delta-m 0.389 --kappa 22
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
from alloy_engine.thermomagnetic.generator_design import design_tmg
from alloy_engine.thermomagnetic.magnetic_circuit import size_magnet, calibrate_kappa, pick_grade

RHO_STEEL = 7850.0


def main() -> None:
    p = argparse.ArgumentParser(description="飛輪式 TMG 參數化設計 (v2)")
    p.add_argument("--target-tc", type=float, default=350.0)
    p.add_argument("--dt-half", type=float, default=30.0, help="循環半溫差 K（swing=2×）")
    p.add_argument("--formula", type=str, default="Fe31Co23Ni17Al14")
    p.add_argument("--delta-m", type=float, default=0.365, help="循環極化變化 ΔJ (T)，取自 GA")
    p.add_argument("--delta-s", type=float, default=5.0, help="磁熵變 ΔS_M (J/kg·K)")
    p.add_argument("--b-gap", type=float, default=1.4, help="氣隙磁場 B_app (T)")
    p.add_argument("--magnet", type=str, default=None,
                   choices=["NdFeB-N42SH", "NdFeB-N38EH", "SmCo-2:17"], help="磁體（預設依溫度自選）")
    p.add_argument("--magnet-temp-cap", type=float, default=300.0, help="熱隔離使磁體溫度上限 °C")
    p.add_argument("--leakage", type=float, default=1.0, help="FEM 漏磁因子（fem_magnetics.py 量；1.0=優化, ~0.48=未優化C型）")
    p.add_argument("--utilization", type=float, default=0.40)
    p.add_argument("--regeneration", type=float, default=0.90)
    p.add_argument("--kappa", type=float, default=None, help="覆寫熱導率 W/mK（預設用校準值）")
    # 幾何
    p.add_argument("--wheel-od", type=float, default=320.0)
    p.add_argument("--hub-od", type=float, default=120.0)
    p.add_argument("--shaft-bore", type=float, default=30.0)
    p.add_argument("--stack-height", type=float, default=50.0)
    p.add_argument("--plate-thickness", type=float, default=0.5)
    p.add_argument("--fill", type=float, default=0.5)
    p.add_argument("--n-segments", type=int, default=24)
    p.add_argument("--n-field-zones", type=int, default=2)
    p.add_argument("--field-span-deg", type=float, default=60.0)
    p.add_argument("--gap-mm", type=float, default=2.0)
    p.add_argument("--n-turns", type=int, default=400)
    p.add_argument("--out", type=Path, default=Path("docs/flywheel_design.json"))
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args()

    dev = torch.device("cpu")
    comp = parse_formula(args.formula)
    if comp is None:
        raise SystemExit(f"無法解析配方：{args.formula}")
    ct = torch.tensor(comp, dtype=torch.float32, device=dev).unsqueeze(0)
    rho = float(density_estimate(ct)[0])
    cp = float(cp_estimate_specific(ct)[0])
    kappa_engine = float(thermal_conductivity_estimate(ct)[0])
    kappa = args.kappa if args.kappa is not None else calibrate_kappa(kappa_engine)

    t_cold = args.target_tc - args.dt_half
    t_hot = args.target_tc + args.dt_half
    plate_t_m = args.plate_thickness * 1e-3

    # 幾何體積 (SI)
    D, d, H = args.wheel_od * 1e-3, args.hub_od * 1e-3, args.stack_height * 1e-3
    A_ann = math.pi / 4.0 * (D ** 2 - d ** 2)
    V_material = A_ann * H * args.fill
    radial_width = (D - d) / 2.0
    core_area = H * radial_width

    rep = design_tmg(
        T_cold_C=t_cold, T_hot_C=t_hot, delta_M_T=args.delta_m,
        rho=rho, cp_specific=cp, kappa=kappa, delta_S_M=args.delta_s,
        B_applied_T=args.b_gap, cycle_utilization=args.utilization,
        regenerator_effectiveness=args.regeneration,
        plate_thickness_m=plate_t_m, n_turns=args.n_turns, core_area_m2=core_area,
    )

    P_total = rep.power_density_W_m3 * V_material
    f = rep.f_Hz
    rpm = 60.0 * f / max(args.n_field_zones, 1)
    n_plates_total = max(int(round(H / plate_t_m * args.fill)), 1) * args.n_segments

    # 磁路（取代 ln()）
    field_fraction = args.n_field_zones * args.field_span_deg / 360.0
    A_gap = field_fraction * A_ann
    T_magnet = min(t_cold, args.magnet_temp_cap)
    mc = size_magnet(args.b_gap, args.gap_mm * 1e-3, A_gap, T_magnet, grade_key=args.magnet, leakage=args.leakage)
    m_magnet = mc.get("magnet_mass_kg", float("nan"))

    # 質量 / 慣量
    m_material = V_material * rho
    m_rotor_struct = RHO_STEEL * (math.pi / 4.0 * (D ** 2 - (args.shaft_bore * 1e-3) ** 2)) * H * 0.35
    m_rotor = m_material + m_rotor_struct
    R = D / 2.0
    I_rotor = 0.5 * m_rotor * R ** 2
    omega = 2.0 * math.pi * rpm / 60.0
    E_flywheel = 0.5 * I_rotor * omega ** 2
    m_total = m_rotor + m_magnet
    P_per_kg = P_total / max(m_total, 1e-9)

    dims = dict(
        meta=dict(target_tc_C=args.target_tc, formula=args.formula, magnet=mc.get("grade")),
        wheel_OD_mm=args.wheel_od, hub_OD_mm=args.hub_od, shaft_bore_mm=args.shaft_bore,
        stack_height_mm=args.stack_height, plate_thickness_mm=args.plate_thickness,
        n_segments=args.n_segments, n_plates_total=n_plates_total, fill=args.fill,
        gap_mm=args.gap_mm, field_span_deg=args.field_span_deg, n_field_zones=args.n_field_zones,
        magnet_ro_over_ri=mc.get("ro_over_ri"), magnet_radial_mm=round(radial_width * 1e3, 1),
        magnet_length_mm=mc.get("magnet_length_mm"),
        shaft_len_mm=args.stack_height + 120.0, flywheel_OD_mm=args.hub_od - 10,
        flywheel_thickness_mm=40.0,
    )
    perf = dict(
        material=dict(rho=round(rho, 1), cp=round(cp, 1),
                      kappa_engine=round(kappa_engine, 1), kappa_used=round(kappa, 1)),
        magnet_circuit=mc,
        delta_M_T=args.delta_m, B_gap_T=args.b_gap, f_Hz=round(f, 3), rpm=round(rpm, 1),
        eta_material_pct=round(rep.eta_material * 100, 3), eta_carnot_pct=round(rep.eta_carnot * 100, 2),
        eta_rel_carnot_pct=round(rep.eta_relative_carnot * 100, 1),
        power_density_W_m3=round(rep.power_density_W_m3, 1), P_total_W=round(P_total, 1),
        V_rms=round(rep.v_rms_volts, 2),
        V_material_cm3=round(V_material * 1e6, 1), m_material_kg=round(m_material, 2),
        m_magnet_kg=round(m_magnet, 2), m_total_kg=round(m_total, 2),
        P_per_kg_W=round(P_per_kg, 2), I_rotor_kgm2=round(I_rotor, 4), E_flywheel_J=round(E_flywheel, 1),
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(dict(dims=dims, perf=perf), ensure_ascii=False, indent=1))
    Path("/tmp/flywheel_design.json").write_text(json.dumps(dict(dims=dims, perf=perf), ensure_ascii=False))

    if args.quiet:
        return
    print("═" * 60)
    print(f"  飛輪式 TMG (v2)  {args.target_tc:.0f}°C  |  {args.formula}  |  磁體 {mc.get('grade')}")
    print("═" * 60)
    print(f"  材料  ρ={rho:.0f}  Cp={cp:.0f}  κ={kappa:.1f} W/mK (引擎估 {kappa_engine:.0f}→校準 {kappa:.0f})")
    print(f"  工作  {t_cold:.0f}→{t_hot:.0f}°C  B_gap={args.b_gap}T  ε={args.regeneration}  磁體溫={T_magnet:.0f}°C")
    print("─" * 60 + "\n  磁路（最大能量積尺寸）")
    print(f"   {mc['regime']}  Br@T={mc['Br_at_T']}T (簡單氣隙上限 {mc['B_cap_simple_T']}T)")
    print(f"   聚磁倍率 C={mc['concentration_C']}  磁長={mc['magnet_length_mm']}mm  "
          f"磁體 {mc['magnet_mass_kg']}kg  退磁裕度 {mc['demag_margin_C']:.0f}°C")
    print("─" * 60 + "\n  效能")
    print(f"   f={f:.2f} Hz → {rpm:.0f} rpm   η={rep.eta_material*100:.3f}% "
          f"(卡諾 {rep.eta_carnot*100:.1f}% → 相對 {rep.eta_relative_carnot*100:.0f}%)")
    print(f"   P/V={rep.power_density_W_m3:,.0f} W/m³ → 整機 P≈{P_total:.0f} W   V_rms≈{rep.v_rms_volts:.1f} V")
    print("─" * 60 + "\n  質量 / BOM")
    print(f"   活材 {m_material:.1f}kg  磁體 {m_magnet:.1f}kg ({mc.get('grade')}, ${mc.get('magnet_cost_usd'):.0f})  "
          f"結構 {m_rotor_struct:.1f}kg → 總 {m_total:.1f}kg  比功率 {P_per_kg:.1f} W/kg")
    print(f"   飛輪 I={I_rotor:.3f} kg·m²  儲能 {E_flywheel:.0f} J @ {rpm:.0f} rpm")
    print("═" * 60)
    print("  ⚠ P/η 為整機模型上界（相對比較）；磁體為最大能量積/漏磁估算（需 FEM 細化）。")
    print(f"  CAD 尺寸 → {args.out}")


if __name__ == "__main__":
    main()
