"""
熱磁發電機裝置層設計模組單元測試
執行: python -m pytest tests/test_generator_design.py -v
"""
import math

import pytest

from alloy_engine.thermomagnetic.generator_design import (
    MU_0,
    magnetic_work_density,
    heat_input_density,
    carnot_efficiency,
    material_efficiency,
    power_density,
    induced_voltage_rms,
    design_tmg,
    design_layered_tmg,
    TMGDesignReport,
    LayeredTMGReport,
)


# ─── 磁功密度 ──────────────────────────────────────────────
class TestMagneticWorkDensity:
    def test_rectangular_upper_bound(self):
        # util=1 → w = ΔJ · B/μ₀
        w = magnetic_work_density(0.20, B_applied_T=1.0, cycle_utilization=1.0)
        assert math.isclose(w, 0.20 / MU_0, rel_tol=1e-9)

    def test_utilization_scales_linearly(self):
        full = magnetic_work_density(0.20, 1.0, 1.0)
        half = magnetic_work_density(0.20, 1.0, 0.5)
        assert math.isclose(half, 0.5 * full, rel_tol=1e-9)

    def test_zero_delta_m_zero_work(self):
        assert magnetic_work_density(0.0, 1.0, 0.3) == 0.0

    def test_negative_input_raises(self):
        with pytest.raises(ValueError):
            magnetic_work_density(-0.1, 1.0)

    def test_bad_utilization_raises(self):
        with pytest.raises(ValueError):
            magnetic_work_density(0.2, 1.0, cycle_utilization=1.5)
        with pytest.raises(ValueError):
            magnetic_work_density(0.2, 1.0, cycle_utilization=0.0)


# ─── 熱輸入密度 ────────────────────────────────────────────
class TestHeatInputDensity:
    def test_sensible_only(self):
        # ΔS_M=0, ε=0 → q = ρ·Cp·ΔT
        q = heat_input_density(7700, 460, 60, 450, delta_S_M=0.0)
        assert math.isclose(q, 7700 * 460 * 60, rel_tol=1e-9)

    def test_regenerator_reduces_sensible(self):
        q0 = heat_input_density(7700, 460, 60, 450, regenerator_effectiveness=0.0)
        q8 = heat_input_density(7700, 460, 60, 450, regenerator_effectiveness=0.8)
        assert math.isclose(q8, 0.2 * q0, rel_tol=1e-9)

    def test_latent_term_added(self):
        q_no_latent = heat_input_density(7700, 460, 60, 450, delta_S_M=0.0)
        q_latent = heat_input_density(7700, 460, 60, 450, delta_S_M=2.0)
        assert math.isclose(q_latent - q_no_latent, 7700 * 450 * 2.0, rel_tol=1e-9)

    def test_bad_regenerator_raises(self):
        with pytest.raises(ValueError):
            heat_input_density(7700, 460, 60, 450, regenerator_effectiveness=1.0)


# ─── 效率 ──────────────────────────────────────────────────
class TestEfficiency:
    def test_carnot_known_value(self):
        # 120→180°C: 1 - 393.15/453.15
        eta = carnot_efficiency(393.15, 453.15)
        assert math.isclose(eta, 1 - 393.15 / 453.15, rel_tol=1e-9)

    def test_carnot_requires_hot_gt_cold(self):
        with pytest.raises(ValueError):
            carnot_efficiency(453.15, 393.15)

    def test_material_efficiency_ratio(self):
        assert math.isclose(material_efficiency(100.0, 1000.0), 0.1, rel_tol=1e-9)

    def test_material_efficiency_zero_q_raises(self):
        with pytest.raises(ValueError):
            material_efficiency(100.0, 0.0)


# ─── 功率與電壓 ────────────────────────────────────────────
class TestPowerAndVoltage:
    def test_power_density(self):
        assert math.isclose(power_density(48000.0, 15.0), 720000.0, rel_tol=1e-9)

    def test_voltage_scales_with_turns_and_freq(self):
        v1 = induced_voltage_rms(200, 0.2, 1e-4, 15.0)
        v2 = induced_voltage_rms(400, 0.2, 1e-4, 15.0)
        assert math.isclose(v2, 2.0 * v1, rel_tol=1e-9)
        v3 = induced_voltage_rms(200, 0.2, 1e-4, 30.0)
        assert math.isclose(v3, 2.0 * v1, rel_tol=1e-9)


