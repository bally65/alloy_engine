"""
D12：發電側整機對標（reference devices）測試。
執行: python -m pytest tests/test_reference_devices.py -v
"""
from alloy_engine.thermomagnetic import reference_devices as rd
from alloy_engine.thermomagnetic import reference_materials as rm
from alloy_engine.thermomagnetic.generator_design import design_tmg


class TestReferenceDeviceData:
    def test_entries_present(self):
        assert len(rd.REFERENCE_DEVICES) >= 4
        assert "Nat.Commun.2023 Gd" in rd.REFERENCE_DEVICES

    def test_delta_t_positive(self):
        for dev in rd.REFERENCE_DEVICES.values():
            assert dev.delta_T_K > 0

    def test_power_density_unit_conversion(self):
        dev = rd.get("Nat.Commun.2023 Gd")
        assert dev.power_density_mW_cm3 == 3.2
        assert dev.power_density_W_m3 == 3200.0  # 1 mW/cm³ = 1000 W/m³

    def test_real_bands_sane(self):
        lo, hi = rd.REAL_POWER_DENSITY_BAND_mW_cm3
        assert 0 < lo < hi < 100          # 真實原型在 mW/cm³ 量級
        flo, fhi = rd.REAL_FREQUENCY_BAND_Hz
        assert 0 < flo < fhi < 100        # 真實 TMG 為次赫至數赫

    def test_unknown_raises(self):
        import pytest
        with pytest.raises(KeyError):
            rd.get("不存在的原型")


class TestModelVsReality:
    """錨點的核心發現：發電側模型是理想化上界（不可被靜默改成「已校準」）。"""

    def _our_pd_matched(self, dev) -> float:
        mat = rm.get("Gd (純釓)")
        r = design_tmg(
            T_cold_C=dev.T_cold_C, T_hot_C=dev.T_hot_C,
            delta_M_T=mat.delta_M_T, rho=mat.rho, cp_specific=mat.cp_specific,
            kappa=mat.kappa, delta_S_M=mat.delta_S_M,
            B_applied_T=1.0, plate_thickness_m=1e-3, f_max_Hz=dev.frequency_Hz,
        )
        return r.power_density_W_m3 / 1000.0, r.eta_relative_carnot * 100.0

    def test_power_density_is_optimistic_upper_bound(self):
        # 即使同頻，本引擎 Gd P/V 仍顯著高於真實（理想化上界），但在 ~3–50× 量級內
        dev = rd.get("Nat.Commun.2023 Gd")
        pd_model, _ = self._our_pd_matched(dev)
        ratio = pd_model / dev.power_density_mW_cm3
        assert 3.0 < ratio < 50.0, f"P/V 高估比 {ratio:.1f}× 超出預期量級"

    def test_efficiency_same_order_as_best_real(self):
        # 效率與最佳真實原型同量級（~10× 內），方向為樂觀
        dev = rd.get("Nat.Commun.2023 Gd")
        _, eta_model = self._our_pd_matched(dev)
        assert eta_model > dev.eta_rel_carnot_pct          # 樂觀
        assert eta_model < dev.eta_rel_carnot_pct * 10.0   # 同量級
