"""
熱磁循環物理量計算模組

科學依據：
  - M(T) = Ms × (1 - T/Tc)^0.5  (平均場 Heisenberg, β=0.5)
  - delta_M = M(T_target-30K) - M(T_target+30K) 為熱磁循環淨磁化變化
  - Tc 工程最佳區 = T_target + 5 到 +50 K（略高於工作溫度）
  - κ 線性混合：對合金通常低估 30-50%（Nordheim 電子散射），但相對排序可用

v5.0 新增：
  - Cp 比熱（Kopp-Neumann rule，±5-10% 排序可信）
  - ΔS_M 磁熵變（mean-field + Bean-Rodbell proximity，σ=30K）
  - 循環頻率 f = α/(2L²)（純擴散，排序有效）
  - 品質頻率 = f / (1 + α_loss·Hc·Br·f)（含 Steinmetz 磁滯懲罰）
"""
import torch
from alloy_engine.data.elements import ELEMENTS

# 純元素熱導率 (W/m·K)，順序對應 ELEMENTS = [Fe,Ni,Co,Cr,Mn,Cu,Mo,Si,Al,V]
KAPPA_PURE = torch.tensor(
    [80.0, 91.0, 100.0, 94.0, 7.8, 401.0, 138.0, 149.0, 237.0, 31.0],
    dtype=torch.float32,
)

# ===== v5.0 新增：純元素莫耳比熱 =====
# 單位: J/(mol·K)，室溫 (~300K) Dulong-Petit 值
# 順序對應 ELEMENTS = [Fe, Ni, Co, Cr, Mn, Cu, Mo, Si, Al, V]
CP_PURE_MOLAR = torch.tensor(
    [25.10, 26.07, 24.81, 23.35, 26.32, 24.44, 24.06, 19.79, 24.20, 24.89],
    dtype=torch.float32,
)

# ===== v5.0 新增：純元素密度 =====
# 單位: kg/m³（從 g/cm³ × 1000）
# 順序對應 ELEMENTS = [Fe, Ni, Co, Cr, Mn, Cu, Mo, Si, Al, V]
RHO_PURE_KG_M3 = torch.tensor(
    [7870.0, 8908.0, 8900.0, 7190.0, 7470.0, 8960.0, 10280.0, 2330.0, 2700.0, 6110.0],
    dtype=torch.float32,
)


def cp_estimate_specific(compositions: torch.Tensor) -> torch.Tensor:
    """
    估算合金質量比熱 Cp_specific (J/kg·K).

    Kopp-Neumann rule:
      Cp_molar   = Σ_i (x_i × Cp_i)        [J/mol·K]
      M_avg      = Σ_i (x_i × M_i)          [g/mol]
      Cp_specific = Cp_molar / M_avg × 1000  [J/kg·K]

    準確度: ±5-10%（排序可信，絕對值不可信到 1%）.
    限制: 忽略 Tc 附近 lambda 異常（GA 內部排序不影響）.
    """
    from alloy_engine.data.elements import get_element_matrix
    cp_molar_pure = CP_PURE_MOLAR.to(compositions.device)
    em = torch.from_numpy(get_element_matrix()).to(compositions.device)
    M_avg = compositions @ em[:, 1]          # M 欄位 index=1，g/mol
    cp_molar = compositions @ cp_molar_pure  # J/mol·K
    return cp_molar / (M_avg * 1e-3)         # J/kg·K


def density_estimate(compositions: torch.Tensor) -> torch.Tensor:
    """合金密度線性混合 (kg/m³)."""
    rho = RHO_PURE_KG_M3.to(compositions.device)
    return compositions @ rho


