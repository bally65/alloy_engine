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
from skills.fluidsim_skills.chemistry import noyes_whitney_dissolution, surface_forces, corrosion_risk, CLEANER_DB, CONTAMINATION_DB
from skills.fluidsim_skills.capillary import capillary_pressure, lucas_washburn_penetration, time_to_penetrate, analyse_fin_penetration
from skills.fluidsim_skills.thermal import fin_efficiency, dittus_boelter_h, fin_efficiency_from_kappa
from skills.fluidsim_skills.droplet import weber_number, ohnesorge_number, droplet_regime, spray_droplet_size, analyse_droplet
from skills.fluidsim_skills.fouling import kern_seaton_fouling, cleaning_interval, fouling_penalty, analyse_fouling, FOULING_RESISTANCE_DB
from skills.fluidsim_skills.airflow import air_properties, fin_channel_pressure_drop, fouling_layer_thickness, analyse_airflow


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


# ─── capillary.py 測試 ──────────────────────────────────────

class TestCapillary:
    def test_pressure_positive_when_angle_below_90(self):
        pc = capillary_pressure(30.0, 45.0, 1.0)
        assert pc > 0, "θ < 90° 時毛細壓力應為正（促進滲入）"

    def test_pressure_zero_when_angle_90(self):
        pc = capillary_pressure(30.0, 90.0, 1.0)
        assert abs(pc) < 1e-6, "θ = 90° 時毛細壓力應接近零"

    def test_pressure_negative_when_angle_above_90(self):
        pc = capillary_pressure(30.0, 120.0, 1.0)
        assert pc < 0, "θ > 90° 時毛細壓力應為負（阻礙滲入）"

    def test_penetration_depth_increases_with_time(self):
        x1 = lucas_washburn_penetration(30.0, 45.0, 1.0, 1e-3, 10.0)
        x2 = lucas_washburn_penetration(30.0, 45.0, 1.0, 1e-3, 40.0)
        assert x2 > x1, "滲透深度應隨時間增加（Lucas-Washburn √t 關係）"

    def test_penetration_blocked_when_angle_ge_90(self):
        x = lucas_washburn_penetration(30.0, 90.0, 1.0, 1e-3, 60.0)
        assert x == 0.0, "θ ≥ 90° 無法自發滲透"

    def test_time_to_penetrate_infinite_when_blocked(self):
        t = time_to_penetrate(30.0, 90.0, 1.0, 1e-3, 10.0)
        assert t == float('inf')

    def test_analyse_fin_penetration_report(self):
        report = analyse_fin_penetration(2.0, 15.0, 30.0, 25.0, 1e-3)
        assert report.can_reach_full_depth in (True, False)
        assert report.capillary_pressure_pa > 0
        assert report.time_to_full_penetration_s > 0
        assert report.recommendation != ''


class TestCapillaryInputValidation:
    def test_negative_tension_raises(self):
        with pytest.raises(ValueError):
            capillary_pressure(-1.0, 45.0, 1.0)

    def test_zero_radius_raises(self):
        with pytest.raises(ValueError):
            capillary_pressure(30.0, 45.0, 0.0)

    def test_angle_out_of_range_raises(self):
        with pytest.raises(ValueError):
            capillary_pressure(30.0, 200.0, 1.0)


# ─── thermal.py 測試 ────────────────────────────────────────

