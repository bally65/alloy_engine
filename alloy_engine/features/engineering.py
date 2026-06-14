"""
Oliynyk 風格特徵工程

對任一組成 c ∈ R^NUM_ELEMENTS（總和為 1），計算每個元素屬性 p 的：
  - 加權平均   mean_p  = Σ c_i p_i
  - 加權變異數 var_p   = Σ c_i (p_i - mean_p)²
  - 存在元素的最大值 / 最小值

最終得到 NUM_PROPS × 4 = 36 維特徵向量（與元素數無關，故加稀土不改維度）。
"""
import numpy as np
import torch

from alloy_engine.data.elements import get_element_matrix


def composition_to_features_torch(
    compositions: torch.Tensor,
    element_matrix_t: torch.Tensor,
) -> torch.Tensor:
    """
    GPU 向量化特徵計算。

    Args:
        compositions    : (N, NUM_ELEMENTS)，每列總和 ≈ 1，on device
        element_matrix_t: (NUM_ELEMENTS, NUM_PROPS)，on device

    Returns:
        features: (N, NUM_PROPS * 4)
    """
    N = compositions.shape[0]
    device = compositions.device
    BIG = torch.tensor(1e10, device=device)

    # 加權平均: (N, E) @ (E, P) = (N, P)
    weighted_mean = compositions @ element_matrix_t

    # 加權變異數
    diff = element_matrix_t.unsqueeze(0) - weighted_mean.unsqueeze(1)   # (N, E, P)
    weighted_var = torch.einsum("ne,nep->np", compositions, diff ** 2)

    # 存在元素（c > 1e-6）的最大 / 最小值
    mask = (compositions > 1e-6).unsqueeze(-1)                          # (N, E, 1)
    em_exp = element_matrix_t.unsqueeze(0).expand(N, -1, -1)
    masked_max = torch.where(mask, em_exp, -BIG).max(dim=1)[0]
    masked_min = torch.where(mask, em_exp,  BIG).min(dim=1)[0]
    masked_max = torch.where(masked_max < -1e9, torch.zeros_like(masked_max), masked_max)
    masked_min = torch.where(masked_min >  1e9, torch.zeros_like(masked_min), masked_min)

    return torch.cat([weighted_mean, weighted_var, masked_max, masked_min], dim=1)


def composition_to_features_np(
    compositions: np.ndarray,
    device: torch.device | None = None,
) -> np.ndarray:
    """
    CPU-friendly 包裝：接受 numpy 陣列，回傳 numpy 陣列。
    內部仍使用 GPU（若可用）加速，計算後搬回 CPU。
    """
    if device is None:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    element_matrix_t = torch.from_numpy(get_element_matrix()).to(device)
    comp_t = torch.from_numpy(compositions.astype(np.float32)).to(device)
    return composition_to_features_torch(comp_t, element_matrix_t).cpu().numpy()
