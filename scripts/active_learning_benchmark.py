"""
主動學習回顧基準：在真實資料上檢驗「資訊性採樣是否真的勝過隨機」。
================================================================================

誠實檢驗 recommend_experiments 的前提。pool-based 模擬：小種子起步，每輪依策略
（不確定度 / 多樣性 / 隨機）加一批，retrain，量測試 R² vs 標註數。

⚠ 重要發現：在本 Br 資料集（266 筆、訊號弱、R² 天花板 ~0.58）上，**隨機採樣勝過
不確定度與多樣性採樣**——這是小/雜訊資料常見的主動學習失效模式（資訊性採樣專挑
離群/雜訊點）。故 recommend_experiments 宜定位為「模型壓力測試 / 找最不確定處」，
而非「以最少標註提升平均精度」——後者在此資料規模下隨機更好。

執行：python scripts/active_learning_benchmark.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))
from alloy_engine.data.elements import ELEMENTS, NUM_ELEMENTS
from alloy_engine.features.engineering import composition_to_features_np

MU = 11.654


def _parse(formula: str):
    v = np.zeros(NUM_ELEMENTS, dtype=np.float32)
    for el, n in re.findall(r"([A-Z][a-z]?)(\d*)", formula):
        if not el:
            continue
        if el not in ELEMENTS:
            return None
        v[ELEMENTS.index(el)] += float(n) if n else 1.0
    s = v.sum()
    return v / s if s > 0 else None


def simulate(X, y, strategy: str, seed: int,
             seed_size: int = 8, batch: int = 8, max_labels: int = 72) -> list[tuple[int, float]]:
    """pool-based AL 模擬，回傳 [(標註數, 測試R²)]。strategy: uncertainty/diversity/random。"""
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import r2_score
    Xs = (X - X.mean(0)) / (X.std(0) + 1e-9)
    rng = np.random.default_rng(seed)
    Xtr, Xte, ytr, yte, Xstr, _ = train_test_split(X, y, Xs, test_size=0.25, random_state=seed)
    lab = list(rng.choice(len(Xtr), seed_size, replace=False))
    pool = [i for i in range(len(Xtr)) if i not in lab]
    curve = []
    while True:
        rf = RandomForestRegressor(n_estimators=120, random_state=0, n_jobs=-1).fit(Xtr[lab], ytr[lab])
        curve.append((len(lab), float(r2_score(yte, rf.predict(Xte)))))
        if len(lab) >= max_labels or len(pool) < batch:
            break
        if strategy == "uncertainty":
            std = np.std([t.predict(Xtr[pool]) for t in rf.estimators_], axis=0)
            order = list(np.argsort(std)[::-1])
        elif strategy == "diversity":
            d = np.sqrt(((Xstr[pool][:, None, :] - Xstr[lab][None, :, :]) ** 2).sum(-1)).min(1)
            order = list(np.argsort(d)[::-1])
        else:  # random
            order = list(rng.permutation(len(pool)))
        take = [pool[i] for i in order[:batch]]
        lab += take
        pool = [i for i in pool if i not in take]
    return curve


def load_br_dataset(path: str | Path = "external/mp_fm_dataset.json"):
    data = json.loads(Path(path).read_text())
    comps, y = [], []
    for formula, mag, _eh in data:
        c = _parse(formula)
        if c is not None:
            comps.append(c); y.append(MU * mag)
    X = composition_to_features_np(np.array(comps), device=None)
    return X, np.array(y)


def main() -> None:
    import collections
    path = Path("external/mp_fm_dataset.json")
    if not path.exists():
        print("找不到 external/mp_fm_dataset.json；先跑 build_mp_magnetization_dataset.py")
        sys.exit(1)
    X, y = load_br_dataset(path)
    print("═" * 70)
    print(f" 主動學習回顧基準（真實 Br，n={len(y)}，8 seeds）")
    print("═" * 70)
    print(f"{'策略':<14}{'R²@n40':>9}{'final':>9}{'AUC':>9}")
    print("-" * 70)
    results = {}
    for strat in ("random", "uncertainty", "diversity"):
        agg = collections.defaultdict(list)
        for s in range(8):
            for n, r in simulate(X, y, strat, s):
                agg[n].append(r)
        pts = sorted(agg)
        n40 = min(pts, key=lambda n: abs(n - 40))
        auc = float(np.mean([np.mean(agg[n]) for n in pts]))
        results[strat] = (np.mean(agg[n40]), np.mean(agg[pts[-1]]), auc)
        print(f"{strat:<14}{results[strat][0]:>9.3f}{results[strat][1]:>9.3f}{auc:>9.3f}")
    print("-" * 70)
    best = max(results, key=lambda k: results[k][2])
    print(f" 最佳策略（AUC）：{best}")
    if best == "random":
        print(" ⚠ 隨機勝出：本資料規模小、訊號弱，資訊性採樣專挑離群點反而不利。")
        print("   → recommend_experiments 宜用於『模型壓力測試/找最不確定處』，")
        print("     而非『以最少標註提升平均精度』（後者此處隨機更好）。")
    print("═" * 70)


if __name__ == "__main__":
    main()
