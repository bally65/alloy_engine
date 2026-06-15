"""
D2：replace_tc_head 烘焙真實 Tc 進主代理（CI-safe，不依賴 checkpoint）。
執行: python -m pytest tests/test_bake_real_tc.py -v
"""
import numpy as np
import torch

from alloy_engine.data.elements import NUM_ELEMENTS, get_element_matrix
from alloy_engine.models.surrogate import SurrogateBundle, PropertyMLP

DEVICE = torch.device("cpu")
FEAT_DIM = get_element_matrix().shape[1] * 4   # 36


def _scaler():
    return (np.zeros(FEAT_DIM, dtype=np.float32),
            np.ones(FEAT_DIM, dtype=np.float32), 0.0, 1.0, False)


def _make_bundle() -> SurrogateBundle:
    em = torch.from_numpy(get_element_matrix()).to(DEVICE)
    mk = lambda: PropertyMLP(FEAT_DIM)
    return SurrogateBundle(
        mlp_tc=mk(), mlp_hc=mk(), mlp_br=mk(), mlp_strength=mk(),
        sc_tc=_scaler(), sc_hc=_scaler(), sc_br=_scaler(), sc_strength=_scaler(),
        device=DEVICE, element_matrix_t=em,
    )


def _comp(n=16):
    return torch.distributions.Dirichlet(torch.ones(NUM_ELEMENTS)).sample((n,))


class TestReplaceTcHead:
    def test_tc_changes_others_unchanged(self):
        b = _make_bundle()
        comp = _comp(20)
        before = b.predict_properties(comp)
        real_tc = PropertyMLP(FEAT_DIM)
        b.replace_tc_head(real_tc, _scaler())
        after = b.predict_properties(comp)
        # Tc 改變（兩個 MLP 權重不同）
        assert not torch.allclose(before["Tc"], after["Tc"])
        # 其餘三頭完全不變
        for k in ("Hc", "Br", "strength"):
            assert torch.allclose(before[k], after[k])

    def test_tc_matches_supplied_model(self):
        b = _make_bundle()
        real_tc = PropertyMLP(FEAT_DIM).eval()
        b.replace_tc_head(real_tc, _scaler())
        comp = _comp(12)
        # bundle 的 Tc 應等於直接用 real_tc 推論（identity scaler）
        from alloy_engine.features.engineering import composition_to_features_torch
        feats = composition_to_features_torch(comp, b.element_matrix_t)
        with torch.no_grad():
            expected = real_tc(feats)
        assert torch.allclose(b.predict_properties(comp)["Tc"], expected, atol=1e-5)

    def test_save_load_roundtrip(self, tmp_path):
        b = _make_bundle()
        real_tc = PropertyMLP(FEAT_DIM)
        b.replace_tc_head(real_tc, _scaler())
        comp = _comp(10)
        ref = b.predict_properties(comp)
        p = tmp_path / "baked.pt"
        b.save(p)
        reloaded = SurrogateBundle.load(p, device=DEVICE)
        out = reloaded.predict_properties(comp)
        for k in ("Tc", "Hc", "Br", "strength"):
            assert torch.allclose(ref[k], out[k], atol=1e-5)

    def test_returns_self_for_chaining(self):
        b = _make_bundle()
        assert b.replace_tc_head(PropertyMLP(FEAT_DIM), _scaler()) is b

    def test_drop_in_for_ga(self):
        from alloy_engine.ga.gpu_ga import GPUGeneticAlgorithm
        b = _make_bundle()
        b.replace_tc_head(PropertyMLP(FEAT_DIM), _scaler())
        ga = GPUGeneticAlgorithm(
            predict_fn=b.predict_properties, device=DEVICE,
            population_size=100, target_tc_celsius=150.0, tc_tolerance=20.0,
            mode="thermomagnetic",
        )
        fit, _ = ga.fitness(ga.population)
        assert fit.shape == (100,) and torch.isfinite(fit).all()


def test_replace_br_head():
    """D3：replace_br_head 換真實 Br 頭，其餘三頭不變。"""
    b = _make_bundle()
    comp = _comp(16)
    before = b.predict_properties(comp)
    real_br = PropertyMLP(FEAT_DIM)
    b.replace_br_head(real_br, _scaler())
    after = b.predict_properties(comp)
    assert not torch.allclose(before["Br"], after["Br"])      # Br 改變
    for k in ("Tc", "Hc", "strength"):
        assert torch.allclose(before[k], after[k])             # 其餘不變