def delta_s_m_estimate(
    compositions: torch.Tensor,
    Tc_K: torch.Tensor,
    T_target_C: float,
    Ms: torch.Tensor,
    proximity_width_K: float = 30.0,
    H_external_T: float = 1.0,
    field_scaling_1T: float = 0.05,
) -> torch.Tensor:
    """
    估算磁熵變 ΔS_M (J/kg·K).

    ΔS_M_max = R × ln(2S+1) per mole（mean-field 絕對熵上限, g≈2）
    ΔS_M     = ΔS_M_max × proximity(T-Tc) × field_factor(H)

    field_scaling 校準依據:
    - Fe-Ni Permalloy @ 1T: ΔS_M ≈ 2-4 J/(kg·K) (Tishin & Spichkin 2003,
      "The Magnetocaloric Effect and its Applications", ch.2)
    - 本公式 raw ΔS_M_max_specific ≈ 120-150 J/(kg·K) for Fe-rich alloys
    - 校準: field_scaling_1T = 0.05 → 輸出 ~3 J/(kg·K) at Tc, 1T
    - 場強依賴: H^(2/3)（mean-field near Tc，Oesterreicher & Parker 1984,
      J. Appl. Phys. 55, 4334）

    限制:
    - field_scaling_1T=0.05 為 Fe-Ni 系經驗值，Gd/稀土系統需另行校準
    - Mn μ=0 假設可能低估高 Mn 合金的熵（MODEL_CARD 已記錄）
    - 忽略一階相變（Fe/Ni/Co 系均為二階，不影響）

    Args:
        compositions:      (N, 10) atomic fractions
        Tc_K:              (N,) 居禮溫度 (K)
        T_target_C:        目標工作溫度 (°C)
        Ms:                (N,) 飽和磁化代理 (T)
        proximity_width_K: Bean-Rodbell 展寬 σ (K)，v5.0=30K
        H_external_T:      外加磁場強度 (T)，default=1.0 (典型 NdFeB)
        field_scaling_1T:  1T 場下理論→實際的縮放因子 (Fe-Ni 系=0.05)
    Returns:
        delta_S_M: (N,) J/(kg·K)，1T 場循環可驅動值
    """
    from alloy_engine.data.elements import get_element_matrix
    R = 8.314
    T_target_K = T_target_C + 273.15
    em = torch.from_numpy(get_element_matrix()).to(compositions.device)
    mu_per_site = compositions @ em[:, 6]             # mu 欄位 index=6，μB/atom
    S_avg = mu_per_site / 2.0                         # g≈2 近似
    delta_S_max_molar = R * torch.log(2.0 * S_avg + 1.0 + 1e-6)   # J/(mol·K)
    M_avg_g_mol = compositions @ em[:, 1]             # g/mol
    delta_S_max_specific = delta_S_max_molar / (M_avg_g_mol * 1e-3)  # J/(kg·K)
    proximity = torch.exp(
        -((T_target_K - Tc_K) ** 2) / (2.0 * proximity_width_K ** 2)
    )
    # H^(2/3): Oesterreicher & Parker 1984 mean-field near Tc
    field_factor = field_scaling_1T * (H_external_T ** (2.0 / 3.0))
    return delta_S_max_specific * proximity * field_factor


def thermal_efficiency_score(
    delta_S_M: torch.Tensor,
    Cp_specific: torch.Tensor,
    delta_T_window: float = 30.0,
) -> torch.Tensor:
    """
    熱磁循環效率代理: score = clamp(ΔS_M / Cp / typical_ratio, 0, 1).

    校準依據（field_scaling_1T=0.05 後）:
    - 典型 Fe-Ni: ΔS_M ≈ 2-4 J/(kg·K), Cp ≈ 450-500 J/(kg·K)
    - raw = ΔS_M/Cp ≈ 0.004-0.009
    - typical_ratio = 0.008 對應 Gd-class (ΔS_M=4, Cp=500)
    - score 範圍 ≈ 0.25-1.0 for Fe-based alloys (有效區分訊號)
    """
    raw = delta_S_M / (Cp_specific + 1e-6)
    # Cap = 0.04 以 Gd-class 為錨點（Gd@1T: ΔS_M=10, Cp=240 → ratio=0.042）
    # Fe 系合金 ratio ≈ 0.006-0.011，自然落在 0.15-0.28 範圍（不飽和）
    return torch.clamp(raw / 0.04, 0.0, 1.0)


