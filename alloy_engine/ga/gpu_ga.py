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
    ) -> None:
        self.predict_fn       = predict_fn
        self.device           = device
        self.N                = population_size
        self.E                = NUM_ELEMENTS
        self.target_tc_K      = target_tc_celsius + 273.15
        self.tc_tol           = tc_tolerance
        self.min_strength     = min_strength_mpa
        self.max_hc           = max_hc
        self.mut_rate         = mutation_rate
        self.mut_sigma        = mutation_sigma
        self.elite_ratio      = elite_ratio
        self.weights          = (w_tc, w_hc, w_br, w_strength, w_hc_constraint)
        self.enable_chemistry_constraints = enable_chemistry_constraints
        self.enable_uncertainty     = enable_uncertainty
        self.predict_fn_uncertainty = predict_fn_uncertainty
        self.n_mc_samples           = n_mc_samples
        self.uncertainty_weight     = uncertainty_weight

        self.population = self._init_population()
        self.history: dict[str, list[float]] = defaultdict(list)

    # ── 初始化 ────────────────────────────────────────────────────────────────
    def _init_population(self) -> torch.Tensor:
        alpha = torch.tensor(
            [3.0, 3.0, 1.5, 1.0, 0.6, 0.5, 0.5, 0.4, 0.4, 0.4],
            device=self.device,
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
        (Fe+Ni+Co) < 0.40            硬：<0.40  0.50      鐵磁基底不足

        超過閾值越多，懲罰越重（線性比例）。
        """
        fe  = pop[:, _IDX["Fe"]]
        ni  = pop[:, _IDX["Ni"]]
        co  = pop[:, _IDX["Co"]]
        cr  = pop[:, _IDX["Cr"]]
        mo  = pop[:, _IDX["Mo"]]
        si  = pop[:, _IDX["Si"]]
        al  = pop[:, _IDX["Al"]]

        penalty = torch.ones(pop.shape[0], device=self.device)

        # (Si + Al) > 0.20 → DO₃ 脆相風險
        si_al = si + al
        excess_si_al = torch.clamp(si_al - 0.20, min=0.0) / 0.20   # 超出比例
        penalty = penalty * (1.0 - 0.40 * torch.clamp(excess_si_al, max=1.0))

        # Mo > 0.08 → μ 相析出風險
        excess_mo = torch.clamp(mo - 0.08, min=0.0) / 0.08
        penalty = penalty * (1.0 - 0.30 * torch.clamp(excess_mo, max=1.0))

        # Cr > 0.30 → σ 相析出風險
        excess_cr = torch.clamp(cr - 0.30, min=0.0) / 0.30
        penalty = penalty * (1.0 - 0.25 * torch.clamp(excess_cr, max=1.0))

        # (Fe+Ni+Co) < 0.40 → 鐵磁基底不足（嚴重懲罰）
        mag_base = fe + ni + co
        deficit_mag = torch.clamp(0.40 - mag_base, min=0.0) / 0.40
        penalty = penalty * (1.0 - 0.50 * torch.clamp(deficit_mag, max=1.0))

        return penalty  # (N,)，範圍 (0, 1]

    # ── 適應度 ────────────────────────────────────────────────────────────────
    @torch.no_grad()
    def fitness(
        self, pop: torch.Tensor
    ) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
        if self.enable_uncertainty and self.predict_fn_uncertainty is not None:
            preds = self.predict_fn_uncertainty(pop, self.n_mc_samples)
            tc  = preds["Tc_mean"]
            hc  = preds["Hc_mean"]
            br  = preds["Br_mean"]
            st  = preds["strength_mean"]
            tc_std = preds["Tc_std"]
        else:
            preds = self.predict_fn(pop)
            tc  = preds["Tc"]
            hc  = preds["Hc"]
            br  = preds["Br"]
            st  = preds["strength"]
            tc_std = None

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
            # sigmoid mapping: median std=23K → score=0.5; std=10 → ≈0.85; std=40 → ≈0.15
            uncertainty_score = torch.sigmoid((23.0 - tc_std) / 8.0)
            F_total = F_base * (1.0 - self.uncertainty_weight
                                + self.uncertainty_weight * uncertainty_score)
        else:
            F_total = F_base

        info = {
            "tc": tc, "hc": hc, "br": br, "strength": st,
            "tc_std": tc_std if tc_std is not None else torch.zeros_like(tc),
        }
        return F_total, info

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
