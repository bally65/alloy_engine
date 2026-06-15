"""
真實 Br 模型：以 Materials Project DFT 磁化訓練的 Br_0K 預測器。
================================================================================

動機：合成 Br 對真實 MP 磁化 R²≈0.006（無預測力），且線性再校準無效（無相關可縮放）。
與 Tc 相同，唯有「以真實資料訓練」才有預測力——本模組以 MP 的 97 個本元素空間 FM
化合物訓練 GBR，交叉驗證 R²≈0.56、MAE≈0.33T（vs 合成 ~0）。

工作溫度 Br = predict_Br0K(comp) × m(T/Tc)（用 magnetization_correction 的平均場，
配真實 Tc 模型）。資料由 build_mp_magnetization_dataset.py 抓取（git-ignored）。
"""
from __future__ import annotations

import json
import pickle
import re
from pathlib import Path

import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import KFold, cross_val_predict
from sklearn.metrics import r2_score, mean_absolute_error

from alloy_engine.data.elements import ELEMENTS, NUM_ELEMENTS
from alloy_engine.features.engineering import composition_to_features_np

MU_B_VOL_TO_TESLA = 11.654


def parse_formula(formula: str) -> np.ndarray | None:
    """把 MP 化學式（如 'Fe5Co3'）解析成本 14 元素空間的原子分率向量；含外元素回 None。"""
    v = np.zeros(NUM_ELEMENTS, dtype=np.float32)
    for el, n in re.findall(r"([A-Z][a-z]?)(\d*)", formula):
        if not el:
            continue
        if el not in ELEMENTS:
            return None
        v[ELEMENTS.index(el)] += float(n) if n else 1.0
    s = v.sum()
    return v / s if s > 0 else None


def load_dataset(path: str | Path = "external/mp_fm_dataset.json") -> tuple[np.ndarray, np.ndarray]:
    """載入 MP FM 資料集 → (compositions (N,14), Br_0K (N,) in Tesla)。"""
    data = json.loads(Path(path).read_text())
    comps, br = [], []
    for formula, mag, _eah in data:
        c = parse_formula(formula)
        if c is not None:
            comps.append(c)
            br.append(MU_B_VOL_TO_TESLA * mag)
    return np.array(comps), np.array(br)


class RealBrModel:
    """MP DFT 磁化訓練的真實 Br_0K 預測器（GBR）；附交叉驗證 R²/MAE。"""

    def __init__(self, model: GradientBoostingRegressor, cv_r2: float, cv_mae: float):
        self.model = model
        self.cv_r2 = cv_r2
        self.cv_mae = cv_mae   # 驗證過的誤差條（T）

    @classmethod
    def train(cls, comps: np.ndarray, br: np.ndarray, seed: int = 0) -> "RealBrModel":
        X = composition_to_features_np(comps.astype(np.float32), device=None)
        kf = KFold(5, shuffle=True, random_state=seed)
        gbr = GradientBoostingRegressor(n_estimators=200, max_depth=2,
                                        learning_rate=0.05, random_state=seed)
        pred = cross_val_predict(gbr, X, br, cv=kf)
        cv_r2 = float(r2_score(br, pred))
        cv_mae = float(mean_absolute_error(br, pred))
        gbr.fit(X, br)   # 最終模型用全資料
        return cls(gbr, cv_r2, cv_mae)

    def predict(self, compositions: np.ndarray) -> np.ndarray:
        """回傳 Br_0K (T)；compositions (N,14) 原子分率。"""
        X = composition_to_features_np(np.asarray(compositions, dtype=np.float32), device=None)
        return self.model.predict(X)

    def save(self, path: str | Path) -> None:
        Path(path).write_bytes(pickle.dumps(
            {"model": self.model, "cv_r2": self.cv_r2, "cv_mae": self.cv_mae}))

    @classmethod
    def load(cls, path: str | Path) -> "RealBrModel":
        d = pickle.loads(Path(path).read_bytes())
        return cls(d["model"], d["cv_r2"], d["cv_mae"])
