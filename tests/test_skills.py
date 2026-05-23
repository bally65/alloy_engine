"""
Skills 計算模組單元測試
執行: python -m pytest tests/test_skills.py -v
"""
import math
import sys
import os
import warnings
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from skills.fluidsim_skills.fluid import water_properties, reynolds_number, flow_regime, flowrate_to_velocity
from skills.fluidsim_skills.pressure import pressure_drop, friction_factor
from skills.fluidsim_skills.cleaning import nozzle_flowrate, nozzle_impact_force
from skills.fluidsim_skills.chemistry import noyes_whitney_dissolution, surface_forces, CLEANER_DB, CONTAMINATION_DB


# ─── fluid.py 測試 ───────────────────────────────────────────

class TestWaterProperties:
    def test_density_20C(self):
        props = water_properties(20)
        assert abs(props.density - 998.20) < 0.1, f"密度誤差過大: {props.density}"

    def test_density_0C(self):
        props = water_properties(0)
        assert abs(props.density - 999.84) < 0.1

    def test_density_60C(self):
        props = water_properties(60)
        assert abs(props.density - 983.20) < 0.2

    def test_viscosity_20C(self):
        # 實際值: 1.002e-3 Pa·s，Vogel 公式應在 0.5% 以內
        props = water_properties(20)
        assert abs(props.dynamic_viscosity - 1.002e-3) / 1.002e-3 < 0.005, \
            f"黏度誤差: {props.dynamic_viscosity:.4e} vs 1.002e-3"

    def test_viscosity_40C(self):
        # 實際值: ~0.653e-3 Pa·s
        props = water_properties(40)
        assert abs(props.dynamic_viscosity - 0.653e-3) / 0.653e-3 < 0.01

    def test_kinematic_viscosity_consistency(self):
        props = water_properties(25)
        assert abs(props.kinematic_viscosity - props.dynamic_viscosity / props.density) < 1e-12


class TestReynolds:
    def test_laminar(self):
        Re = reynolds_number(0.025, 0.05, 1e-6)
        assert Re < 2300
        assert flow_regime(Re) == 'laminar'

    def test_turbulent(self):
        Re = reynolds_number(0.025, 2.5, 1e-6)
        assert Re > 4000
        assert flow_regime(Re) == 'turbulent'

    def test_value(self):
        # Re = V*D/ν = 1.0*0.01/1e-6 = 10000
        Re = reynolds_number(0.01, 1.0, 1e-6)
        assert abs(Re - 10000) < 1


# ─── pressure.py 測試 ───────────────────────────────────────

class TestFrictionFactor:
    def test_laminar(self):
        f = friction_factor(1000)
        assert abs(f - 64.0 / 1000) < 1e-6

    def test_turbulent_smooth(self):
        # Re=100000，光滑管，Moody 圖約 0.018
        f = friction_factor(100000, 0.0)
        assert 0.015 < f < 0.022

    def test_turbulent_rough(self):
        # 粗糙管摩擦係數應高於光滑管
        f_smooth = friction_factor(50000, 0.0)
        f_rough = friction_factor(50000, 0.01)
        assert f_rough > f_smooth


class TestPressureDrop:
    def test_output_fields(self):
        result = pressure_drop(0.025, 10.0, 20.0)
        assert result.total_loss_pa > 0
        assert result.total_loss_bar > 0
        assert result.friction_factor > 0
        assert result.velocity > 0

    def test_longer_pipe_more_loss(self):
        r1 = pressure_drop(0.025, 5.0, 20.0)
        r2 = pressure_drop(0.025, 10.0, 20.0)
        assert r2.friction_loss_pa > r1.friction_loss_pa

    def test_higher_flow_more_loss(self):
        r1 = pressure_drop(0.0095, 3.0, 5.0)
        r2 = pressure_drop(0.0095, 3.0, 15.0)
        assert r2.total_loss_pa > r1.total_loss_pa

    def test_bar_pa_consistency(self):
        result = pressure_drop(0.0095, 3.0, 8.0)
        assert abs(result.total_loss_bar - result.total_loss_pa / 1e5) < 1e-6


# ─── cleaning.py 測試 ───────────────────────────────────────

class TestNozzle:
    def test_flowrate_increases_with_pressure(self):
        Q1 = nozzle_flowrate(1.0, 2.0)
        Q2 = nozzle_flowrate(4.0, 2.0)
        assert Q2 > Q1

    def test_flowrate_increases_with_diameter(self):
        Q1 = nozzle_flowrate(3.0, 1.0)
        Q2 = nozzle_flowrate(3.0, 2.0)
        assert Q2 > Q1

    def test_impact_force_positive(self):
        result = nozzle_impact_force(3.0, 2.0, 150, 25)
        assert result.impact_force_N > 0
        assert result.exit_velocity > 0
        assert result.flowrate_lpm > 0
        assert result.coverage_width_mm > 0

    def test_higher_pressure_more_force(self):
        r1 = nozzle_impact_force(2.0, 1.5, 150, 15)
        r2 = nozzle_impact_force(6.0, 1.5, 150, 15)
        assert r2.impact_force_N > r1.impact_force_N