class TestThermal:
    def test_short_fin_efficiency_near_one(self):
        # 極短翅片幾乎無熱阻，η 應趨近 1
        eta = fin_efficiency(0.001, 0.0001, 205.0, 30.0)
        assert eta > 0.99

    def test_tall_fin_efficiency_below_one(self):
        # 較高翅片效率應明顯 < 1
        eta = fin_efficiency(0.050, 0.0001, 205.0, 30.0)
        assert eta < 0.95

    def test_higher_kappa_higher_efficiency(self):
        # 更高 κ 翅片效率應更高（熱更容易傳到翅片末端）
        eta_low = fin_efficiency(0.015, 0.0001, 100.0, 30.0)
        eta_high = fin_efficiency(0.015, 0.0001, 400.0, 30.0)
        assert eta_high > eta_low

    def test_fin_efficiency_from_kappa_consistency(self):
        # fin_efficiency_from_kappa 應與 fin_efficiency 直接計算結果一致
        report = fin_efficiency_from_kappa(15.0, 0.1, 205.0, 30.0)
        eta_direct = fin_efficiency(0.015, 0.0001, 205.0, 30.0)
        assert abs(report.fin_efficiency - eta_direct) < 1e-10

    def test_dittus_boelter_positive(self):
        h = dittus_boelter_h(2.0, 0.009, 25.0)
        assert h > 0

    def test_fin_efficiency_invalid_inputs(self):
        with pytest.raises(ValueError):
            fin_efficiency(0, 0.0001, 205.0, 30.0)
        with pytest.raises(ValueError):
            fin_efficiency(0.015, 0, 205.0, 30.0)
        with pytest.raises(ValueError):
            fin_efficiency(0.015, 0.0001, 0, 30.0)


# ─── droplet.py 測試 ────────────────────────────────────────

class TestDroplet:
    def test_weber_number_positive(self):
        We = weber_number(10.0, 0.0002, 998.2, 0.0728)
        assert We > 0

    def test_ohnesorge_number_positive(self):
        Oh = ohnesorge_number(0.0002, 998.2, 1.002e-3, 0.0728)
        assert Oh > 0

    def test_intact_regime_low_we(self):
        We = weber_number(1.0, 0.0002, 998.2, 0.0728)
        Oh = ohnesorge_number(0.0002, 998.2, 1.002e-3, 0.0728)
        assert droplet_regime(We, Oh) == 'intact'

    def test_catastrophic_regime_high_we(self):
        We = weber_number(30.0, 0.002, 998.2, 0.0728)
        Oh = ohnesorge_number(0.002, 998.2, 1.002e-3, 0.0728)
        assert droplet_regime(We, Oh) == 'catastrophic_breakup'

    def test_smd_decreases_with_pressure(self):
        smd_low = spray_droplet_size(1.0, 2.0)
        smd_high = spray_droplet_size(6.0, 2.0)
        assert smd_high < smd_low, "更高壓力應產生更小 SMD"

    def test_smd_invalid_pressure(self):
        with pytest.raises(ValueError):
            spray_droplet_size(0.0, 2.0)


# ─── fouling.py 測試 ────────────────────────────────────────

class TestFouling:
    def test_rf_grows_with_time(self):
        rf1 = kern_seaton_fouling(100, 1.76e-4, 8e-4)
        rf2 = kern_seaton_fouling(2000, 1.76e-4, 8e-4)
        assert rf2 > rf1

    def test_rf_approaches_asymptote(self):
        rf_long = kern_seaton_fouling(1e6, 1.76e-4, 8e-4)
        assert abs(rf_long - 1.76e-4) / 1.76e-4 < 0.001, "長時間後應趨近 Rf*"

    def test_fouling_penalty_between_0_and_100(self):
        penalty = fouling_penalty(1.76e-4, 50.0)
        assert 0 < penalty < 100

    def test_cleaning_interval_finite(self):
        # 使用高 Rf* (0.01) 和較高 U (100) 確保 10% 損失在漸近值範圍內可達到
        # Rf_target = 0.10/(100×0.90) ≈ 1.11e-3 < 0.01 = Rf*，因此結果為有限值
        t = cleaning_interval(100.0, 0.01, 0.001, 10.0)
        assert 0 < t < float('inf')

    def test_cleaning_interval_infinite_when_target_unreachable(self):
        # 漸近熱阻太小，永遠不能造成 50% 損失
        t = cleaning_interval(U_clean=50.0, asymptotic_Rf=1e-6,
                               fouling_rate_constant=1e-3, target_efficiency_loss_pct=50.0)
        assert t == float('inf')

    def test_analyse_fouling_report(self):
        report = analyse_fouling(1000, 'ac_indoor_unit')
        assert report.current_Rf > 0
        assert 0 <= report.efficiency_penalty_pct < 100
        assert report.recommendation != ''

    def test_fouling_invalid_time(self):
        with pytest.raises(ValueError):
            kern_seaton_fouling(-1, 1.76e-4, 8e-4)

    def test_fouling_invalid_environment(self):
        with pytest.raises(ValueError):
            analyse_fouling(1000, environment='mars_dust')


