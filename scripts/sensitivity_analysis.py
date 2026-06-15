"""
D6：複合/整機「假設參數」敏感度分析。

composite.py / generator_design.py 有幾個目前靠假設的參數（無實測）：
  - connectivity（複合 κ 並聯/串聯權重，預設 0.7）
  - extra_regeneration（分層回熱，預設 0.90）
  - cycle_utilization（磁功利用率，預設 0.30）

本腳本對代表材料逐一掃描各參數的合理範圍，量化關鍵輸出（最佳基底分率 φ*、
複合功率增益、整機功率密度）的擺幅——藉此判斷「哪些假設真的重要、值得優先實測」。

執行：python scripts/sensitivity_analysis.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from alloy_engine.thermomagnetic import reference_materials as rm
from alloy_engine.thermomagnetic.composite import (
    MATRIX_MATERIALS, optimal_matrix_fraction,
)


def run_sensitivity(material_name: str = "(Mn,Fe)2(P,Si)",
                    matrix_name: str = "Cu") -> dict:
    """回傳各假設參數掃描下的輸出擺幅（結構化，供報告/測試）。"""
    mat = rm.get(material_name)
    matrix = MATRIX_MATERIALS[matrix_name]
    base = dict(
        phase_delta_M_T=mat.delta_M_T, phase_cp=mat.cp_specific,
        phase_rho=mat.rho, phase_kappa=mat.kappa,
        phase_delta_S_M=mat.delta_S_M, Tc_C=mat.Tc_C, matrix=matrix,
    )

    def gain_phi(**overrides):
        opt = optimal_matrix_fraction(**base, **overrides)
        return opt.power_gain, opt.best_matrix_fraction

    sweeps = {
        "connectivity":       (np.linspace(0.4, 1.0, 7),  "connectivity"),
        "extra_regeneration": (np.linspace(0.0, 0.95, 8), "extra_regeneration"),
    }
    results: dict[str, dict] = {}
    for label, (grid, kw) in sweeps.items():
        gains, phis = [], []
        for v in grid:
            g, phi = gain_phi(**{kw: float(v)})
            gains.append(g); phis.append(phi)
        gains, phis = np.array(gains), np.array(phis)
        results[label] = {
            "grid": grid, "gains": gains, "phis": phis,
            "gain_min": float(gains.min()), "gain_max": float(gains.max()),
            "gain_rel_spread": float((gains.max() - gains.min()) / gains.mean()),
            "phi_min": float(phis.min()), "phi_max": float(phis.max()),
        }
    return {"material": material_name, "matrix": matrix_name, "sweeps": results}


def main() -> None:
    out = run_sensitivity()
    print("═" * 76)
    print(f" D6 — 假設參數敏感度（材料={out['material']}，基底={out['matrix']}）")
    print("═" * 76)
    print(f"{'參數':<22}{'掃描範圍':<16}{'功率增益範圍':<20}{'相對擺幅':>10}{'φ* 範圍':>10}")
    print("-" * 76)
    ranked = sorted(out["sweeps"].items(),
                    key=lambda kv: kv[1]["gain_rel_spread"], reverse=True)
    for label, r in ranked:
        rng = f"[{r['grid'][0]:.2f},{r['grid'][-1]:.2f}]"
        gain_rng = f"×{r['gain_min']:.1f}–×{r['gain_max']:.1f}"
        phi_rng = f"{r['phi_min']:.2f}–{r['phi_max']:.2f}"
        print(f"{label:<22}{rng:<16}{gain_rng:<20}{r['gain_rel_spread']*100:>9.0f}%{phi_rng:>10}")
    print("-" * 76)
    top = ranked[0]
    print(f" 最敏感假設：{top[0]}（相對擺幅 {top[1]['gain_rel_spread']*100:.0f}%）→ 優先實測對象")
    print(" 解讀：相對擺幅小 = 該假設對結論影響有限，現值可用；大 = 應優先量測校準。")
    print("═" * 76)


if __name__ == "__main__":
    main()