# ─── chemistry.py 測試 ───────────────────────────────────────

class TestDissolution:
    def test_longer_time_more_dissolved(self):
        r1 = noyes_whitney_dissolution('grease_light', 2, 'alkaline_mild', 2.0)
        r2 = noyes_whitney_dissolution('grease_light', 15, 'alkaline_mild', 2.0)
        assert r2.dissolved_fraction > r1.dissolved_fraction, \
            "接觸時間越長溶解分率應越高"

    def test_higher_concentration_more_dissolved(self):
        r1 = noyes_whitney_dissolution('grease_light', 10, 'alkaline_mild', 0.5)
        r2 = noyes_whitney_dissolution('grease_light', 10, 'alkaline_mild', 3.0)
        assert r2.dissolved_fraction > r1.dissolved_fraction

    def test_dissolved_fraction_bounded(self):
        r = noyes_whitney_dissolution('grease_light', 60, 'alkaline_mild', 5.0)
        assert 0.0 <= r.dissolved_fraction <= 1.0

    def test_mineral_scale_needs_acid(self):
        r_alkaline = noyes_whitney_dissolution('mineral_scale', 20, 'alkaline_mild', 2.0)
        r_acid = noyes_whitney_dissolution('mineral_scale', 20, 'acid_mild', 3.0)
        assert r_acid.dissolved_fraction > r_alkaline.dissolved_fraction, \
            "水垢應該酸性清潔劑效果更好"

    def test_realistic_timescale(self):
        # 弱鹼 2%，10分鐘，輕度油污：應在 30-80% 範圍（非立即飽和）
        r = noyes_whitney_dissolution('grease_light', 10, 'alkaline_mild', 2.0)
        assert 0.2 < r.dissolved_fraction < 0.95, \
            f"溶解分率 {r.dissolved_fraction:.2f} 不在合理範圍（表示時間參數已失效）"

    def test_2min_vs_20min_significant_difference(self):
        r_short = noyes_whitney_dissolution('grease_heavy', 2, 'alkaline_mild', 2.0)
        r_long = noyes_whitney_dissolution('grease_heavy', 20, 'alkaline_mild', 2.0)
        diff = r_long.dissolved_fraction - r_short.dissolved_fraction
        assert diff > 0.1, \
            f"2分鐘與20分鐘結果差異僅 {diff:.3f}，時間參數可能仍無效"


class TestSurfaceForces:
    def test_surfactant_reduces_surface_tension(self):
        result = surface_forces('surfactant_neutral', 1.0)
        assert result.surface_tension_mN < 72.8, "界面活性劑應降低表面張力"

    def test_higher_conc_lower_tension_below_cmc(self):
        cmc = CLEANER_DB['surfactant_neutral']['cmc_pct']
        r1 = surface_forces('surfactant_neutral', cmc * 0.2)
        r2 = surface_forces('surfactant_neutral', cmc * 0.8)
        assert r2.surface_tension_mN < r1.surface_tension_mN

    def test_spreading_coefficient_nonpositive(self):
        # 物理上 S = γ(cosθ - 1) ≤ 0 恆成立
        for cleaner_key in ['alkaline_mild', 'surfactant_neutral', 'disinfectant']:
            result = surface_forces(cleaner_key, 2.0)
            assert result.spreading_coefficient <= 0.01, \
                f"{cleaner_key}: S={result.spreading_coefficient:.3f} 應 ≤ 0"

    def test_shear_stress_positive(self):
        result = surface_forces('alkaline_mild', 2.0, shear_velocity=1.5, fin_spacing_mm=1.2)
        assert result.shear_stress_Pa > 0


# ─── 邊界條件與錯誤處理測試 ─────────────────────────────────