# ─── corrosion_risk 測試 ─────────────────────────────────────

class TestCorrosionRisk:
    def test_strong_alkali_high_risk_aluminum(self):
        r = corrosion_risk('alkaline_strong', 'aluminum', 10.0)
        assert r.risk_level == 'high', "強鹼對鋁翅片應為高風險"

    def test_neutral_safe_aluminum(self):
        r = corrosion_risk('surfactant_neutral', 'aluminum', 10.0)
        assert r.risk_level == 'safe'

    def test_acid_safe_on_copper(self):
        r = corrosion_risk('acid_mild', 'copper', 10.0)
        # pH 4.0 → medium risk for copper
        assert r.risk_level in ('medium', 'high')

    def test_acid_safe_on_aluminum(self):
        # 弱酸 pH 4.0，短暫接觸對鋁應為 medium（非 high）
        r = corrosion_risk('acid_mild', 'aluminum', 5.0)
        assert r.risk_level in ('medium', 'low')

    def test_recommendation_not_empty(self):
        r = corrosion_risk('alkaline_mild', 'aluminum', 10.0)
        assert len(r.recommendation) > 0

    def test_invalid_cleaner_raises(self):
        with pytest.raises(ValueError):
            corrosion_risk('unknown_cleaner', 'aluminum')

    def test_invalid_material_raises(self):
        with pytest.raises(ValueError):
            corrosion_risk('alkaline_mild', 'titanium')


# ─── water_used_L 測試 ───────────────────────────────────────

class TestWaterUsed:
    def test_water_used_positive(self):
        from skills.fluidsim_skills.cleaning import design_cleaning_system
        r = design_cleaning_system('test', 800, 180, 3.0)
        assert r.water_used_L > 0

    def test_water_used_equals_flow_times_time(self):
        from skills.fluidsim_skills.cleaning import design_cleaning_system
        r = design_cleaning_system('test', 800, 180, 3.0)
        expected = r.nozzle.flowrate_lpm * r.estimated_cleaning_time_min
        assert abs(r.water_used_L - expected) < 1e-9

    def test_higher_pressure_more_water(self):
        from skills.fluidsim_skills.cleaning import design_cleaning_system
        r1 = design_cleaning_system('test', 800, 180, 2.0)
        r2 = design_cleaning_system('test', 800, 180, 6.0)
        assert r2.water_used_L > r1.water_used_L


# ─── 集成測試：comprehensive_report ──────────────────────────

# ─── airflow.py 測試 ────────────────────────────────────────

