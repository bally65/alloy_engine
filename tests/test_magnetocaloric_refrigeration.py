"""
磁熱製冷（反向運作）模組單元測試
執行: python -m pytest tests/test_magnetocaloric_refrigeration.py -v
"""
import math

import pytest

from alloy_engine.thermomagnetic.magnetocaloric_refrigeration import (
    adiabatic_temperature_change,
    carnot_cop_cooling,
    cooling_capacity_per_cycle,
    ideal_work_input,
    hysteresis_penalized_cop,
    specific_cooling_power,
    design_refrigerator,
    MCRDesignReport,
)


class TestMCEBasics:
    def test_delta_t_ad_gd_value(self):
        # Gd@1.5T: T=294, ΔS_M=5, Cp=300 → ~4.9K（文獻 3–5K）
        dt = adiabatic_temperature_change(294.0, 300.0, 5.0)
        assert 3.0 < dt < 6.0

    def test_delta_t_ad_uses_abs_entropy(self):
        # ΔS_M 正負號不影響 ΔT_ad 大小
        assert math.isclose(
            adiabatic_temperature_change(294.0, 300.0, 5.0),
            adiabatic_temperature_change(294.0, 300.0, -5.0),
        )

    def test_delta_t_ad_bad_cp_raises(self):
        with pytest.raises(ValueError):
            adiabatic_temperature_change(294.0, 0.0, 5.0)

    def test_carnot_cop_known(self):
        # 270K/296K span=26K → 270/26
        assert math.isclose(carnot_cop_cooling(270.0, 296.0), 270.0 / 26.0)

    def test_carnot_requires_hot_gt_cold(self):
        with pytest.raises(ValueError):
            carnot_cop_cooling(296.0, 270.0)


class TestCycleEnergy:
    def test_cooling_capacity_formula(self):
        q = cooling_capacity_per_cycle(270.0, 10.0, utilization=0.3)
        assert math.isclose(q, 0.3 * 270.0 * 10.0)

    def test_ideal_work_input(self):
        assert math.isclose(ideal_work_input(900.0, 9.0), 100.0)

    def test_hysteresis_reduces_net_and_cop(self):
        q_net0, w0, cop0 = hysteresis_penalized_cop(900.0, 100.0, 0.0)
        q_net1, w1, cop1 = hysteresis_penalized_cop(900.0, 100.0, 50.0)
        assert q_net1 < q_net0
        assert w1 > w0
        assert cop1 < cop0

    def test_hysteresis_can_cancel_cooling(self):
        # w_hyst ≥ q_cold → 淨冷量 ≤ 0 → COP=0（內部產熱抵銷製冷）
        q_net, _w, cop = hysteresis_penalized_cop(500.0, 100.0, 600.0)
        assert q_net < 0
        assert cop == 0.0

    def test_specific_cooling_power(self):
        assert math.isclose(specific_cooling_power(800.0, 10.0), 8000.0)

    def test_scp_clamps_negative_net(self):
        assert specific_cooling_power(-100.0, 10.0) == 0.0


class TestDesignRefrigerator:
    def _base(self, **kw):
        params = dict(
            T_cold_C=-3, T_hot_C=23, delta_S_M=11.0,
            cp_specific=700.0, f_Hz=10.0,
        )
        params.update(kw)
        return design_refrigerator(**params)

    def test_returns_report(self):
        assert isinstance(self._base(), MCRDesignReport)

    def test_matches_hmr_benchmark_low_hysteresis(self):
        # CAS HMR (PNAS 2026): ~8.3 kW/kg, ε_ex ~54% @ 26K span, 10 Hz
        r = self._base(hysteresis_loss_J_kg=50.0)
        assert 7.0 < r.specific_cooling_power_W_kg / 1000 < 9.5
        assert 0.45 < r.exergy_efficiency < 0.70

    def test_hysteresis_devastates_cop(self):
        low = self._base(hysteresis_loss_J_kg=50.0)
        high = self._base(hysteresis_loss_J_kg=800.0)
        assert high.cop < 0.25 * low.cop  # 磁滯為頭號殺手

    def test_cop_below_carnot(self):
        r = self._base(hysteresis_loss_J_kg=50.0)
        assert 0 < r.cop < r.cop_carnot

    def test_excess_hysteresis_warns(self):
        r = self._base(hysteresis_loss_J_kg=2000.0)
        assert any("製冷" in w or "磁滯" in w for w in r.warnings)

    def test_summary_is_string(self):
        assert isinstance(self._base().summary(), str)
