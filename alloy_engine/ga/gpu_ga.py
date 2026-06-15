"""
GPU 向量化基因演算法

核心設計：
  - 族群、選擇、交配、突變全部在 GPU tensor 上完成，無 CPU 來回
  - 錦標賽選擇 (k=3) 完全向量化
  - BLX-α 交配：對連續變數比 SBX 簡單且效果接近
  - 高斯突變 + softmax 風格正規化：確保組成總和恆為 1
  - 菁英保留 (5%)：避免最佳解遺失

多目標適應度（加權懲罰法）：
  F = w_tc·exp(-(Tc-Tc*)²/2σ²) + w_hc·1/(1+Hc/20) + w_br·1/(1+2Br) + w_σ·Φ(σy)
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Callable, Optional

import torch

from alloy_engine.data.elements import ELEMENTS, NUM_ELEMENTS

# 元素索引（與 ELEMENTS 列表對齊）
_IDX = {e: i for i, e in enumerate(ELEMENTS)}

import numpy as np
from sklearn.cluster import KMeans

logger = logging.getLogger(__name__)

PredictFn = Callable[[torch.Tensor], dict[str, torch.Tensor]]
UncertaintyFn = Callable[[torch.Tensor, int], dict[str, torch.Tensor]]


def diversity_select(
    compositions: np.ndarray,
    fitness: np.ndarray,
    n_clusters: int = 5,
    pool_size: int = 1000,
    seed: int = 42,
) -> np.ndarray:
    """
    從 fitness 最高的 pool_size 個候選中做 K-means 聚類，
    每個 cluster 取 fitness 最高的 1 個，回傳 n_clusters 個索引
    （相對於原始 compositions 陣列）。

    Args:
        compositions : (N, NUM_ELEMENTS) 組成矩陣
        fitness      : (N,) 適應度分數
        n_clusters   : 聚類數 = 輸出候選數
        pool_size    : 先取 fitness 前幾名做聚類母體（避免對全族群跑 K-means）
        seed         : KMeans random_state

    Returns:
        selected_idx : (n_clusters,) int array，在原始陣列中的索引
    """
    n = len(fitness)
    pool_size = min(pool_size, n)

    # 取 fitness 前 pool_size 名
    pool_idx = np.argsort(fitness)[::-1][:pool_size]
    pool_comp = compositions[pool_idx]          # (pool_size, E)
    pool_fit  = fitness[pool_idx]               # (pool_size,)

    km = KMeans(n_clusters=n_clusters, random_state=seed, n_init="auto")
    labels = km.fit_predict(pool_comp)          # (pool_size,)

    selected_idx = []
    for k in range(n_clusters):
        mask = labels == k
        if not mask.any():
            continue
        # cluster 內 fitness 最高的那個（相對於 pool）
        best_in_cluster = np.where(mask)[0][pool_fit[mask].argmax()]
        selected_idx.append(pool_idx[best_in_cluster])   # 轉回原始索引

    return np.array(selected_idx)


class GPUGeneticAlgorithm:
    def __init__(
        self,
        predict_fn:           PredictFn,
        device:               torch.device,
        population_size:      int   = 200_000,
        target_tc_celsius:    float = 350.0,
        tc_tolerance:         float = 30.0,
        min_strength_mpa:     float = 400.0,
        max_hc:               float = 80.0,
        mutation_rate:        float = 0.15,
        mutation_sigma:       float = 0.06,
        elite_ratio:          float = 0.05,
        w_tc:                 float = 0.40,
        w_hc:                 float = 0.20,
        w_br:                 float = 0.15,
        w_strength:           float = 0.20,
        w_hc_constraint:      float = 0.05,
        enable_chemistry_constraints: bool = True,
        enable_uncertainty:   bool  = False,
        predict_fn_uncertainty: Optional[UncertaintyFn] = None,
        n_mc_samples:         int   = 20,
        uncertainty_weight:   float = 0.10,
        # ── thermomagnetic mode ───────────────────────────────────────────────
        mode:                 str   = "softmag",   # "softmag" | "thermomagnetic"
        w_tc_tm:              float = 0.25,        # v5.0: 0.30→0.25
        w_delta_M:            float = 0.20,        # v5.0: 0.30→0.20
        w_kappa:              float = 0.0,         # v5.0: 廢棄（用 efficiency 取代）
        w_strength_tm:        float = 0.05,        # v5.0: 0.10→0.05（薄片應用）
        w_tc_window:          float = 0.10,        # v5.0: 0.20→0.10
        delta_T_window:       float = 30.0,        # 循環半溫差 (K)
        min_strength_mpa_thermomagnetic: float = 150.0,
        # ── v5.0 新增參數 ─────────────────────────────────────────────────────
        w_delta_S:            float = 0.15,        # 磁熵變分數
        w_efficiency:         float = 0.15,        # 熱效率分數
        w_freq:               float = 0.10,        # 含磁滯品質頻率
        L_meters:             float = 1e-3,        # 元件特徵長度 (C1 修改)
        proximity_width_K:    float = 30.0,        # B2 修改：50K→30K
        # ── 整機級目標 (device-level objective) ───────────────────────────────
        w_device:             float = 0.0,         # 整機功率密度×效率分數權重（0=停用）
        device_B_applied_T:   float = 1.4,         # 整機設計：Halbach 永磁場
        device_regeneration:  float = 0.90,        # 整機設計：固態回熱效率
        device_utilization:   float = 0.30,        # 整機設計：迴線利用率
        device_L_meters:      float = 5e-4,        # 整機設計：薄板厚度（高頻）
        device_matrix:        Optional[str] = None,  # 複合基底 "Cu"/"Al"/"alpha-Fe"（None=裸相）
        # ── analysis flag ─────────────────────────────────────────────────
        min_delta_m_threshold: float = 0.20,       # delta_M 硬約束下限 (sweep 用)
    ) -> None:
        self.predict_fn       = predict_fn
        self.device           = device
        self.N                = population_size
        self.E                = NUM_ELEMENTS
        self.target_tc_celsius = target_tc_celsius
        self.target_tc_K      = target_tc_celsius + 273.15
        self.tc_tol           = tc_tolerance
        self.max_hc           = max_hc
        self.mut_rate         = mutation_rate
        self.mut_sigma        = mutation_sigma
        self.elite_ratio      = elite_ratio
        self.enable_chemistry_constraints = enable_chemistry_constraints
        self.enable_uncertainty     = enable_uncertainty
        self.predict_fn_uncertainty = predict_fn_uncertainty
        self.n_mc_samples           = n_mc_samples
        self.uncertainty_weight     = uncertainty_weight

        self.mode = mode
        if mode == "thermomagnetic":
            self.min_strength = min_strength_mpa_thermomagnetic
            self.tm_weights   = (w_tc_tm, w_delta_M, w_kappa, w_strength_tm, w_tc_window)
            self.delta_T_window = delta_T_window
            self.w_delta_S      = w_delta_S
            self.w_efficiency   = w_efficiency
            self.w_freq         = w_freq
            self.L_meters       = L_meters
            self.proximity_width_K = proximity_width_K
            self.min_delta_m_threshold = min_delta_m_threshold
            self.w_device       = w_device
            self.device_B_applied_T  = device_B_applied_T
            self.device_regeneration = device_regeneration
            self.device_utilization  = device_utilization
            self.device_L_meters     = device_L_meters
            self.device_matrix       = device_matrix
        else:
            self.min_strength = min_strength_mpa
            self.weights      = (w_tc, w_hc, w_br, w_strength, w_hc_constraint)

        self.population = self._init_population()
        self.history: dict[str, list[float]] = defaultdict(list)

    # ── 初始化 ────────────────────────────────────────────────────────────────
    def _init_population(self) -> torch.Tensor:
        # 與合成資料共用同一 Dirichlet 先驗（按 ELEMENTS 對齊，含 P/Ge）
        from alloy_engine.data.synthetic import alpha_vector
        alpha = torch.tensor(
            alpha_vector(), dtype=torch.float32, device=self.device,
        ).expand(self.N, -1)
        return torch.distributions.Dirichlet(alpha).sample()

    # ── 化學可合成性懲罰 ──────────────────────────────────────────────────────
    def _chemistry_penalty(self, pop: torch.Tensor) -> torch.Tensor:
        """
        軟約束懲罰（乘法，1.0 = 無懲罰）：

        規則                           閾值      懲罰係數   物理原因
        (Si+Al) > 0.20               軟：>0.20  0.60      DO₃ 脆相
        Mo > 0.08                    軟：>0.08  0.70      μ 相析出
        Cr > 0.30                    軟：>0.30  0.75      σ 相析出
        (Fe+Ni+Co+Gd) < 0.40         硬：<0.40  0.50      鐵磁基底不足
        (Gd+La) 氧化/處理            線性      ≤0.25     稀土活性、易氧化（D9）
        稀土 ×(Fe+Si) 一階脆裂       交互      ≤0.20     La(Fe,Si)₁₃/Gd₅SiGe 脆相（D9）

        超過閾值越多，懲罰越重（線性比例）。稀土懲罰為「漸進」而非硬切——
        反映惰性氣氛/鈍化/黏結成型的製造成本，但保留有效 MCE 材料
        （純 Gd ~0.75、La-Fe-Si ~0.96 的可製造分數仍具競爭力）。
        """
        fe  = pop[:, _IDX["Fe"]]
        ni  = pop[:, _IDX["Ni"]]
        co  = pop[:, _IDX["Co"]]
        cr  = pop[:, _IDX["Cr"]]
        mo  = pop[:, _IDX["Mo"]]
        si  = pop[:, _IDX["Si"]]
        al  = pop[:, _IDX["Al"]]
        p   = pop[:, _IDX["P"]]
        ge  = pop[:, _IDX["Ge"]]

        penalty = torch.ones(pop.shape[0], device=self.device)

        # (Si+Al+P+Ge) > 0.20 → 類金屬脆相風險（DO₃ / 一階 (Mn,Fe)2(P,Si) 脆裂，需黏結成型）
        # P/Ge 一併計入：解鎖的一階 MCE 雖有效，但確實脆、可製造性應 down-rank（D8/D9 同理）
        si_al = si + al + p + ge
        excess_si_al = torch.clamp(si_al - 0.20, min=0.0) / 0.20   # 超出比例
        penalty = penalty * (1.0 - 0.40 * torch.clamp(excess_si_al, max=1.0))

        # Mo > 0.08 → μ 相析出風險
        excess_mo = torch.clamp(mo - 0.08, min=0.0) / 0.08
        penalty = penalty * (1.0 - 0.30 * torch.clamp(excess_mo, max=1.0))

        # Cr > 0.30 → σ 相析出風險
        excess_cr = torch.clamp(cr - 0.30, min=0.0) / 0.30
        penalty = penalty * (1.0 - 0.25 * torch.clamp(excess_cr, max=1.0))

        # (Fe+Ni+Co+Gd) < 0.40 → 鐵磁基底不足（嚴重懲罰）；Gd 為室溫鐵磁體
        gd = pop[:, _IDX["Gd"]]
        mag_base = fe + ni + co + gd
        deficit_mag = torch.clamp(0.40 - mag_base, min=0.0) / 0.40
        penalty = penalty * (1.0 - 0.50 * torch.clamp(deficit_mag, max=1.0))

        # ── 稀土可製造性懲罰（D9）──────────────────────────────────
        # 稀土（Gd/La）活性高、易氧化；一階磁熱相（La-Fe-Si、Gd₅SiGe）脆裂，
        # 常需氫化/鍍層/黏結成型 → 過去「可製造性」被高估。以漸進懲罰反映
        # 真實處理成本，但不排除有效 MCE 材料（純 Gd、La-Fe-Si 仍保留可製造分）。
        la = pop[:, _IDX["La"]]
        re_total = gd + la
        # (a) 氧化/處理：稀土含量線性懲罰，純稀土上限罰 0.25（保留 0.75）
        penalty = penalty * (1.0 - 0.25 * torch.clamp(re_total, max=1.0))
        # (b) 一階脆裂：稀土與 (Fe+Si) 共存 → La(Fe,Si)₁₃/Gd₅SiGe 型脆相，需黏結
        fe_si = fe + si
        brittle = torch.clamp(re_total - 0.03, min=0.0) * torch.clamp(fe_si - 0.50, min=0.0)
        penalty = penalty * (1.0 - 0.20 * torch.clamp(brittle * 6.0, max=1.0))

        # Cu > 20% → 熱磁模式懲罰（Cu 非磁性，稀釋磁矩；工業熱磁合金上限 ~10%）
        if self.mode == "thermomagnetic":
            cu = pop[:, _IDX["Cu"]]
            cu_excess = torch.clamp(cu - 0.20, min=0.0)
            cu_penalty = torch.exp(-cu_excess * 8.0)
            penalty = penalty * cu_penalty

        return penalty  # (N,)，範圍 (0, 1]

    # ── 適應度（軟磁 mode）────────────────────────────────────────────────────
    def _fitness_softmag(
        self, pop: torch.Tensor, preds: dict, tc_std=None
    ) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
        tc  = preds["Tc"]
        hc  = preds["Hc"]
        br  = preds["Br"]
        st  = preds["strength"]

        tc_score = torch.exp(-((tc - self.target_tc_K) ** 2) / (2 * self.tc_tol ** 2))
        hc_score = 1.0 / (1.0 + hc / 20.0)
        br_score = 1.0 / (1.0 + br * 2.0)
        strength_score = torch.where(
            st >= self.min_strength,
            torch.ones_like(st),
            torch.exp((st - self.min_strength) / 100.0),
        )
        hc_constraint = torch.where(
            hc <= self.max_hc,
            torch.ones_like(hc),
            torch.exp((self.max_hc - hc) / 30.0),
        )

        w_tc, w_hc, w_br, w_st, w_hcc = self.weights
        F_base = (
            w_tc  * tc_score
            + w_hc  * hc_score
            + w_br  * br_score
            + w_st  * strength_score
            + w_hcc * hc_constraint
        )

        if self.enable_chemistry_constraints:
            F_base = F_base * self._chemistry_penalty(pop)

        if self.enable_uncertainty and tc_std is not None:
            uncertainty_score = torch.sigmoid((23.0 - tc_std) / 8.0)
            F_total = F_base * (1.0 - self.uncertainty_weight
                                + self.uncertainty_weight * uncertainty_score)
        else:
            F_total = F_base

        zero_std = torch.zeros_like(tc) if tc_std is None else tc_std
        return F_total, {"tc": tc, "hc": hc, "br": br, "strength": st,
                         "tc_std": zero_std}

    # ── 適應度（熱磁 mode）────────────────────────────────────────────────────
    def _fitness_thermomagnetic(
        self, pop: torch.Tensor, preds: dict
    ) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
        from alloy_engine.thermomagnetic.properties import (
            thermal_conductivity_estimate,
            magnetic_thermodynamic_score,
            cp_estimate_specific,
            delta_s_m_estimate,
            thermal_efficiency_score,
            cycle_frequency_estimate,
            quality_frequency_score,
        )

        tc_K = preds["Tc"]
        hc   = preds["Hc"]
        br   = preds["Br"]   # Br 作為 Ms 代理（Spearman r=0.84 已驗證）
        st   = preds["strength"]

        thermo = magnetic_thermodynamic_score(
            Ms=br,
            Tc_K=tc_K,
            T_target_C=self.target_tc_celsius,
            delta_T_window=self.delta_T_window,
        )
        kappa = thermal_conductivity_estimate(pop)

        tc_C = tc_K - 273.15
        tc_hit = torch.exp(-((tc_C - self.target_tc_celsius) ** 2)
                           / (2 * self.tc_tol ** 2))

        # delta_M normalize：基準 0.5 T（Permalloy 工業循環實測值）+ power 0.7 增敏
        delta_M_ratio = torch.clamp(thermo["delta_M"] / 0.5, 0.0, 1.0)
        delta_M_score = delta_M_ratio ** 0.7

        strength_score = torch.where(
            st >= self.min_strength,
            torch.ones_like(st),
            torch.exp((st - self.min_strength) / 80.0),
        )

        # ── v5.0 新增物理量 ───────────────────────────────────────────────────
        cp_spec = cp_estimate_specific(pop)                           # J/(kg·K)
        delta_S = delta_s_m_estimate(
            pop, tc_K, self.target_tc_celsius, Ms=br,
            proximity_width_K=self.proximity_width_K,
            H_external_T=1.0,       # 典型 NdFeB 永磁場強
            field_scaling_1T=0.05,  # Fe-Ni 系校準 (Tishin 2003)
        )                                                              # J/(kg·K)

        # ΔS_M normalize：6.5 J/(kg·K) 為 cap
        # 校準：全族群高 fitness 子集飽和率 37%（30-50% 區間），5.0 太低故調高至 6.5
        # 參考：Gd@1T ΔS_M≈10 J/(kg·K)，Fe 系優秀合金 ≈ 4-6 J/(kg·K)
        delta_S_score = torch.clamp(delta_S / 6.5, 0.0, 1.0)

        eff_score = thermal_efficiency_score(delta_S, cp_spec)

        f_Hz      = cycle_frequency_estimate(pop, kappa, cp_spec, L_meters=self.L_meters)
        f_quality = quality_frequency_score(f_Hz, Hc=hc, Br=br, alpha_loss=0.001)
        # cap=15 Hz：基於全族群 f_quality 分布（p95=13.4 Hz，mean=9.6 Hz）
        # 避免 cap=1000 導致全族群廢解（100% <0.05）
        freq_score = torch.clamp(f_quality / 15.0, 0.0, 1.0)

        w_tc, w_dM, _w_k, w_st, w_win = self.tm_weights
        F_base = (
            w_tc              * tc_hit
            + w_dM            * delta_M_score
            + self.w_delta_S  * delta_S_score
            + self.w_efficiency * eff_score
            + self.w_freq     * freq_score
            + w_win           * thermo["tc_window_score"]
            + w_st            * strength_score
        )

        # ── 整機級目標：直接最佳化發電機功率密度 × 效率 ──────────────────────────
        device_info: dict[str, torch.Tensor] = {}
        if self.w_device > 0.0:
            from alloy_engine.thermomagnetic.device_score import (
                device_power_efficiency_score,
            )
            matrix_obj = None
            if self.device_matrix is not None:
                from alloy_engine.thermomagnetic.composite import MATRIX_MATERIALS
                matrix_obj = MATRIX_MATERIALS[self.device_matrix]
            dev = device_power_efficiency_score(
                pop, Ms=br, Tc_K=tc_K, Hc=hc, T_target_C=self.target_tc_celsius,
                B_applied_T=self.device_B_applied_T,
                cycle_utilization=self.device_utilization,
                regenerator_effectiveness=self.device_regeneration,
                delta_T_window=self.delta_T_window,
                L_meters=self.device_L_meters,
                proximity_width_K=self.proximity_width_K,
                H_external_T=self.device_B_applied_T,
                matrix=matrix_obj,
            )
            F_base = F_base + self.w_device * dev["device_score"]
            device_info = {
                "device_score":       dev["device_score"],
                "device_eta":         dev["eta"],
                "device_power_W_m3":  dev["power_density_W_m3"],
            }
            if "best_matrix_fraction" in dev:
                device_info["device_matrix_frac"] = dev["best_matrix_fraction"]

        # 硬約束：delta_M < min_delta_m_threshold 視為熱磁應用不可用
        thr = self.min_delta_m_threshold
        low_dM_penalty = torch.where(
            thermo["delta_M"] < thr,
            (thermo["delta_M"] / (thr + 1e-6)) ** 2,
            torch.ones_like(thermo["delta_M"]),
        )
        F_base = F_base * low_dM_penalty

        if self.enable_chemistry_constraints:
            F_base = F_base * self._chemistry_penalty(pop)

        return F_base, {
            "tc":              tc_K,
            "hc":              hc,
            "br":              br,
            "strength":        st,
            "tc_std":          torch.zeros_like(tc_K),
            "kappa":           kappa,
            "cp":              cp_spec,
            "delta_M":         thermo["delta_M"],
            "delta_S_M":       delta_S,
            "cycle_frequency": f_Hz,
            "quality_freq":    f_quality,
            "M_at_low":        thermo["M_at_low"],
            "M_at_high":       thermo["M_at_high"],
            "tc_window_score": thermo["tc_window_score"],
            **device_info,
        }

    # ── 適應度（dispatch）─────────────────────────────────────────────────────
    @torch.no_grad()
    def fitness(
        self, pop: torch.Tensor
    ) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
        if self.enable_uncertainty and self.predict_fn_uncertainty is not None:
            preds_mc = self.predict_fn_uncertainty(pop, self.n_mc_samples)
            preds = {
                "Tc": preds_mc["Tc_mean"], "Hc": preds_mc["Hc_mean"],
                "Br": preds_mc["Br_mean"], "strength": preds_mc["strength_mean"],
            }
            tc_std = preds_mc["Tc_std"]
        else:
            preds  = self.predict_fn(pop)
            tc_std = None

        if self.mode == "thermomagnetic":
            return self._fitness_thermomagnetic(pop, preds)
        else:
            return self._fitness_softmag(pop, preds, tc_std)

    # ── 遺傳算子 ──────────────────────────────────────────────────────────────
    def _tournament_select(
        self, fitness: torch.Tensor, k: int = 3
    ) -> tuple[torch.Tensor, torch.Tensor]:
        N = self.N
        idx_a = torch.randint(0, N, (N, k), device=self.device)
        idx_b = torch.randint(0, N, (N, k), device=self.device)
        wa = idx_a.gather(1, fitness[idx_a].argmax(1, keepdim=True)).squeeze(1)
        wb = idx_b.gather(1, fitness[idx_b].argmax(1, keepdim=True)).squeeze(1)
        return wa, wb

    def _crossover(self, A: torch.Tensor, B: torch.Tensor) -> torch.Tensor:
        u = torch.rand_like(A)
        child = u * A + (1 - u) * B
        diff  = (A - B).abs()
        child = child + (torch.rand_like(A) - 0.5) * 0.1 * diff
        child = torch.clamp(child, min=0.0)
        return child / (child.sum(1, keepdim=True) + 1e-10)

    def _mutate(self, pop: torch.Tensor) -> torch.Tensor:
        mask  = (torch.rand_like(pop) < self.mut_rate).float()
        noise = torch.randn_like(pop) * self.mut_sigma
        out   = torch.clamp(pop + mask * noise, min=0.0)
        return out / (out.sum(1, keepdim=True) + 1e-10)

    # ── 單步進化 ──────────────────────────────────────────────────────────────
    def step(self) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
        fit, info = self.fitness(self.population)

        n_elite  = int(self.N * self.elite_ratio)
        elite_idx = fit.argsort(descending=True)[:n_elite]
        elites   = self.population[elite_idx].clone()

        pa, pb   = self._tournament_select(fit)
        offspring = self._crossover(self.population[pa], self.population[pb])
        offspring = self._mutate(offspring)
        offspring[:n_elite] = elites
        self.population = offspring

        bi = fit.argmax()
        self.history["best_fitness"].append(fit[bi].item())
        self.history["mean_fitness"].append(fit.mean().item())
        self.history["best_tc_C"].append(info["tc"][bi].item() - 273.15)
        self.history["best_strength"].append(info["strength"][bi].item())
        self.history["best_hc"].append(info["hc"][bi].item())
        self.history["best_br"].append(info["br"][bi].item())
        self.history["best_tc_std"].append(info["tc_std"][bi].item())
        if "delta_M" in info:
            self.history["best_delta_M"].append(info["delta_M"][bi].item())
            self.history["best_kappa"].append(info["kappa"][bi].item())
        if "delta_S_M" in info:
            self.history["best_delta_S_M"].append(info["delta_S_M"][bi].item())
            self.history["best_cp"].append(info["cp"][bi].item())
            self.history["best_freq"].append(info["cycle_frequency"][bi].item())
        return fit, info

    # ── 主迴圈 ────────────────────────────────────────────────────────────────
    def run(
        self, n_gen: int = 150, verbose: bool = True
    ) -> tuple[torch.Tensor, torch.Tensor, dict[str, torch.Tensor]]:
        for g in range(n_gen):
            fit, info = self.step()
            if verbose and (g + 1) % 10 == 0:
                bi = fit.argmax()
                logger.info(
                    "Gen %3d | F=%.4f | Tc=%6.1f°C | Hc=%6.2f | Br=%.2fT | σy=%4.0fMPa",
                    g + 1, fit[bi].item(),
                    info["tc"][bi].item() - 273.15,
                    info["hc"][bi].item(),
                    info["br"][bi].item(),
                    info["strength"][bi].item(),
                )
        return self.population, fit, info