class TestAirflow:
    def test_pressure_drop_positive(self):
        dp, v_max, Re = fin_channel_pressure_drop(1.5, 1.8, 25.0, 0.1)
        assert dp > 0
        assert v_max > 1.5   # 最小截面速度 > 面速度
        assert Re > 0

    def test_higher_velocity_higher_dp(self):
        dp1, _, _ = fin_channel_pressure_drop(1.0, 1.8, 25.0, 0.1)
        dp2, _, _ = fin_channel_pressure_drop(3.0, 1.8, 25.0, 0.1)
        assert dp2 > dp1

    def test_narrower_gap_higher_dp(self):
        dp1, _, _ = fin_channel_pressure_drop(1.5, 2.5, 25.0, 0.1)
        dp2, _, _ = fin_channel_pressure_drop(1.5, 1.5, 25.0, 0.1)
        assert dp2 > dp1

    def test_fouling_increases_dp(self):
        result = analyse_airflow(1.5, 1.8, 25.0, 0.1, Rf_current=1.4e-4)
        assert result.pressure_drop_fouled_pa >= result.pressure_drop_clean_pa

    def test_zero_fouling_no_penalty(self):
        result = analyse_airflow(1.5, 1.8, 25.0, 0.1, Rf_current=0.0)
        assert result.airflow_reduction_pct == pytest.approx(0.0, abs=1e-6)
        assert result.fouling_layer_um == pytest.approx(0.0, abs=1e-6)

    def test_fouling_layer_thickness_proportional_to_Rf(self):
        d1 = fouling_layer_thickness(1e-4, 'dust')
        d2 = fouling_layer_thickness(2e-4, 'dust')
        assert abs(d2 / d1 - 2.0) < 1e-9

    def test_air_properties_valid(self):
        props = air_properties(25.0)
        assert 1.1 < props.density < 1.3
        assert props.dynamic_viscosity > 0
        assert props.prandtl > 0

    def test_invalid_velocity_raises(self):
        with pytest.raises(ValueError):
            fin_channel_pressure_drop(0.0, 1.8, 25.0, 0.1)

    def test_invalid_pitch_raises(self):
        with pytest.raises(ValueError):
            fin_channel_pressure_drop(1.5, 0.05, 25.0, 0.1)  # pitch < thickness


class TestComprehensiveReport:
    def test_generates_without_error(self):
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'skills'))
        from design_assist.scripts.comprehensive_report import generate_report

        class Args:
            equipment = '測試機台'
            type = 'split-1.5hp'
            width = None
            height = None
            supply = 3.0
            contamination = 'grease_light'
            fin_material = 'aluminum'
            fin_spacing = None
            fin_height = 15.0
            fin_thickness = 0.1
            kappa = None
            elapsed_hours = 1000.0
            environment = 'ac_indoor_unit'
            U_clean = 50.0
            target_loss = 10.0
            pipe_d = 9.5
            face_velocity = 1.5

        report = generate_report(Args())
        assert '摘要' in report
        assert '毛細滲透' in report
        assert '積垢' in report
        assert '翅片效率' in report
        assert '空氣側壓降' in report
        assert len(report) > 500

    def test_all_contamination_types(self):
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'skills'))
        from design_assist.scripts.comprehensive_report import generate_report

        class Args:
            type = 'split-1.5hp'
            width = None
            height = None
            supply = 3.0
            fin_material = 'aluminum'
            fin_spacing = None
            fin_height = 15.0
            fin_thickness = 0.1
            kappa = None
            elapsed_hours = 500.0
            environment = 'ac_indoor_unit'
            U_clean = 50.0
            target_loss = 10.0
            pipe_d = 9.5
            face_velocity = 1.5

        for cont in CONTAMINATION_DB.keys():
            Args.equipment = f'測試-{cont}'
            Args.contamination = cont
            report = generate_report(Args())
            assert len(report) > 200, f"contamination={cont} 報告異常短"


from skills.fluidsim_skills.chemistry import rinse_analysis
from skills.fluidsim_skills.roi import energy_roi
from skills.fluidsim_skills.airflow import _FIN_TYPE_CORRECTION


# ─── rinse_analysis 測試 ─────────────────────────────────────────────────────

