"""
複合磁熱材料模型測試
執行: python -m pytest tests/test_composite.py -v
"""
import math

import pytest

from alloy_engine.thermomagnetic.composite import (
    MatrixMaterial, MATRIX_MATERIALS,
    composite_properties, optimal_matrix_fraction, CompositeOptimum,
)

CU = MATRIX_MATERIALS["Cu"]

# Mn-Fe-P 代表值（高 ΔM、低 κ）
PHASE = dict(
    phase_delta_M_T=1.10, phase_cp=600.0, phase_rho=6800.0,
    phase_kappa=3.5, phase_delta_S_M=14.0,
)


class TestCompositeProperties:
    def test_zero_matrix_returns_phase(self):
        p = composite_properties(matrix=CU, matrix_volume_fraction=0.0, **PHASE)
        assert math.isclose(p["delta_M_T"], 1.10)
        assert math.isclose(p["kappa"], 3.5)
        assert math.isclose(p["rho"], 6800.0)

    def test_matrix_dilutes_delta_m_linearly(self):
        p = composite_properties(matrix=CU, matrix_volume_fraction=0.5, **PHASE)
        assert math.isclose(p["delta_M_T"], 0.5 * 1.10, rel_tol=1e-9)

    def test_matrix_raises_kappa(self):
        bare = composite_properties(matrix=CU, matrix_volume_fraction=0.0, **PHASE)
        comp = composite_properties(matrix=CU, matrix_volume_fraction=0.5, **PHASE)
        assert comp["kappa"] > 10 * bare["kappa"]   # Cu κ=401 大幅拉高

    def test_kappa_between_series_and_parallel(self):
        phi = 0.4
        f = 1 - phi
        k_par = f * PHASE["phase_kappa"] + phi * CU.kappa
        k_ser = 1.0 / (f / PHASE["phase_kappa"] + phi / CU.kappa)
        comp = composite_properties(matrix=CU, matrix_volume_fraction=phi,
                                    connectivity=0.7, **PHASE)
        assert k_ser <= comp["kappa"] <= k_par

    def test_connectivity_extremes(self):
        phi = 0.4
        f = 1 - phi
        k_par = f * PHASE["phase_kappa"] + phi * CU.kappa
        k_ser = 1.0 / (f / PHASE["phase_kappa"] + phi / CU.kappa)
        par = composite_properties(matrix=CU, matrix_volume_fraction=phi,
                                   connectivity=1.0, **PHASE)
        ser = composite_properties(matrix=CU, matrix_volume_fraction=phi,
                                   connectivity=0.0, **PHASE)
        assert math.isclose(par["kappa"], k_par, rel_tol=1e-9)
        assert math.isclose(ser["kappa"], k_ser, rel_tol=1e-9)

    def test_delta_s_diluted_by_mass_fraction(self):
        p = composite_properties(matrix=CU, matrix_volume_fraction=0.5, **PHASE)
        assert p["delta_S_M"] < 14.0   # 僅磁熱相貢獻，按質量分率稀釋

    def test_invalid_fraction_raises(self):
        with pytest.raises(ValueError):
            composite_properties(matrix=CU, matrix_volume_fraction=1.0, **PHASE)


class TestOptimalMatrixFraction:
    def test_returns_optimum(self):
        opt = optimal_matrix_fraction(Tc_C=27.0, matrix=CU, **PHASE)
        assert isinstance(opt, CompositeOptimum)
        assert 0.0 < opt.best_matrix_fraction < 0.7

    def test_composite_beats_bare_for_low_kappa_phase(self):
        # 低 κ 高 ΔM 相加 Cu 基底後功率密度應大幅提升
        opt = optimal_matrix_fraction(Tc_C=27.0, matrix=CU, **PHASE)
        assert opt.composite_power_density_W_m3 > 2.0 * opt.bare_power_density_W_m3
        assert opt.power_gain > 2.0

    def test_high_kappa_phase_needs_less_matrix_than_low_kappa(self):
        # 本身 κ 已高（Fe 系 109）的相，最佳基底分率應「小於」低 κ 相，
        # 且功率增益較溫和（低 κ 相從基底獲益遠大於高 κ 相）。
        hi_k = optimal_matrix_fraction(
            phase_delta_M_T=0.20, phase_cp=460.0, phase_rho=7700.0,
            phase_kappa=109.0, phase_delta_S_M=0.5, Tc_C=150.0, matrix=CU,
        )
        lo_k = optimal_matrix_fraction(Tc_C=27.0, matrix=CU, **PHASE)
        assert hi_k.best_matrix_fraction < lo_k.best_matrix_fraction
        assert hi_k.power_gain < lo_k.power_gain


def test_zero_phase_kappa_no_crash():
    """缺陷修復：磁熱相 κ=0 不應 ZeroDivisionError（與 device_score torch 路徑一致）。"""
    from alloy_engine.thermomagnetic.composite import composite_properties, MATRIX_MATERIALS
    r = composite_properties(
        phase_delta_M_T=0.5, phase_cp=400, phase_rho=7000, phase_kappa=0.0,
        phase_delta_S_M=2.0, matrix=MATRIX_MATERIALS["Cu"],
        matrix_volume_fraction=0.3, connectivity=1.0)
    assert r["kappa"] >= 0.0  # 不崩潰、有限值
