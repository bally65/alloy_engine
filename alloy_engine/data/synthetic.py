"""
物理啟發式合成訓練資料生成

生產建議：用 Materials Project / NEMAD 真實資料替換此模組中的函數。
關鍵物理規律：
  - Fe-Ni Permalloy 在 ~50% Ni 時具最佳軟磁特性
  - Cr/Mn 透過反鐵磁耦合壓制 Tc（每 at% 約降 50K）
  - Mo/Cr/V 是固溶強化主力元素
"""
import logging

import numpy as np

from alloy_engine.data.elements import ELEMENTS

logger = logging.getLogger(__name__)


def physics_based_properties_batch(
    comp: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    批次生成合金性質（含實驗雜訊）。

    Args:
        comp: (N, NUM_ELEMENTS) 組成矩陣，每列總和 ≈ 1

    Returns:
        (tc, hc, br, sigma_y) 各為 (N,) ndarray
          tc      : 居禮溫度 (K)
          hc      : 矯頑力 (A/m)
          br      : 剩磁 (T)
          sigma_y : 降伏強度 (MPa)
    """
    fe = comp[:, ELEMENTS.index("Fe")]
    ni = comp[:, ELEMENTS.index("Ni")]
    co = comp[:, ELEMENTS.index("Co")]
    cr = comp[:, ELEMENTS.index("Cr")]
    mn = comp[:, ELEMENTS.index("Mn")]
    cu = comp[:, ELEMENTS.index("Cu")]
    mo = comp[:, ELEMENTS.index("Mo")]
    si = comp[:, ELEMENTS.index("Si")]
    al = comp[:, ELEMENTS.index("Al")]
    v  = comp[:, ELEMENTS.index("V")]
    n  = comp.shape[0]

    # ── Tc (居禮溫度, K) ──────────────────────────────────────────────────────
    mag_frac = fe + ni + co

    # Base: 純元素線性混合（對二元合金準）
    base_tc = np.where(
        mag_frac > 0.05,
        (fe * 1043 + ni * 627 + co * 1400) / np.maximum(mag_frac, 0.01),
        50.0,
    )

    # Slater-Pauling Fe-Co 協同增強（峰值 80 K，於 Fe=Co=0.5）
    fe_co_synergy = 80.0 * 4.0 * (fe * co) / (mag_frac ** 2 + 1e-6)

    # 抑制項：Cr/Mn 係數大幅降低（v1: 5500/4500 → v2: 1800/1200）
    cr_suppress = 1800 * np.power(cr, 1.2)
    mn_suppress = 1200 * np.power(mn, 1.2)

    # 稀釋項：係數降低（v1: 0.5 → v2: 0.20）
    nonmag   = 1 - mag_frac - cr - mn
    dilution = base_tc * nonmag * 0.20

    # Permalloy 區增強（保留）
    permalloy = np.where(
        (ni > 0.3) & (ni < 0.6) & (fe > 0.3),
        100 * np.exp(-((ni - 0.5) ** 2) / 0.02),
        0,
    )

    tc = (base_tc + fe_co_synergy) * mag_frac - cr_suppress - mn_suppress - dilution + permalloy
    tc += np.random.normal(0, 25, n)
    tc = np.clip(tc, 50, 1500)

    # ── Hc (矯頑力, A/m)：越低越軟 ───────────────────────────────────────────
    fe_ni_balance = np.abs(fe - ni)
    base_hc = 50.0 + 250 * fe_ni_balance
    base_hc -= 30 * si
    base_hc += 100 * (cu + mo)
    base_hc *= np.random.uniform(0.7, 1.3, n)
    hc = np.clip(base_hc, 1.0, 1000)

    # ── Br (剩磁, T) — v5.1 calibrated ──────────────────────────────────────
    # Per-element Br contribution (T): Fe=1.40, Ni=0.60, Co=1.80 (Bozorth 1951, Cullity 2009)
    # Old formula: mag_moment*0.4 → max 1.07 T (pure Fe), no Co synergy
    BR_ELEM_CONTRIB = np.array([1.40, 0.60, 1.80, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    br_base = comp @ BR_ELEM_CONTRIB
    mag_frac = fe + ni + co
    # Fe-Co Slater-Pauling synergy: Hiperco50 Br=2.40T >> linear pred 1.60T
    fe_co_synergy_br = 0.80 * 4.0 * (fe * co) / (mag_frac ** 2 + 1e-6)
    br = (br_base + fe_co_synergy_br) * np.random.uniform(0.88, 1.12, n)
    br = np.clip(br, 0.01, 2.6)

    # ── σy (降伏強度, MPa)：固溶強化模型 ─────────────────────────────────────
    base_str      = 250 + 100 * fe
    solid_solution = 800 * cr + 1200 * mo + 600 * si + 400 * al + 900 * v + 300 * mn
    cu_penalty    = 200 * cu
    sigma_y = (base_str + solid_solution - cu_penalty) * np.random.uniform(0.85, 1.15, n)
    sigma_y = np.clip(sigma_y, 50, 1500)

    return tc, hc, br, sigma_y


def generate_sparse_composition(
    n_samples: int,
    alpha_full: np.ndarray,
    rng: np.random.Generator,
    n_active_min: int = 2,
    n_active_max: int = 8,
    n_active_lambda: float = 4.0,
) -> tuple[np.ndarray, np.ndarray]:
    """
    稀疏 Dirichlet 採樣：每筆只啟用 n_active 個元素，其餘為精確 0。

    做法：先用 Poisson 決定啟用元素數，再按 alpha 加權選元素，
    最後在選中元素的子空間做正規 Dirichlet，確保分率分佈正確。

    Args:
        n_samples       : 樣本數
        alpha_full      : (n_elements,) Dirichlet 偏置向量
        rng             : numpy Generator (reproducible)
        n_active_min    : 最少啟用元素數
        n_active_max    : 最多啟用元素數
        n_active_lambda : Poisson 均值，控制平均啟用數

    Returns:
        compositions : (n_samples, n_elements) float32，每列總和=1
        n_active_arr : (n_samples,) int32，每筆啟用元素數
    """
    n_elements = len(alpha_full)
    compositions = np.zeros((n_samples, n_elements), dtype=np.float32)
    n_active_arr = np.zeros(n_samples, dtype=np.int32)

    probs = alpha_full / alpha_full.sum()

    for i in range(n_samples):
        # 1. 決定啟用元素數（Poisson + clip）
        n_active = int(np.clip(rng.poisson(n_active_lambda), n_active_min, n_active_max))
        n_active_arr[i] = n_active

        # 2. 按 alpha 加權選擇哪些元素啟用
        active_idx = rng.choice(n_elements, size=n_active, replace=False, p=probs)

        # 3. 在選中元素的子空間做標準 Dirichlet
        alpha_active = alpha_full[active_idx]
        fractions = rng.dirichlet(alpha_active)

        # 4. 放回 10 維向量
        compositions[i, active_idx] = fractions

    return compositions, n_active_arr


def generate_training_data(
    n_samples: int = 8_000,
    seed: int = 42,
    sparse: bool = True,
    n_active_lambda: float = 4.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    生成訓練資料集。

    Args:
        n_samples       : 樣本數
        seed            : 亂數種子
        sparse          : True = 稀疏 Dirichlet（預設）；False = 舊版全元素 Dirichlet
        n_active_lambda : 稀疏模式下 Poisson 均值（平均啟用元素數）

    Returns:
        (compositions, tc, hc, br, sigma_y)
        compositions: (n_samples, NUM_ELEMENTS) float32
    """
    rng = np.random.default_rng(seed)
    np.random.seed(seed)  # physics_based_properties_batch 內部仍用 np.random

    alpha_full = np.array([3.0, 3.0, 1.5, 1.0, 0.6, 0.5, 0.5, 0.4, 0.4, 0.4],
                          dtype=np.float64)

    if sparse:
        logger.info("生成 %d 筆稀疏訓練樣本（Poisson lambda=%.1f）…", n_samples, n_active_lambda)
        compositions, n_active = generate_sparse_composition(
            n_samples, alpha_full, rng,
            n_active_min=2, n_active_max=8, n_active_lambda=n_active_lambda,
        )
        n_active_mean = n_active.mean()
        logger.info("啟用元素數: mean=%.2f  min=%d  max=%d", n_active_mean, n_active.min(), n_active.max())
    else:
        logger.info("生成 %d 筆訓練樣本（全元素 Dirichlet）…", n_samples)
        compositions = rng.dirichlet(alpha_full, size=n_samples).astype(np.float32)

    tc, hc, br, sigma_y = physics_based_properties_batch(compositions)
    logger.info(
        "Tc: %.0f–%.0f K | Hc: %.1f–%.1f A/m | Br: %.2f–%.2f T | σy: %.0f–%.0f MPa",
        tc.min(), tc.max(), hc.min(), hc.max(),
        br.min(), br.max(), sigma_y.min(), sigma_y.max(),
    )
    return compositions, tc, hc, br, sigma_y
