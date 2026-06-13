"""
整機級 (device-level) 適應度 — GA 直接對「發電機效能」最佳化
============================================================

generator_design.py 的純量設計工具量化了單一設計點；本模組把同一組方程式
**torch 向量化**，讓 GPU GA 能對整個族群（~10⁵ 個配方）直接計算「整機功率
密度 × 效率」並作為適應度，而非僅最佳化 delta_M / ΔS_M 等材料代理量。

與 properties.py 的關係：本模組複用 properties 的 delta_M、Cp、ρ、ΔS_M、
循環頻率（皆已向量化），再代入 generator_design 的整機公式：

    w_mag  = util · ΔJ · (B_app/μ₀)
    q_in   = ρ·Cp·ΔT_swing·(1-ε) + ρ·T_avg·ΔS_M
    η      = w_mag / q_in
    P/V    = w_mag · f_quality   （f_quality 已含 Steinmetz 磁滯懲罰）
    score  = 0.5·clamp(P/V / P_REF) + 0.5·clamp(η / η_REF)

所有運算皆為逐元素 torch op，可直接在 GA 的 (N,) 張量上執行。
"""
from __future__ import annotations

import torch

from alloy_engine.thermomagnetic.generator_design import MU_0
from alloy_engine.thermomagnetic.properties import (
    magnetic_thermodynamic_score,
    cp_estimate_specific,
    density_estimate,
    delta_s_m_estimate,
    thermal_conductivity_estimate,
    cycle_frequency_estimate,
    quality_frequency_score,
)

# 正規化錨點（來自 simulate_tmg_design.py 升級設計量級）
POWER_DENSITY_REF_W_M3 = 5.0e6     # ~5 MW/m³
EFFICIENCY_REF = 0.02              # 2% 材料效率（Fe 系架構優化上限附近）


def device_power_efficiency_score(
    pop: torch.Tensor,
    Ms: torch.Tensor,
    Tc_K: torch.Tensor,
    Hc: torch.Tensor,
    T_target_C: float,
    *,
    B_applied_T: float = 1.4,
    cycle_utilization: float = 0.30,
    regenerator_effectiveness: float = 0.90,
    delta_T_window: float = 30.0,
    L_meters: float = 5e-4,
    proximity_width_K: float = 30.0,
    H_external_T: float = 1.4,
    field_scaling_1T: float = 0.05,
) -> dict[str, torch.Tensor]:
    """
    向量化計算整機功率密度、效率與綜合適應度分數。

    Args:
        pop:        (N, NUM_ELEMENTS) 原子分率
        Ms:         (N,) 飽和磁化代理（surrogate 的 Br）
        Tc_K:       (N,) 居禮溫度 (K)
        Hc:         (N,) 矯頑力
        T_target_C: 目標工作溫度 (°C)
        其餘為整機設計參數（與 generator_design.design_tmg 對應）
    Returns:
        dict（皆為 (N,) 張量）：
          w_mag_J_m3, q_in_J_m3, eta, power_density_W_m3, f_quality, device_score
    """
    dev = pop.device
    T_target_K = T_target_C + 273.15
    T_avg_K = T_target_K
    delta_T_swing = 2.0 * delta_T_window

    thermo = magnetic_thermodynamic_score(
        Ms=Ms, Tc_K=Tc_K, T_target_C=T_target_C, delta_T_window=delta_T_window
    )
    delta_M = thermo["delta_M"]                       # (N,) Tesla

    rho = density_estimate(pop)                       # kg/m³
    cp = cp_estimate_specific(pop)                    # J/kg·K
    kappa = thermal_conductivity_estimate(pop)        # W/m·K
    delta_S = delta_s_m_estimate(
        pop, Tc_K, T_target_C, Ms=Ms,
        proximity_width_K=proximity_width_K,
        H_external_T=H_external_T, field_scaling_1T=field_scaling_1T,
    )                                                 # J/kg·K

    # 磁功密度 w = util · ΔJ · (B/μ₀)
    H_app = B_applied_T / MU_0
    w_mag = cycle_utilization * delta_M * H_app       # J/m³

    # 熱輸入密度（顯熱含回熱 + 磁熵潛熱）
    sensible = rho * cp * delta_T_swing * (1.0 - regenerator_effectiveness)
    latent = rho * T_avg_K * delta_S
    q_in = sensible + latent + 1e-9

    eta = w_mag / q_in

    # 品質頻率（含磁滯懲罰）→ 功率密度
    f_Hz = cycle_frequency_estimate(pop, kappa, cp, L_meters=L_meters)
    f_quality = quality_frequency_score(f_Hz, Hc=Hc, Br=Ms, alpha_loss=0.001)
    power_density = w_mag * f_quality                 # W/m³

    # 綜合分數：功率密度與效率各半，皆正規化並 clamp 到 [0,1]
    p_score = torch.clamp(power_density / POWER_DENSITY_REF_W_M3, 0.0, 1.0)
    e_score = torch.clamp(eta / EFFICIENCY_REF, 0.0, 1.0)
    device_score = 0.5 * p_score + 0.5 * e_score

    return {
        "w_mag_J_m3": w_mag,
        "q_in_J_m3": q_in,
        "eta": eta,
        "power_density_W_m3": power_density,
        "f_quality": f_quality,
        "device_score": device_score,
    }
