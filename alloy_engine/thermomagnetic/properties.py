"""
熱磁循環物理量計算模組

科學依據：
  - M(T) = Ms × (1 - T/Tc)^0.5  (平均場 Heisenberg, β=0.5)
  - delta_M = M(T_target-30K) - M(T_target+30K) 為熱磁循環淨磁化變化
  - Tc 工程最佳區 = T_target + 5 到 +50 K（略高於工作溫度）
  - κ 線性混合：對合金通常低估 30-50%（Nordheim 電子散射），但相對排序可用
"""
import torch
from alloy_engine.data.elements import ELEMENTS

# 純元素熱導率 (W/m·K)，順序對應 ELEMENTS = [Fe,Ni,Co,Cr,Mn,Cu,Mo,Si,Al,V]
KAPPA_PURE = torch.tensor(
    [80.0, 91.0, 100.0, 94.0, 7.8, 401.0, 138.0, 149.0, 237.0, 31.0],
    dtype=torch.float32,
)


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