class TestInputValidation:
    """確認非法輸入會拋出 ValueError，而非靜默產生錯誤結果。"""

    def test_friction_factor_zero_re(self):
        with pytest.raises(ValueError):
            friction_factor(0)

    def test_friction_factor_negative_re(self):
        with pytest.raises(ValueError):
            friction_factor(-100)

    def test_pressure_drop_zero_diameter(self):
        with pytest.raises(ValueError):
            pressure_drop(diameter=0, length=3, flowrate_lpm=10)

    def test_pressure_drop_negative_diameter(self):
        with pytest.raises(ValueError):
            pressure_drop(diameter=-0.01, length=3, flowrate_lpm=10)

    def test_pressure_drop_negative_flowrate(self):
        with pytest.raises(ValueError):
            pressure_drop(diameter=0.01, length=3, flowrate_lpm=-5)

    def test_pressure_drop_negative_length(self):
        with pytest.raises(ValueError):
            pressure_drop(diameter=0.01, length=-1, flowrate_lpm=10)

    def test_nozzle_flowrate_negative_pressure(self):
        with pytest.raises(ValueError):
            nozzle_flowrate(-1.0, 2.0)

    def test_nozzle_flowrate_zero_diameter(self):
        with pytest.raises(ValueError):
            nozzle_flowrate(3.0, 0.0)

    def test_nozzle_impact_negative_pressure(self):
        with pytest.raises(ValueError):
            nozzle_impact_force(-1.0, 2.0)

    def test_nozzle_impact_spray_angle_too_large(self):
        with pytest.raises(ValueError):
            nozzle_impact_force(3.0, 2.0, spray_angle_deg=180)

    def test_nozzle_impact_spray_angle_zero(self):
        with pytest.raises(ValueError):
            nozzle_impact_force(3.0, 2.0, spray_angle_deg=0)

    def test_nozzle_impact_negative_distance(self):
        with pytest.raises(ValueError):
            nozzle_impact_force(3.0, 2.0, distance_mm=-10)

    def test_reynolds_zero_diameter(self):
        with pytest.raises(ValueError):
            reynolds_number(0, 1.0, 1e-6)

    def test_reynolds_negative_velocity(self):
        with pytest.raises(ValueError):
            reynolds_number(0.01, -1.0, 1e-6)

    def test_flow_regime_negative_re(self):
        with pytest.raises(ValueError):
            flow_regime(-1)


class TestBoundaryValues:
    """邊界值行為測試。"""

    def test_flow_regime_re_4000_is_transitional(self):
        # Re=4000 應屬過渡流（含邊界，符合 ASHRAE 標準）
        assert flow_regime(4000) == 'transitional'

    def test_flow_regime_re_2300_is_transitional(self):
        assert flow_regime(2300) == 'transitional'

    def test_flow_regime_re_2299_is_laminar(self):
        assert flow_regime(2299) == 'laminar'

    def test_flow_regime_re_4001_is_turbulent(self):
        assert flow_regime(4001) == 'turbulent'

    def test_nozzle_zero_pressure_returns_zero(self):
        Q = nozzle_flowrate(0.0, 2.0)
        assert Q == 0.0

    def test_nozzle_impact_zero_pressure_returns_zeros(self):
        r = nozzle_impact_force(0.0, 2.0)
        assert r.flowrate_lpm == 0.0
        assert r.impact_force_N == 0.0

    def test_pressure_drop_zero_flowrate(self):
        result = pressure_drop(0.01, 3.0, 0.0)
        assert result.total_loss_pa == 0.0

    def test_water_properties_out_of_range_warns(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            water_properties(-10)
            assert len(w) == 1
            assert issubclass(w[0].category, UserWarning)

    def test_water_properties_clamped_silently_correct(self):
        # 超出範圍後截斷，結果應等同邊界值
        props_boundary = water_properties(0)
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            props_out = water_properties(-50)
        assert props_out.density == pytest.approx(props_boundary.density, rel=1e-6)


class TestSolubilityBoostCompleteness:
    """確認所有清潔劑對所有污垢都有明確的增效值（無空缺）。"""

    def test_all_combinations_defined(self):
        contamination_keys = list(CONTAMINATION_DB.keys())
        for cleaner_key, cleaner in CLEANER_DB.items():
            for cont_key in contamination_keys:
                boost = cleaner['solubility_boost'].get(cont_key)
                assert boost is not None, (
                    f"清潔劑 '{cleaner_key}' 對污垢 '{cont_key}' 缺少 solubility_boost 值"
                )
                assert boost > 0, (
                    f"清潔劑 '{cleaner_key}' 對污垢 '{cont_key}' 的 boost={boost} 應 > 0"
                )

    def test_acid_beats_alkaline_on_mineral_scale(self):
        r_acid = noyes_whitney_dissolution('mineral_scale', 15, 'acid_mild', 3.0)
        r_alk  = noyes_whitney_dissolution('mineral_scale', 15, 'alkaline_mild', 2.0)
        assert r_acid.dissolved_fraction > r_alk.dissolved_fraction

    def test_disinfectant_best_for_biofilm(self):
        r_dis  = noyes_whitney_dissolution('biofilm', 20, 'disinfectant', 1.0)
        r_surf = noyes_whitney_dissolution('biofilm', 20, 'surfactant_neutral', 1.0)
        assert r_dis.dissolved_fraction > r_surf.dissolved_fraction


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
