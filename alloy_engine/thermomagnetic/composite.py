"""
複合磁熱材料 (composite MCM) 有效物性模型 — 高 κ 基底 + 高 ΔM 相
================================================================

reference_materials.py 的 what-if 顯示：高 ΔM 的稀土/一階材料因 κ 太低
（3–10 W/mK）導致循環頻率崩跌，整機功率密度反而輸給 Fe 系。本模組量化
「複合材料」這條出路：把高 ΔM 磁熱相分散在高導熱基底（Cu/Al/α-Fe）中，
用一點 ΔM 的稀釋換取大幅提升的 κ → 頻率 → 功率密度。

兩相複合有效物性（基底體積分率 φ，磁熱相 = 1−φ）：
  ΔM_eff   = (1−φ)·ΔM_phase            （基底非磁性，僅稀釋極化）
  ρ_eff    = (1−φ)·ρ_phase + φ·ρ_matrix （體積加權）
  Cp_eff   = 質量加權（依質量分率）
  ΔS_M_eff = ΔS_M_phase · 相質量分率    （僅磁熱相有 MCE）
  κ_eff    = connectivity·κ∥ + (1−connectivity)·κ⊥
             κ∥ = 並聯上限（基底貫通），κ⊥ = 串聯下限

關鍵權衡：φ↑ → κ_eff 快速上升（頻率↑），但 ΔM_eff 線性下降（磁功↓），
存在一個使整機功率密度最大的最佳 φ*。

科學依據：複合熱導率上下界 Wiener bounds；α-Fe/Al 強化 La-Fe-Si 成型策略
（使用者提供文獻：雙相 La-Fe-Si-H、9 wt.% Al 球磨複合）。

模型限制：功率密度 = w_mag·f 中 f = α/(2L²) 無上限，故 κ 在模型中「永遠
有益」，連高 κ 的 Fe 系都會被建議加一點 Cu。實機在高頻會受渦流、磁滯、
對流換熱速率封頂，κ 的邊際效益會遞減。因此本模型對「低 κ 相」的複合增益
（×5–×22）量級可信，對「已高 κ 相」的小幅增益則偏樂觀，僅供相對比較。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from alloy_engine.thermomagnetic.generator_design import (
    design_layered_tmg, LayeredTMGReport,
)


@dataclass(frozen=True)
class MatrixMaterial:
    name: str
    kappa: float      # W/m·K
    rho: float        # kg/m³
    cp_specific: float  # J/kg·K


# 高導熱基底候選
MATRIX_MATERIALS: dict[str, MatrixMaterial] = {
    "Cu":    MatrixMaterial("Cu", kappa=401.0, rho=8960.0, cp_specific=385.0),
    "Al":    MatrixMaterial("Al", kappa=237.0, rho=2700.0, cp_specific=900.0),
    "alpha-Fe": MatrixMaterial("alpha-Fe", kappa=80.0, rho=7870.0, cp_specific=449.0),
}


def composite_properties(
    *,
    phase_delta_M_T: float,
    phase_cp: float,
    phase_rho: float,
    phase_kappa: float,
    phase_delta_S_M: float,
    matrix: MatrixMaterial,
    matrix_volume_fraction: float,
    connectivity: float = 0.7,
) -> dict[str, float]:
    """
    計算兩相複合材料的有效物性。

    Args:
        phase_*:               磁熱相物性
        matrix:                高導熱基底材料
        matrix_volume_fraction: 基底體積分率 φ ∈ [0, 1)
        connectivity:          κ 並聯(1)/串聯(0)權重，預設 0.7（基底大致貫通）
    Returns:
        dict(delta_M_T, cp_specific, rho, kappa, delta_S_M)
    """
    phi = matrix_volume_fraction
    if not 0.0 <= phi < 1.0:
        raise ValueError("matrix_volume_fraction 必須落在 [0, 1)")
    if not 0.0 <= connectivity <= 1.0:
        raise ValueError("connectivity 必須落在 [0, 1]")
    f_phase = 1.0 - phi

    rho_eff = f_phase * phase_rho + phi * matrix.rho
    m_phase = f_phase * phase_rho
    m_matrix = phi * matrix.rho
    m_tot = m_phase + m_matrix
    cp_eff = (m_phase * phase_cp + m_matrix * matrix.cp_specific) / m_tot
    delta_M_eff = f_phase * phase_delta_M_T
    delta_S_eff = phase_delta_S_M * (m_phase / m_tot)

    k_par = f_phase * phase_kappa + phi * matrix.kappa
    k_ser = 1.0 / (f_phase / phase_kappa + phi / matrix.kappa)
    kappa_eff = connectivity * k_par + (1.0 - connectivity) * k_ser

    return {
        "delta_M_T": delta_M_eff,
        "cp_specific": cp_eff,
        "rho": rho_eff,
        "kappa": kappa_eff,
        "delta_S_M": delta_S_eff,
    }


@dataclass
class CompositeOptimum:
    matrix_name: str
    best_matrix_fraction: float
    bare_power_density_W_m3: float
    composite_power_density_W_m3: float
    composite_report: LayeredTMGReport
    eff_props: dict[str, float]

    @property
    def power_gain(self) -> float:
        return self.composite_power_density_W_m3 / (self.bare_power_density_W_m3 + 1e-12)


def optimal_matrix_fraction(
    *,
    phase_delta_M_T: float,
    phase_cp: float,
    phase_rho: float,
    phase_kappa: float,
    phase_delta_S_M: float,
    Tc_C: float,
    matrix: MatrixMaterial,
    half_window_K: float = 30.0,
    B_applied_T: float = 1.4,
    extra_regeneration: float = 0.90,
    plate_thickness_m: float = 5e-4,
    n_layers: int = 8,
    connectivity: float = 0.7,
    phi_max: float = 0.7,
    n_grid: int = 71,
) -> CompositeOptimum:
    """
    掃描基底體積分率 φ ∈ [0, phi_max]，找出使整機功率密度最大的 φ*。

    各 φ 以升級分層架構（design_layered_tmg）在 Tc±half_window 評估。
    """
    t_lo, t_hi = Tc_C - half_window_K, Tc_C + half_window_K

    def power_at(phi: float) -> tuple[float, LayeredTMGReport, dict]:
        p = composite_properties(
            phase_delta_M_T=phase_delta_M_T, phase_cp=phase_cp,
            phase_rho=phase_rho, phase_kappa=phase_kappa,
            phase_delta_S_M=phase_delta_S_M, matrix=matrix,
            matrix_volume_fraction=phi, connectivity=connectivity,
        )
        rep = design_layered_tmg(
            T_cold_C=t_lo, T_hot_C=t_hi,
            layer_delta_M_T=[p["delta_M_T"]] * n_layers,
            rho=p["rho"], cp_specific=p["cp_specific"], kappa=p["kappa"],
            delta_S_M=p["delta_S_M"], B_applied_T=B_applied_T,
            extra_regeneration=extra_regeneration,
            plate_thickness_m=plate_thickness_m,
        )
        return rep.power_density_W_m3, rep, p

    bare_power, _, _ = power_at(0.0)
    phis = np.linspace(0.0, phi_max, n_grid)
    best = max((power_at(float(phi)) + (float(phi),) for phi in phis),
               key=lambda t: t[0])
    best_power, best_rep, best_props, best_phi = best

    return CompositeOptimum(
        matrix_name=matrix.name,
        best_matrix_fraction=best_phi,
        bare_power_density_W_m3=bare_power,
        composite_power_density_W_m3=best_power,
        composite_report=best_rep,
        eff_props=best_props,
    )
