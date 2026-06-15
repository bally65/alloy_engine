"""主動學習 / DoE 層測試（CI-safe，合成 bundle，不依賴 checkpoint）。"""
import numpy as np
import torch

from alloy_engine.data.elements import NUM_ELEMENTS, get_element_matrix
from alloy_engine.models.surrogate import SurrogateBundle, PropertyMLP
from alloy_engine.ga import active_learning as al

DEVICE = torch.device("cpu")
FEAT_DIM = get_element_matrix().shape[1] * 4


def _scaler():
    return (np.zeros(FEAT_DIM, dtype=np.float32), np.ones(FEAT_DIM, dtype=np.float32), 0.0, 1.0, False)


def _bundle():
    em = torch.from_numpy(get_element_matrix()).to(DEVICE)
    mk = lambda: PropertyMLP(FEAT_DIM, dropout_rate=0.1)
    return SurrogateBundle(mlp_tc=mk(), mlp_hc=mk(), mlp_br=mk(), mlp_strength=mk(),
                           sc_tc=_scaler(), sc_hc=_scaler(), sc_br=_scaler(), sc_strength=_scaler(),
                           device=DEVICE, element_matrix_t=em)


def _comp(n=40):
    return torch.distributions.Dirichlet(torch.ones(NUM_ELEMENTS)).sample((n,))


class TestActiveLearning:
    def test_uncertainty_positive(self):
        stds = al.composition_uncertainty(_bundle(), _comp(12), n_mc=15)
        assert (stds["Tc"] >= 0).all() and stds["Tc"].sum() > 0   # dropout → 非零

    def test_acquisition_shape_finite(self):
        b = _bundle(); c = _comp(30)
        score, bd = al.acquisition_scores(b, c, n_mc=10)
        assert score.shape == (30,) and torch.isfinite(score).all()
        assert "uncertainty" in bd and "novelty" in bd

    def test_novelty_far_is_higher(self):
        feats = torch.tensor([[0.0, 0.0], [10.0, 10.0]])
        ref = torch.tensor([[0.0, 0.0]])
        nov = al.novelty_scores(feats, ref)
        assert nov[1] > nov[0]                                   # 遠的新穎度高
        assert torch.allclose(al.novelty_scores(feats, None), torch.zeros(2))

    def test_diverse_batch_distinct_and_spread(self):
        b = _bundle(); c = _comp(50)
        feats = al.composition_to_features_torch(c, b.element_matrix_t)
        score, _ = al.acquisition_scores(b, c, n_mc=8)
        sel = al.select_diverse_batch(feats, score, k=5)
        assert len(sel) == len(set(sel)) == 5                    # 5 個相異
        # 多樣性：所選的平均兩兩距離 ≥ 純前5名（farthest-point 應更分散或相當）
        top5 = torch.topk(score, 5).indices
        d_sel = torch.cdist(feats[sel], feats[sel]).sum()
        d_top = torch.cdist(feats[top5], feats[top5]).sum()
        assert d_sel >= 0.95 * d_top

    def test_recommend_returns_k(self):
        recs = al.recommend_experiments(_bundle(), _comp(40), k=4, n_mc=10)
        assert len(recs) == 4
        for r in recs:
            assert {"index", "Tc_C", "Br_T", "Tc_std_K", "acquisition", "rationale"} <= set(r)


class TestALBenchmark:
    def test_simulate_returns_curve(self):
        """回顧基準機制測試（合成資料；只驗機制，不斷言 AL>random）。"""
        import importlib.util
        from pathlib import Path
        spec = importlib.util.spec_from_file_location(
            "albench", Path(__file__).resolve().parent.parent / "scripts" / "active_learning_benchmark.py")
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        rng = np.random.default_rng(0)
        X = rng.normal(size=(120, 36)).astype(np.float32)
        y = 2.0 * X[:, 0] + rng.normal(0, 0.1, 120)   # 可學的訊號
        for strat in ("random", "uncertainty", "diversity"):
            curve = mod.simulate(X, y, strat, seed=0, max_labels=40)
            assert len(curve) >= 2
            assert curve[0][0] == 8 and curve[-1][0] <= 40       # 標註數遞增
            assert all(isinstance(r, float) for _, r in curve)