# ─── 整機推算 ──────────────────────────────────────────────
class TestDesignTMG:
    def _baseline(self, **kw):
        params = dict(
            T_cold_C=120, T_hot_C=180, delta_M_T=0.20,
            rho=7700.0, cp_specific=460.0, kappa=109.0,
            delta_S_M=0.5, B_applied_T=1.0, cycle_utilization=0.30,
        )
        params.update(kw)
        return design_tmg(**params)

    def test_returns_report(self):
        assert isinstance(self._baseline(), TMGDesignReport)

    def test_efficiency_below_carnot(self):
        r = self._baseline()
        assert 0 < r.eta_material < r.eta_carnot

    def test_regeneration_improves_efficiency(self):
        base = self._baseline(regenerator_effectiveness=0.0)
        reg = self._baseline(regenerator_effectiveness=0.8)
        assert reg.eta_material > base.eta_material
        # 磁功與頻率與熱無關，應保持不變
        assert math.isclose(reg.w_mag_J_m3, base.w_mag_J_m3, rel_tol=1e-9)
        assert math.isclose(reg.f_Hz, base.f_Hz, rel_tol=1e-9)

    def test_sensible_heat_dominates(self):
        # 驗證設計文件核心洞察：低溫廢熱下顯熱遠大於磁功
        r = self._baseline()
        assert r.q_in_J_m3 > 100 * r.w_mag_J_m3

    def test_low_delta_m_warning(self):
        r = self._baseline(delta_M_T=0.05)
        assert any("ΔJ" in w for w in r.warnings)

    def test_summary_is_string(self):
        assert isinstance(self._baseline().summary(), str)


# ─── 分層發電床 ────────────────────────────────────────────
class TestLayeredTMG:
    def _layered(self, n=8, **kw):
        params = dict(
            T_cold_C=120, T_hot_C=180,
            layer_delta_M_T=[0.20] * n,
            rho=7700.0, cp_specific=460.0, kappa=109.0, delta_S_M=0.5,
            B_applied_T=1.4, cycle_utilization=0.30,
        )
        params.update(kw)
        return design_layered_tmg(**params)

    def test_returns_report(self):
        r = self._layered()
        assert isinstance(r, LayeredTMGReport)
        assert len(r.layer_reports) == 8

    def test_per_layer_span_splits_total(self):
        r = self._layered(n=8)
        assert math.isclose(r.per_layer_span_K, 60.0 / 8, rel_tol=1e-9)

    def test_layering_beats_single_layer_no_regen(self):
        # 層化（窄子溫差）效率優於單層全溫差（同無額外回熱）
        single = design_tmg(
            T_cold_C=120, T_hot_C=180, delta_M_T=0.20,
            rho=7700.0, cp_specific=460.0, kappa=109.0, delta_S_M=0.5,
            B_applied_T=1.4, regenerator_effectiveness=0.0,
        )
        layered = self._layered(n=8, extra_regeneration=0.0)
        assert layered.eta_material > single.eta_material

    def test_extra_regeneration_improves_efficiency(self):
        no_reg = self._layered(extra_regeneration=0.0)
        reg = self._layered(extra_regeneration=0.9)
        assert reg.eta_material > no_reg.eta_material

    def test_voltages_add_in_series(self):
        # N 層線圈串聯 → 總電壓約為單層的 N 倍
        r = self._layered(n=8)
        per_layer_v = r.layer_reports[0].v_rms_volts
        assert math.isclose(r.v_rms_volts, sum(x.v_rms_volts for x in r.layer_reports))
        assert r.v_rms_volts > 5 * per_layer_v

    def test_efficiency_below_carnot(self):
        r = self._layered()
        assert 0 < r.eta_material < r.eta_carnot

    def test_empty_layers_raises(self):
        with pytest.raises(ValueError):
            self._layered(n=0, layer_delta_M_T=[])
