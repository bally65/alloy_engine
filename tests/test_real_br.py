"""真實 Br 模型測試（CI-safe，不依賴 MP 資料集）。"""
import numpy as np
import pytest

from alloy_engine.data.elements import ELEMENTS, NUM_ELEMENTS
from alloy_engine.models.real_br import parse_formula, RealBrModel


class TestParseFormula:
    def test_simple(self):
        v = parse_formula("Fe5Co3")
        assert v is not None and abs(v.sum() - 1.0) < 1e-5
        assert v[ELEMENTS.index("Fe")] == pytest.approx(5 / 8)
        assert v[ELEMENTS.index("Co")] == pytest.approx(3 / 8)

    def test_single_element(self):
        v = parse_formula("Fe")
        assert v[ELEMENTS.index("Fe")] == pytest.approx(1.0)

    def test_outside_space_returns_none(self):
        assert parse_formula("Fe2O3") is None   # O 不在元素空間


class TestRealBrModel:
    def _data(self, n=60):
        rng = np.random.default_rng(0)
        comps = rng.dirichlet(np.ones(NUM_ELEMENTS), size=n).astype(np.float32)
        # 造一個與 Fe 含量相關的目標，確保模型學得到訊號
        br = 2.0 * comps[:, ELEMENTS.index("Fe")] + rng.normal(0, 0.05, n)
        return comps, br

    def test_train_predict_roundtrip(self, tmp_path):
        comps, br = self._data()
        m = RealBrModel.train(comps, br)
        assert isinstance(m.cv_r2, float) and isinstance(m.cv_mae, float)
        pred = m.predict(comps)
        assert pred.shape == (len(br),)
        p = tmp_path / "br.pkl"
        m.save(p)
        m2 = RealBrModel.load(p)
        assert np.allclose(m2.predict(comps), pred)

    def test_learns_signal(self):
        # 目標設為某 Oliynyk 特徵的函數 → GBR 應能還原（CV R² 明顯為正）
        from alloy_engine.features.engineering import composition_to_features_np
        rng = np.random.default_rng(0)
        comps = rng.dirichlet(np.ones(NUM_ELEMENTS), size=120).astype(np.float32)
        X = composition_to_features_np(comps, device=None)
        f0 = (X[:, 0] - X[:, 0].mean()) / (X[:, 0].std() + 1e-9)
        br = 3.0 * f0 + rng.normal(0, 0.1, 120)
        m = RealBrModel.train(comps, br)
        assert m.cv_r2 > 0.3
