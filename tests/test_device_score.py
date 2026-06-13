"""
整機級適應度 (device_score) + 基準材料 + GA 整機目標整合測試
執行: python -m pytest tests/test_device_score.py -v
"""
import torch
import pytest

from alloy_engine.data.elements import NUM_ELEMENTS
from alloy_engine.ga.gpu_ga import GPUGeneticAlgorithm
from alloy_engine.thermomagnetic.device_score import (
    device_power_efficiency_score,
)
from alloy_engine.thermomagnetic.reference_materials import (
    REFERENCE_MATERIALS, get, ReferenceMaterial,
)

DEVICE = torch.device("cpu")


def _pop(n=64):
    alpha = torch.ones(NUM_ELEMENTS) * 2.0
    return torch.distributions.Dirichlet(alpha).sample((n,))


# ─── device_score ──────────────────────────────────────────
class TestDeviceScore:
    def test_shapes_and_keys(self):
        pop = _pop(50)
        n = pop.shape[0]
        out = device_power_efficiency_score(
            pop, Ms=torch.ones(n), Tc_K=torch.full((n,), 450.0),
            Hc=torch.full((n,), 50.0), T_target_C=150.0,
        )
        for k in ("w_mag_J_m3", "q_in_J_m3", "eta",
                  "power_density_W_m3", "device_score"):
            assert out[k].shape == (n,)

    def test_score_in_unit_range(self):
        pop = _pop(50)
        n = pop.shape[0]
        out = device_power_efficiency_score(
            pop, Ms=torch.ones(n), Tc_K=torch.full((n,), 450.0),
            Hc=torch.full((n,), 50.0), T_target_C=150.0,
        )
        assert (out["device_score"] >= 0).all()
        assert (out["device_score"] <= 1.0).all()

    def test_higher_field_more_work(self):
        pop = _pop(40)
        n = pop.shape[0]
        kw = dict(Ms=torch.ones(n), Tc_K=torch.full((n,), 450.0),
                  Hc=torch.full((n,), 50.0), T_target_C=150.0)
        lo = device_power_efficiency_score(pop, B_applied_T=1.0, **kw)
        hi = device_power_efficiency_score(pop, B_applied_T=1.5, **kw)
        assert (hi["w_mag_J_m3"] >= lo["w_mag_J_m3"]).all()

    def test_regeneration_raises_efficiency(self):
        pop = _pop(40)
        n = pop.shape[0]
        kw = dict(Ms=torch.ones(n), Tc_K=torch.full((n,), 450.0),
                  Hc=torch.full((n,), 50.0), T_target_C=150.0)
        no_reg = device_power_efficiency_score(pop, regenerator_effectiveness=0.0, **kw)
        reg = device_power_efficiency_score(pop, regenerator_effectiveness=0.9, **kw)
        assert (reg["eta"] >= no_reg["eta"]).all()


# ─── reference materials ───────────────────────────────────
class TestReferenceMaterials:
    def test_all_present(self):
        assert len(REFERENCE_MATERIALS) >= 5
        for m in REFERENCE_MATERIALS.values():
            assert isinstance(m, ReferenceMaterial)
            assert m.delta_M_T > 0 and m.cp_specific > 0 and m.kappa > 0

    def test_get_known(self):
        assert get("Gd (純釓)").transition == "2nd"

    def test_get_unknown_raises(self):
        with pytest.raises(KeyError):
            get("不存在的材料")

    def test_rare_earth_has_higher_delta_m_than_engine(self):
        # 稀土/一階材料 ΔM 應高於 Fe 系引擎基準
        engine = get("Fe-Cr-Cu-Si (本引擎)")
        assert get("(Mn,Fe)2(P,Si)").delta_M_T > engine.delta_M_T


# ─── GA 整機目標整合 ───────────────────────────────────────
class TestGADeviceObjective:
    def _predict(self, comps):
        n = comps.shape[0]
        return {
            "Tc":       torch.full((n,), 423.0, device=DEVICE),  # 150°C
            "Hc":       torch.full((n,), 50.0,  device=DEVICE),
            "Br":       torch.full((n,), 1.0,   device=DEVICE),
            "strength": torch.full((n,), 500.0, device=DEVICE),
        }

    def _ga(self, w_device):
        return GPUGeneticAlgorithm(
            predict_fn=self._predict, device=DEVICE,
            population_size=200, target_tc_celsius=150.0, tc_tolerance=20.0,
            mode="thermomagnetic", w_device=w_device,
        )

    def test_device_objective_runs_and_reports(self):
        ga = self._ga(w_device=1.0)
        fit, info = ga.fitness(ga.population)
        assert fit.shape == (200,)
        assert torch.isfinite(fit).all()
        assert "device_score" in info
        assert "device_eta" in info and "device_power_W_m3" in info

    def test_device_objective_off_by_default(self):
        ga = self._ga(w_device=0.0)
        _fit, info = ga.fitness(ga.population)
        assert "device_score" not in info   # 預設不計算，向後相容

    def test_device_objective_evolves(self):
        ga = self._ga(w_device=1.0)
        pop, fit, info = ga.run(n_gen=8, verbose=False)
        assert torch.isfinite(fit).all()
        assert len(ga.history["best_fitness"]) == 8
