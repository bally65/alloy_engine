"""掃描飛輪式 TMG 設計空間（OD × 片厚 × B_gap × ε）→ Pareto（功率 vs 質量 vs 效率 vs 成本），
找出「最划算能量率比 + 最低推動能量」方案。

目標（多目標）：max P_total、max η、min 成本、min 質量（質量低＝飛輪推動/啟動能量低）。
取非支配 (Pareto) 集；推薦點＝Pareto 內「每美元功率 P/$」最高者（最划算），另列最高 η 與最低質量點。

輸出：docs/sweep_pareto.csv、docs/sweep_pareto.png
用法：python scripts/sweep_designs.py --target-tc 350
"""
from __future__ import annotations

import argparse
import csv
import itertools
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from alloy_engine.models.real_br import parse_formula
from alloy_engine.thermomagnetic.properties import (
    density_estimate, cp_estimate_specific, thermal_conductivity_estimate,
)
from alloy_engine.thermomagnetic.generator_design import design_tmg
from alloy_engine.thermomagnetic.magnetic_circuit import size_magnet, calibrate_kappa

# 各情境 GA 飛輪最佳合金（取自 compare_architectures 結果）
GA_BEST = {
    25:  ("Fe26Ni17Cr17Co16", 0.411),
    150: ("Fe31Co18Ni16Cr15", 0.379),
    350: ("Fe31Co23Ni17Al14", 0.365),
    500: ("Co32Fe30Al17Ni15", 0.371),
}
PRICE = dict(alloy_usd_kg=30.0, steel_usd_kg=3.0, electrical_flat=60.0)
RHO_STEEL = 7850.0


def evaluate(formula, delta_m, rho, cp, kappa, *, target_tc, dt_half,
             b_gap, plate_mm, wheel_od_mm, eps, hub_od=120.0, shaft_bore=30.0,
             stack_height=50.0, fill=0.5, n_segments=24, n_field_zones=2,
             field_span_deg=60.0, gap_mm=2.0, n_turns=400, util=0.40,
             delta_s=5.0, magnet_temp_cap=300.0) -> dict:
    t_cold, t_hot = target_tc - dt_half, target_tc + dt_half
    D, d, H = wheel_od_mm * 1e-3, hub_od * 1e-3, stack_height * 1e-3
    A_ann = math.pi / 4.0 * (D ** 2 - d ** 2)
    V_material = A_ann * H * fill
    core_area = H * (D - d) / 2.0
    rep = design_tmg(T_cold_C=t_cold, T_hot_C=t_hot, delta_M_T=delta_m, rho=rho,
                     cp_specific=cp, kappa=kappa, delta_S_M=delta_s, B_applied_T=b_gap,
                     cycle_utilization=util, regenerator_effectiveness=eps,
                     plate_thickness_m=plate_mm * 1e-3, n_turns=n_turns, core_area_m2=core_area)
    P_total = rep.power_density_W_m3 * V_material
    rpm = 60.0 * rep.f_Hz / max(n_field_zones, 1)
    field_fraction = n_field_zones * field_span_deg / 360.0
    mc = size_magnet(b_gap, gap_mm * 1e-3, field_fraction * A_ann, min(t_cold, magnet_temp_cap))
    m_material = V_material * rho
    m_struct = RHO_STEEL * (math.pi / 4.0 * (D ** 2 - (shaft_bore * 1e-3) ** 2)) * H * 0.35
    m_total = m_material + m_struct + mc["magnet_mass_kg"]
    cost = (m_material * PRICE["alloy_usd_kg"] + m_struct * PRICE["steel_usd_kg"]
            + mc["magnet_cost_usd"] + PRICE["electrical_flat"])
    I_rotor = 0.5 * (m_material + m_struct) * (D / 2.0) ** 2
    E_spin = 0.5 * I_rotor * (2 * math.pi * rpm / 60.0) ** 2
    return dict(b_gap=b_gap, plate_mm=plate_mm, wheel_od_mm=wheel_od_mm, eps=eps,
                f_Hz=rep.f_Hz, rpm=rpm, eta_pct=rep.eta_material * 100,
                P_total_W=P_total, m_total_kg=m_total, cost_usd=cost,
                P_per_usd=P_total / max(cost, 1e-9), P_per_kg=P_total / max(m_total, 1e-9),
                E_spin_J=E_spin, magnet=mc["grade"], magnet_kg=mc["magnet_mass_kg"])


