"""
物理保真度修正測試：D4（頻率封頂）+ D5（一階相變銳度）
執行: python -m pytest tests/test_physics_fidelity.py -v
"""
import math

import pytest
import torch

from alloy_engine.thermomagnetic.generator_design import (
    effective_frequency, design_tmg,
)
from alloy_engine.thermomagnetic.properties import magnetic_thermodynamic_score


# ─── D4：工程可達頻率封頂 ──────────────────────────────────
class TestEffectiveFrequency:
    def test_low_freq_near_identity(self):
        # f << f_max → f_eff ≈ f
        assert effective_frequency(0.5, 50.0) == pytest.approx(0.5 / (1 + 0.5 / 50))
        assert effective_frequency(0.5, 50.0) > 0.49

    def test_saturates_toward_fmax(self):
        assert effective_frequency(1e6, 50.0) == pytest.approx(50.0, rel=1e-3)

    def test_half_fmax_at_fmax(self):
        assert effective_frequency(50.0, 50.0) == pytest.approx(25.0)

    def test_monotone_increasing(self):
        vals = [effective_frequency(f, 50.0) for f in (1, 10, 50, 100, 500)]
        assert all(b > a for a, b in zip(vals, vals[1:]))

    def test_never_exceeds_fmax(self):
        for f in (1, 10, 100, 1e4):
            assert effective_frequency(f, 50.0) < 50.0

    def test_bad_input_raises(self):
        with pytest.raises(ValueError):
            effective_frequency(-1.0, 50.0)
        with pytest.raises(ValueError):
            effective_frequency(10.0, 0.0)


class TestDesignTMGFrequencyCap:
    def _d(self, **kw):
        p = dict(T_cold_C=120, T_hot_C=180, delta_M_T=0.20,
                 rho=7700.0, cp_specific=460.0, kappa=109.0)
        p.update(kw)
        return design_tmg(**p)

    def test_reported_freq_below_fmax(self):
        assert self._d(plate_thickness_m=5e-4, f_max_Hz=50.0).f_Hz < 50.0

    def test_kappa_diminishing_returns(self):
        # κ ×10 不會讓功率密度 ×10（封頂後次線性）
        lo = self._d(kappa=50.0, plate_thickness_m=5e-4)
        hi = self._d(kappa=500.0, plate_thickness_m=5e-4)
        assert hi.power_density_W_m3 < 10.0 * lo.power_density_W_m3


# ─── D5：一階相變銳度 ──────────────────────────────────────
class TestFirstOrderTransition:
    def _delta_m(self, T_target_C, width=None, Tc_K=300.0, Ms=1.0):
        out = magnetic_thermodynamic_score(
            Ms=torch.tensor([Ms]), Tc_K=torch.tensor([Tc_K]),
            T_target_C=T_target_C, delta_T_window=30.0, transition_width_K=width,
        )
        return float(out["delta_M"])

    def test_default_is_meanfield_backcompat(self):
        # transition_width_K=None 必須完全等於原平均場 sqrt 公式
        Tc, Ttgt, dT = 400.0, 50.0, 30.0
        T_low = (Ttgt + 273.15) - dT
        T_high = (Ttgt + 273.15) + dT
        exp_low = math.sqrt(max(1 - T_low / Tc, 0.0))
        exp_high = math.sqrt(max(1 - T_high / Tc, 0.0))
        expected = exp_low - exp_high
        assert self._delta_m(Ttgt, width=None, Tc_K=Tc) == pytest.approx(expected, rel=1e-5)

    def test_first_order_sharper_than_meanfield(self):
        # 同窗下一階陡降的 delta_M 應大於平均場（修「低估一階材料」）
        mf = self._delta_m(0.0, width=None)
        fo = self._delta_m(0.0, width=5.0)
        assert fo > mf

    def test_narrower_width_larger_delta_m(self):
        # 過渡越窄（越接近一階）→ delta_M 越大
        assert self._delta_m(0.0, width=3.0) > self._delta_m(0.0, width=30.0)

    def test_delta_m_bounded_by_ms(self):
        # delta_M 不可超過 Ms
        assert 0.0 <= self._delta_m(0.0, width=2.0, Ms=1.0) <= 1.0