class TestRinseAnalysis:
    def test_alkaline_cleaner_needs_rinse(self):
        r = rinse_analysis(cleaner_ph=10.0, cleaner_volume_L=1.0)
        assert r.total_rinse_L > 0
        assert r.dilution_factor > 1

    def test_neutral_cleaner_no_rinse_needed(self):
        r = rinse_analysis(cleaner_ph=7.0, cleaner_volume_L=1.0)
        assert r.dilution_factor == 1.0
        assert r.total_rinse_L == 0.0

    def test_acid_cleaner_compliant_after_rinse(self):
        r = rinse_analysis(cleaner_ph=4.0, cleaner_volume_L=0.5, rounds=3)
        assert r.estimated_final_ph >= 6.0

    def test_strong_alkali_high_dilution(self):
        r_mild = rinse_analysis(cleaner_ph=9.5, cleaner_volume_L=1.0)
        r_strong = rinse_analysis(cleaner_ph=12.0, cleaner_volume_L=1.0)
        assert r_strong.dilution_factor > r_mild.dilution_factor

    def test_invalid_ph_raises(self):
        with pytest.raises(ValueError):
            rinse_analysis(cleaner_ph=15.0, cleaner_volume_L=1.0)

    def test_invalid_volume_raises(self):
        with pytest.raises(ValueError):
            rinse_analysis(cleaner_ph=9.0, cleaner_volume_L=0.0)

    def test_more_rounds_same_total_less_per_round(self):
        r3 = rinse_analysis(cleaner_ph=10.0, cleaner_volume_L=1.0, rounds=3)
        r6 = rinse_analysis(cleaner_ph=10.0, cleaner_volume_L=1.0, rounds=6)
        assert abs(r3.total_rinse_L - r6.total_rinse_L) < 0.01  # 總量相同
        assert r6.volume_per_round_L < r3.volume_per_round_L      # 每輪較少


# ─── energy_roi 測試 ─────────────────────────────────────────────────────────

class TestEnergyROI:
    def test_positive_extra_kwh(self):
        r = energy_roi(rated_power_kw=1.0, power_increase_pct=5.0)
        assert r.annual_extra_kwh > 0

    def test_zero_increase_zero_extra(self):
        r = energy_roi(rated_power_kw=1.0, power_increase_pct=0.0)
        assert r.annual_extra_kwh == 0.0
        assert r.payback_months == float('inf')

    def test_higher_increase_higher_kwh(self):
        r1 = energy_roi(rated_power_kw=1.0, power_increase_pct=2.0)
        r2 = energy_roi(rated_power_kw=1.0, power_increase_pct=10.0)
        assert r2.annual_extra_kwh > r1.annual_extra_kwh

    def test_co2_proportional_to_kwh(self):
        r = energy_roi(rated_power_kw=1.0, power_increase_pct=5.0,
                       grid_emission_factor=0.5)
        assert abs(r.co2_reduction_kg - r.annual_extra_kwh * 0.5) < 0.01

    def test_payback_decreases_with_higher_savings(self):
        r_low  = energy_roi(rated_power_kw=0.5, power_increase_pct=1.0,
                            cleaning_cost=1500)
        r_high = energy_roi(rated_power_kw=5.0, power_increase_pct=20.0,
                            cleaning_cost=1500)
        assert r_high.payback_months < r_low.payback_months

    def test_invalid_power_raises(self):
        with pytest.raises(ValueError):
            energy_roi(rated_power_kw=0.0, power_increase_pct=5.0)


# ─── fin_type 修正係數測試 ─────────────────────────────────────────────────────

class TestFinType:
    def test_plain_lowest_dp(self):
        dp_p, _, _ = fin_channel_pressure_drop(1.5, 1.8, 25, 0.1, fin_type='plain')
        dp_w, _, _ = fin_channel_pressure_drop(1.5, 1.8, 25, 0.1, fin_type='wavy')
        dp_l, _, _ = fin_channel_pressure_drop(1.5, 1.8, 25, 0.1, fin_type='louvered')
        assert dp_p < dp_w < dp_l

    def test_correction_factors_match_constants(self):
        dp_p, _, _ = fin_channel_pressure_drop(1.5, 1.8, 25, 0.1, fin_type='plain')
        dp_l, _, _ = fin_channel_pressure_drop(1.5, 1.8, 25, 0.1, fin_type='louvered')
        ratio = dp_l / dp_p
        assert abs(ratio - _FIN_TYPE_CORRECTION['louvered']) < 0.01

    def test_invalid_fin_type_raises(self):
        with pytest.raises(ValueError):
            fin_channel_pressure_drop(1.5, 1.8, 25, 0.1, fin_type='spiral')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