def pareto_mask(rows) -> list[bool]:
    """非支配：max P, max η, min cost, min mass。"""
    obj = np.array([[r["P_total_W"], r["eta_pct"], -r["cost_usd"], -r["m_total_kg"]] for r in rows])
    n = len(rows); keep = [True] * n
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            if np.all(obj[j] >= obj[i]) and np.any(obj[j] > obj[i]):
                keep[i] = False
                break
    return keep


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-tc", type=int, default=350, choices=list(GA_BEST))
    ap.add_argument("--dt-half", type=float, default=30.0)
    args = ap.parse_args()

    formula, delta_m = GA_BEST[args.target_tc]
    ct = torch.tensor(parse_formula(formula), dtype=torch.float32).unsqueeze(0)
    rho = float(density_estimate(ct)[0]); cp = float(cp_estimate_specific(ct)[0])
    kappa = calibrate_kappa(float(thermal_conductivity_estimate(ct)[0]))

    grid = dict(
        b_gap=[0.8, 1.0, 1.2, 1.4],
        plate_mm=[0.2, 0.3, 0.5, 1.0],
        wheel_od_mm=[200, 280, 360, 440],
        eps=[0.60, 0.75, 0.85, 0.95],
    )
    rows = [evaluate(formula, delta_m, rho, cp, kappa, target_tc=args.target_tc,
                     dt_half=args.dt_half, b_gap=b, plate_mm=p, wheel_od_mm=w, eps=e)
            for b, p, w, e in itertools.product(grid["b_gap"], grid["plate_mm"],
                                                grid["wheel_od_mm"], grid["eps"])]
    keep = pareto_mask(rows)
    pareto = [r for r, k in zip(rows, keep) if k]

    # 推薦＝Pareto 內「最高效率 η」中「成本/質量最低」者（最划算能量率比 + 最低推動能量）。
    # 註：純 max(W/$) 會偏好最大設計（P∝OD² 勝過成本），不符「最低推動」，故不採用。
    _max_eta = max(r["eta_pct"] for r in pareto)
    rec = min([r for r in pareto if r["eta_pct"] >= _max_eta - 1e-6], key=lambda r: r["cost_usd"])
    max_power = max(pareto, key=lambda r: r["P_total_W"])
    least_mass = min(pareto, key=lambda r: r["m_total_kg"])

    out_csv = Path("docs/sweep_pareto.csv")
    with out_csv.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]) + ["pareto"])
        w.writeheader()
        for r, k in zip(rows, keep):
            w.writerow({**r, "pareto": int(k)})

    # 圖：成本 vs 功率，色=η，標 Pareto + 推薦
    fig, ax = plt.subplots(figsize=(8.4, 6))
    allc = np.array([r["cost_usd"] for r in rows]); allp = np.array([r["P_total_W"] for r in rows])
    alle = np.array([r["eta_pct"] for r in rows])
    sc = ax.scatter(allc, allp, c=alle, cmap="viridis", s=22, alpha=0.5, label="all designs")
    pc = np.array([r["cost_usd"] for r in pareto]); pp = np.array([r["P_total_W"] for r in pareto])
    order = np.argsort(pc)
    ax.plot(pc[order], pp[order], "-", color="crimson", lw=1.3, alpha=0.8, label="Pareto front")
    ax.scatter(pc, pp, edgecolors="crimson", facecolors="none", s=60, linewidths=1.3)
    ax.scatter([rec["cost_usd"]], [rec["P_total_W"]], marker="*", s=420, color="gold",
               edgecolors="k", zorder=5, label="recommended (max eta, min cost)")
    ax.set_xlabel("estimated cost (USD)"); ax.set_ylabel("ceiling power P_total (W)")
    ax.set_title(f"Flywheel TMG design sweep — {args.target_tc}°C ({formula})\n"
                 f"256 designs · color=η% · ★=most cost-effective")
    plt.colorbar(sc, label="material efficiency η (%)")
    ax.legend(loc="lower right", fontsize=8); ax.grid(alpha=0.3)
    plt.tight_layout(); plt.savefig("docs/sweep_pareto.png", dpi=150, bbox_inches="tight")

    def show(tag, r):
        print(f"  {tag:<22} B={r['b_gap']} 片厚={r['plate_mm']}mm OD={r['wheel_od_mm']} ε={r['eps']} | "
              f"P={r['P_total_W']:.0f}W η={r['eta_pct']:.2f}% m={r['m_total_kg']:.1f}kg "
              f"${r['cost_usd']:.0f} | {r['P_per_usd']:.1f}W/$ {r['rpm']:.0f}rpm")
    print(f"\n設計掃描 {args.target_tc}°C：{len(rows)} 設計，Pareto {len(pareto)} 個")
    print("-" * 96)
    show("★ 推薦 (max η · 最省)", rec)
    show("最大功率 (可擴大)", max_power)
    show("最低質量 (最省推動)", least_mass)
    print("-" * 96)
    print("  Pareto front（按成本排序）：")
    for r in sorted(pareto, key=lambda x: x["cost_usd"]):
        show("   ·", r)
    print(f"\n  CSV → {out_csv}   圖 → docs/sweep_pareto.png")


if __name__ == "__main__":
    main()