def cycle_frequency_estimate(
    compositions: torch.Tensor,
    kappa: torch.Tensor,
    Cp_specific: torch.Tensor,
    L_meters: float = 1e-3,
) -> torch.Tensor:
    """
    熱磁循環頻率估算 (Hz).

    f = α / (2L²)，α = κ / (ρ Cp) 為熱擴散率 (m²/s).

    限制: 純擴散，無對流；f ∝ 1/L²（L 極敏感，已改為參數）.
    """
    rho = density_estimate(compositions)
    alpha = kappa / (rho * Cp_specific + 1e-6)
    return alpha / (2.0 * L_meters ** 2)


def quality_frequency_score(
    f_Hz: torch.Tensor,
    Hc: torch.Tensor,
    Br: torch.Tensor,
    alpha_loss: float = 0.001,
) -> torch.Tensor:
    """
    含磁滯損失的品質頻率 (v5.0 C3 修正).

    P_hyst ∝ f × Hc × Br (Steinmetz)
    score = f / (1 + α_loss · Hc · Br · f)

    防止 GA 偏向「高 f 但 Hc 大」的局部最優.
    """
    loss = alpha_loss * Hc * Br * f_Hz
    return f_Hz / (1.0 + loss + 1e-6)


def thermal_conductivity_estimate(compositions: torch.Tensor) -> torch.Tensor:
    """
    線性混合估算合金熱導率 κ (W/m·K).

    Args:
        compositions: (N, 10) atomic fractions, on any device
    Returns:
        kappa: (N,) 估算熱導率
    """
    kappa_pure = KAPPA_PURE.to(compositions.device)
    return compositions @ kappa_pure


def magnetic_thermodynamic_score(
    Ms: torch.Tensor,
    Tc_K: torch.Tensor,
    T_target_C: float,
    delta_T_window: float = 30.0,
) -> dict[str, torch.Tensor]:
    """
    計算熱磁循環的關鍵物理量（無 noise，deterministic）.

    M(T) = Ms × clamp(1 - T/Tc, 0, 1)^0.5  (平均場 β=0.5)

    Args:
        Ms:            (N,) 飽和磁化代理（surrogate 的 Br 輸出）
        Tc_K:          (N,) 居禮溫度 (K)
        T_target_C:    目標工作溫度 (°C)
        delta_T_window: 循環半溫差 (K)，循環在 [T_target - dT, T_target + dT]

    Returns:
        dict with tensors (all shape (N,)):
          M_at_low       : 循環低溫端磁化量
          M_at_high      : 循環高溫端磁化量
          delta_M        : M_at_low - M_at_high（熱磁循環能量代理）
          tc_window_score: Tc 落在工程最佳區 [T_target+5, T_target+50] 的 Gaussian 分數
    """
    dev = Ms.device
    T_target_K = T_target_C + 273.15
    T_low_K  = T_target_K - delta_T_window
    T_high_K = T_target_K + delta_T_window

    Tc_safe = torch.clamp(Tc_K, min=10.0)

    ratio_low  = torch.clamp(1.0 - T_low_K  / Tc_safe, min=0.0, max=1.0)
    ratio_high = torch.clamp(1.0 - T_high_K / Tc_safe, min=0.0, max=1.0)

    M_at_low  = Ms * torch.sqrt(ratio_low)
    M_at_high = Ms * torch.sqrt(ratio_high)
    delta_M   = M_at_low - M_at_high

    # 工程最佳區：Tc 偏高 T_target+25K 為中心，sigma=20K
    tc_offset = Tc_K - T_target_K
    tc_window_score = torch.exp(-((tc_offset - 25.0) ** 2) / (2 * 20.0 ** 2))

    return {
        "M_at_low":        M_at_low,
        "M_at_high":       M_at_high,
        "delta_M":         delta_M,
        "tc_window_score": tc_window_score,
    }
