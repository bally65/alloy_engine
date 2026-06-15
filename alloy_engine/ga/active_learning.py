"""
主動學習 / 實驗設計（DoE）：推薦「先合成哪些合金」以最大化驗證/改進模型。
================================================================================

橋接計算與實體實驗（見 docs/MEASUREMENT_PROTOCOL.md）：給定候選成分池與已校準的
bundle，依「實驗價值」排序並選出**多樣化的一批**最值得先做的樣品。

實驗價值（acquisition）= 加權組合：
  1. 模型不確定度（MC-Dropout 在 Tc/Br 的標準差）——模型越不確定，量測學到越多。
  2. 新穎度（在特徵空間距訓練資料越遠 = 外推 = 資訊量大；需提供 reference_feats）。
批次選擇用 greedy farthest-point（max-min 距離）確保選出的樣品彼此分散，避免做 k 個
幾乎相同的實驗。
"""
from __future__ import annotations

import torch

from alloy_engine.features.engineering import composition_to_features_torch


def _minmax(x: torch.Tensor) -> torch.Tensor:
    """正規化到 [0,1]；常數向量回 0。"""
    lo, hi = x.min(), x.max()
    return (x - lo) / (hi - lo) if hi > lo else torch.zeros_like(x)


@torch.no_grad()
def composition_uncertainty(
    bundle, comps: torch.Tensor, n_mc: int = 30,
    props: tuple[str, ...] = ("Tc", "Br"),
) -> dict[str, torch.Tensor]:
    """以 MC-Dropout 回傳各性質的預測標準差 {prop: (N,)}。"""
    res = bundle.predict_properties_with_uncertainty(comps, n_samples=n_mc)
    return {p: res[f"{p}_std"] for p in props}


@torch.no_grad()
def novelty_scores(feats: torch.Tensor, reference_feats: torch.Tensor | None) -> torch.Tensor:
    """每候選到 reference（訓練資料）特徵的最小距離；無 reference 回 0。"""
    if reference_feats is None or reference_feats.numel() == 0:
        return torch.zeros(feats.shape[0], device=feats.device)
    d = torch.cdist(feats, reference_feats.to(feats.device))   # (N, M)
    return d.min(dim=1).values


@torch.no_grad()
def acquisition_scores(
    bundle, comps: torch.Tensor,
    *, w_uncertainty: float = 1.0, w_novelty: float = 0.5,
    reference_feats: torch.Tensor | None = None,
    props: tuple[str, ...] = ("Tc", "Br"), n_mc: int = 30,
) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
    """
    每候選的實驗價值分數（越高越值得先做）+ 拆解。
    分數 = w_unc·(各性質正規化 std 之和) + w_novelty·(正規化新穎度)。
    """
    feats = composition_to_features_torch(comps, bundle.element_matrix_t)
    stds = composition_uncertainty(bundle, comps, n_mc=n_mc, props=props)
    unc = sum(_minmax(stds[p]) for p in props) / len(props)
    nov = _minmax(novelty_scores(feats, reference_feats))
    score = w_uncertainty * unc + w_novelty * nov
    breakdown = {"uncertainty": unc, "novelty": nov, **{f"{p}_std": stds[p] for p in props}}
    return score, breakdown


@torch.no_grad()
def select_diverse_batch(
    feats: torch.Tensor, scores: torch.Tensor, k: int, pool_frac: float = 0.25,
) -> list[int]:
    """
    批次主動學習：先取分數前 pool 名，再用 greedy farthest-point 選 k 個彼此最分散者。
    避免選出 k 個幾乎相同的高分候選（資訊冗餘）。
    """
    n = feats.shape[0]
    k = min(k, n)
    pool_size = min(n, max(k, int(pool_frac * n)))
    pool = torch.topk(scores, pool_size).indices            # 原始索引
    pf = feats[pool]
    chosen_local = [0]                                       # 池內位置；先取最高分
    while len(chosen_local) < k:
        sel = pf[chosen_local]                              # (s, F)
        d = torch.cdist(pf, sel).min(dim=1).values          # 每池候選到已選的最近距離
        d[chosen_local] = -1.0                              # 已選排除
        chosen_local.append(int(d.argmax().item()))
    return [int(pool[i].item()) for i in chosen_local]


@torch.no_grad()
def recommend_experiments(
    bundle, comps: torch.Tensor, k: int = 5,
    *, reference_feats: torch.Tensor | None = None,
    w_uncertainty: float = 1.0, w_novelty: float = 0.5, n_mc: int = 30,
) -> list[dict]:
    """回傳 k 個推薦先做的實驗（成分索引 + 預測 + 不確定度 + 分數 + 理由）。"""
    feats = composition_to_features_torch(comps, bundle.element_matrix_t)
    score, bd = acquisition_scores(
        bundle, comps, w_uncertainty=w_uncertainty, w_novelty=w_novelty,
        reference_feats=reference_feats, n_mc=n_mc,
    )
    idxs = select_diverse_batch(feats, score, k)
    preds = bundle.predict_properties(comps)
    out = []
    for i in idxs:
        reasons = []
        if bd["uncertainty"][i] > 0.6:
            reasons.append("模型不確定度高")
        if reference_feats is not None and bd["novelty"][i] > 0.6:
            reasons.append("成分新穎（外推）")
        if not reasons:
            reasons.append("分散批次代表")
        out.append({
            "index": i,
            "Tc_C": float(preds["Tc"][i]) - 273.15,
            "Br_T": float(preds["Br"][i]),
            "Tc_std_K": float(bd["Tc_std"][i]),
            "Br_std_T": float(bd["Br_std"][i]),
            "acquisition": float(score[i]),
            "rationale": "；".join(reasons),
        })
    return out
