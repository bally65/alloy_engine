"""
磁化溫度修正測試（D3）：0K 飽和 ↔ 工作溫度。
執行: python -m pytest tests/test_magnetization_correction.py -v
"""
import numpy as np

from alloy_engine.thermomagnetic.magnetization_correction import (
    reduced_magnetization_meanfield,
    kuzmin_reduced_magnetization,
    saturation_to_working,
    working_to_saturation,
)


class TestReducedMagnetization:
    def test_zero_temp_is_unity(self):
        # m(0)=1（完全有序）
        assert reduced_magnetization_meanfield(0.0, 1000.0) > 0.999

    def test_above_tc_is_zero(self):
        assert reduced_magnetization_meanfield(1100.0, 1000.0) == 0.0
        assert kuzmin_reduced_magnetization(1100.0, 1000.0) == 0.0

    def test_in_range_0_1(self):
        T = np.linspace(0, 1200, 50)
        for fn in (reduced_magnetization_meanfield, kuzmin_reduced_magnetization):
            m = fn(T, 1000.0)
            assert np.all(m >= 0.0) and np.all(m <= 1.0)

    def test_monotone_decreasing(self):
        T = np.linspace(1, 999, 60)
        m = reduced_magnetization_meanfield(T, 1000.0)
        assert np.all(np.diff(m) <= 1e-6)

    def test_meanfield_and_kuzmin_agree_qualitatively(self):
        # 兩模型在半 Tc 都應落在合理區間（非完全有序、非崩潰）
        for fn in (reduced_magnetization_meanfield, kuzmin_reduced_magnetization):
            m = fn(500.0, 1000.0)
            assert 0.5 < m < 1.0


class TestConversion:
    def test_working_below_saturation(self):
        # 0 < T < Tc：工作溫度磁化必低於 0K 飽和
        br_work = saturation_to_working(2.0, 300.0, 1043.0)  # Fe-like
        assert br_work < 2.0

    def test_high_tc_small_correction(self):
        # 高 Tc（Fe 1043K）在室溫修正很小（仍 >90% 飽和）
        br_work = saturation_to_working(2.0, 300.0, 1043.0)
        assert br_work > 0.9 * 2.0

    def test_near_tc_large_correction(self):
        # 低 Tc（Gd 293K）在室溫 290K 已大幅塌縮 → 修正很大
        br_work = saturation_to_working(2.0, 290.0, 293.0)
        assert br_work < 0.5 * 2.0

    def test_round_trip_identity(self):
        # working_to_saturation ∘ saturation_to_working ≈ 恆等
        br0 = 1.8
        work = saturation_to_working(br0, 300.0, 800.0)
        back = working_to_saturation(work, 300.0, 800.0)
        assert abs(back - br0) < 1e-6

    def test_explains_bias_direction(self):
        # 修正把 0K 值往下拉 → 縮小「合成(工作溫度) 低於 MP(0K)」的落差
        # 即：corrected MP 比 raw MP 更接近合成值（更小、更可比）
        mp_0k = 2.2
        mp_corrected = saturation_to_working(mp_0k, 300.0, 1043.0)
        assert mp_corrected < mp_0k
