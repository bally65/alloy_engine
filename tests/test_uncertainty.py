"""不確定度傳播（UQ）測試。"""
from alloy_engine.thermomagnetic.uncertainty import device_performance_with_uncertainty as uq


class TestUQ:
    def test_returns_error_bars(self):
        r = uq("La(Fe,Si)13H", 47, n_samples=500)
        assert r.power_W_m3_std > 0 and r.eta_rel_carnot_std > 0

    def test_realistic_is_discounted(self):
        r = uq("La(Fe,Si)13H", 47, n_samples=300)
        assert r.power_realistic_W_m3 < r.power_W_m3_mean  # D12 折減

    def test_relative_spread_matches_input(self):
        # 輸出功率相對擺幅應與輸入 ±12% 同量級（線性傳播）
        r = uq("(Mn,Fe)2(P,Si)", 27, n_samples=2000)
        rel = r.power_W_m3_std / r.power_W_m3_mean
        assert 0.05 < rel < 0.25

    def test_reproducible_with_seed(self):
        a = uq("Gd (純釓)", 21, n_samples=300, seed=1)
        b = uq("Gd (純釓)", 21, n_samples=300, seed=1)
        assert a.power_W_m3_mean == b.power_W_m3_mean

    def test_summary_string(self):
        assert "P/V" in uq("La(Fe,Si)13H", 47, n_samples=200).summary()
