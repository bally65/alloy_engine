"""
HybridBundle 測試：真實 Tc 模型 + 合成 Hc/Br/強度（CI-safe，不依賴 checkpoint）
執行: python -m pytest tests/test_hybrid.py -v
"""
import numpy as np
import torch

from alloy_engine.data.elements import NUM_ELEMENTS, get_element_matrix
from alloy_engine.models.surrogate import SurrogateBundle, PropertyMLP
from alloy_engine.models.hybrid import HybridBundle

DEVICE = torch.device("cpu")
FEAT_DIM = get_element_matrix().shape[1] * 4   # NUM_PROPS × 4 = 36


def _identity_scaler():
    return (np.zeros(FEAT_DIM, dtype=np.float32),
            np.ones(FEAT_DIM, dtype=np.float32), 0.0, 1.0, False)


def _make_synthetic() -> SurrogateBundle:
    em = torch.from_numpy(get_element_matrix()).to(DEVICE)
    mk = lambda: PropertyMLP(FEAT_DIM)
    return SurrogateBundle(
        mlp_tc=mk(), mlp_hc=mk(), mlp_br=mk(), mlp_strength=mk(),
        sc_tc=_identity_scaler(), sc_hc=_identity_scaler(),
        sc_br=_identity_scaler(), sc_strength=_identity_scaler(),
        device=DEVICE, element_matrix_t=em,
    )


def _comp(n=16):
    return torch.distributions.Dirichlet(torch.ones(NUM_ELEMENTS) * 2).sample((n,))


class TestHybridBundle:
    def _hybrid(self):
        synth = _make_synthetic()
        tc_model = PropertyMLP(FEAT_DIM)
        return HybridBundle(synth, tc_model, _identity_scaler(), DEVICE), synth, tc_model

    def test_interface_keys(self):
        hyb, _, _ = self._hybrid()
        out = hyb.predict_properties(_comp(10))
        assert set(out) == {"Tc", "Hc", "Br", "strength"}
        assert all(out[k].shape == (10,) for k in out)

    def test_tc_comes_from_real_model(self):
        # 混合 Tc 應等於真實 tc_model 的輸出，而非合成 mlp_tc
        hyb, synth, tc_model = self._hybrid()
        comp = _comp(12)
        out = hyb.predict_properties(comp)
        expected_tc = hyb._real_tc(comp)
        assert torch.allclose(out["Tc"], expected_tc)
        # 且與合成 Tc 不同（兩模型權重不同）
        synth_tc = synth.predict_properties(comp)["Tc"]
        assert not torch.allclose(out["Tc"], synth_tc)

    def test_other_props_come_from_synthetic(self):
        hyb, synth, _ = self._hybrid()
        comp = _comp(12)
        out = hyb.predict_properties(comp)
        ref = synth.predict_properties(comp)
        for k in ("Hc", "Br", "strength"):
            assert torch.allclose(out[k], ref[k])

    def test_uncertainty_tc_is_deterministic(self):
        hyb, _, _ = self._hybrid()
        comp = _comp(8)
        res = hyb.predict_properties_with_uncertainty(comp, n_samples=5)
        assert torch.allclose(res["Tc_std"], torch.zeros(8))
        assert torch.allclose(res["Tc_mean"], hyb._real_tc(comp))

    def test_drop_in_for_ga_fitness(self):
        # GA 以 predict_fn=bundle.predict_properties 介接 → 混合須能無縫替換
        from alloy_engine.ga.gpu_ga import GPUGeneticAlgorithm
        hyb, _, _ = self._hybrid()
        ga = GPUGeneticAlgorithm(
            predict_fn=hyb.predict_properties, device=DEVICE,
            population_size=100, target_tc_celsius=150.0, tc_tolerance=20.0,
            mode="thermomagnetic",
        )
        fit, info = ga.fitness(ga.population)
        assert fit.shape == (100,)
        assert torch.isfinite(fit).all()
