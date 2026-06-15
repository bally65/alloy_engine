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

# 每元素剩磁貢獻 (T)：磁性元素有值，其餘（含 P/Ge 類金屬）預設 0。
BR_ELEM_CONTRIB: dict[str, float] = {
    "Fe": 1.40, "Ni": 0.60, "Co": 1.80, "Gd": 1.80,
}

# Dirichlet 設計先驗（取樣偏置）：磁性主族權重高，類金屬/添加物較低。
# 缺鍵預設 0.4。P/Ge 給中低權重以利搜出 (Mn,Fe)2(P,Si)、La(Fe,Si,Ge)13。
ALPHA_PRIOR: dict[str, float] = {
    "Fe": 3.0, "Ni": 3.0, "Co": 1.5, "Cr": 1.0, "Mn": 0.6, "Cu": 0.5,
    "Mo": 0.5, "Si": 0.4, "Al": 0.4, "V": 0.4, "Gd": 1.2, "La": 1.0,
    "P": 0.6, "Ge": 0.6,
}


def alpha_vector() -> np.ndarray:
    """回傳按 ELEMENTS 對齊的 Dirichlet alpha 向量（單一真實來源，供 GA 共用）。"""
    return np.array([ALPHA_PRIOR.get(e, 0.4) for e in ELEMENTS], dtype=np.float64)


def hydrogenation_tc_shift_K(comp: np.ndarray) -> np.ndarray:
    """
    氫化 Tc 上修模型（缺陷 D8）：La(Fe,Si)13 吸氫後 Tc 由 ~200K 上修至 ~340–450K。

    本函數回傳「若將 La-Fe-Si(-Ge) 1:13 相氫化」對 Tc 的近似上移量 (K)，作為
    處理步驟的可選修正（非組成元素，故不入成分向量）。對非 1:13 相回傳 ~0。

    Args:
        comp: (N, NUM_ELEMENTS) 成分矩陣
    Returns:
        (N,) Tc 上移量 (K)，0–150K
    """
    la = comp[:, ELEMENTS.index("La")]
    fe = comp[:, ELEMENTS.index("Fe")]
    si = comp[:, ELEMENTS.index("Si")]
    ge = comp[:, ELEMENTS.index("Ge")]
    metalloid = si + 0.8 * ge
    la_fe_si = (
        np.exp(-((la - 0.07) ** 2) / (2 * 0.03 ** 2))
        * np.exp(-((metalloid - 0.12) ** 2) / (2 * 0.05 ** 2))
        * (1.0 / (1.0 + np.exp(-(fe - 0.5) * 20.0)))
    )
    return (150.0 * la_fe_si).astype(np.float32)


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
    gd = comp[:, ELEMENTS.index("Gd")]
    la = comp[:, ELEMENTS.index("La")]
    p  = comp[:, ELEMENTS.index("P")]
    ge = comp[:, ELEMENTS.index("Ge")]
    n  = comp.shape[0]

    # La-Fe-Si(-Ge) 1:13 相鄰近度（La≈7%, 類金屬(Si+Ge)≈12%, Fe>0.5 時最強）：
    # Ge 可替代 Si 進入 1:13 相（La(Fe,Si,Ge)13），效率略低於 Si。
    metalloid_lafesi = si + 0.8 * ge
    la_fe_si = (
        np.exp(-((la - 0.07) ** 2) / (2 * 0.03 ** 2))
        * np.exp(-((metalloid_lafesi - 0.12) ** 2) / (2 * 0.05 ** 2))
        * (1.0 / (1.0 + np.exp(-(fe - 0.5) * 20.0)))
    )

    # (Mn,Fe)2(P,Si) 一階相鄰近度（無稀土室溫 MCE 主力）：Mn≈1/3、(P+Si)≈1/3、需 Fe。
    # Tc 可調至近室溫，ΔS_M 為各體系最大。
    mn_fe_p_si = (
        np.exp(-((mn - 0.33) ** 2) / (2 * 0.12 ** 2))
        * np.exp(-(((p + si) - 0.33) ** 2) / (2 * 0.12 ** 2))
        * (1.0 / (1.0 + np.exp(-(fe - 0.10) * 20.0)))
    )

    # ── Tc (居禮溫度, K) ──────────────────────────────────────────────────────
    # Gd 為低 Tc 鐵磁體 (293K)，計入磁性基底
    mag_frac = fe + ni + co + gd

    # Base: 純元素線性混合（對二元合金準）
    base_tc = np.where(
        mag_frac > 0.05,
        (fe * 1043 + ni * 627 + co * 1400 + gd * 293) / np.maximum(mag_frac, 0.01),
        50.0,
    )

    # Slater-Pauling Fe-Co 協同增強（峰值 80 K，於 Fe=Co=0.5）
    fe_co_synergy = 80.0 * 4.0 * (fe * co) / (mag_frac ** 2 + 1e-6)

    # 抑制項：Cr/Mn 係數大幅降低（v1: 5500/4500 → v2: 1800/1200）
    cr_suppress = 1800 * np.power(cr, 1.2)
    # Mn 反鐵磁抑制；但在 (Mn,Fe)2(P,Si) 一階相中 Mn 為鐵磁耦合 → 由 proximity 解除抑制
    mn_suppress = 1200 * np.power(mn, 1.2) * (1.0 - 0.85 * mn_fe_p_si)

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
    # La-Fe-Si 1:13 相把 Tc 拉向 ~285K（近室溫 tunable，氫化可再上修，見 hydrogenation_tc_shift_K）
    tc = tc + la_fe_si * (285.0 - tc) * 0.7
    # (Mn,Fe)2(P,Si) 一階相把 Tc 拉向 ~290K（近室溫）
    tc = tc + mn_fe_p_si * (290.0 - tc) * 0.8
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
    # 每元素 Br 貢獻 (T)：Fe=1.40, Ni=0.60, Co=1.80 (Bozorth 1951, Cullity 2009)；
    # Gd=1.80（高 mu 室溫鐵磁，飽和極化代理）；其餘非磁性=0（含 P/Ge）。
    # 以字典建構（按 ELEMENTS 對齊），加元素只需補鍵，缺鍵預設 0。
    br_contrib = np.array([BR_ELEM_CONTRIB.get(e, 0.0) for e in ELEMENTS], dtype=np.float64)
    br_base = comp @ br_contrib
    mag_frac = fe + ni + co + gd
    # Fe-Co Slater-Pauling synergy: Hiperco50 Br=2.40T >> linear pred 1.60T
    fe_co_synergy_br = 0.80 * 4.0 * (fe * co) / (mag_frac ** 2 + 1e-6)
    # La-Fe-Si / Mn-Fe-P-Si 一階相 Fe 矩增強（Br≈1.0–1.4T）
    la_fe_si_br = 0.70 * la_fe_si
    mn_fe_p_si_br = 0.55 * mn_fe_p_si
    br = (br_base + fe_co_synergy_br + la_fe_si_br + mn_fe_p_si_br) * np.random.uniform(0.88, 1.12, n)
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

    # Dirichlet 偏置：以 ALPHA_PRIOR 按 ELEMENTS 對齊建構（單一真實來源）
    alpha_full = alpha_vector()

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
