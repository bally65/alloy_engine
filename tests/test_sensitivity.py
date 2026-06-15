"""
D6：假設參數敏感度分析測試。
執行: python -m pytest tests/test_sensitivity.py -v
"""
import importlib.util
from pathlib import Path

# 由 scripts/ 載入（非套件）
_spec = importlib.util.spec_from_file_location(
    "sensitivity_analysis",
    Path(__file__).resolve().parent.parent / "scripts" / "sensitivity_analysis.py",
)
sa = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sa)


class TestSensitivity:
    def test_structure(self):
        out = sa.run_sensitivity()
        assert "connectivity" in out["sweeps"]
        assert "extra_regeneration" in out["sweeps"]
        for r in out["sweeps"].values():
            assert r["gain_min"] > 0 and r["gain_max"] >= r["gain_min"]

    def test_connectivity_more_sensitive_than_regeneration(self):
        # 結論：connectivity 影響增益、regeneration 在增益比中相消
        out = sa.run_sensitivity()
        conn = out["sweeps"]["connectivity"]["gain_rel_spread"]
        regen = out["sweeps"]["extra_regeneration"]["gain_rel_spread"]
        assert conn > regen

    def test_regeneration_cancels_in_gain_ratio(self):
        # 回熱同時放大 bare 與 composite → 增益比幾乎不變
        out = sa.run_sensitivity()
        assert out["sweeps"]["extra_regeneration"]["gain_rel_spread"] < 0.05

    def test_qualitative_conclusion_robust(self):
        # 即使 connectivity 全範圍掃描，複合仍顯著有益（增益 > ×2）
        out = sa.run_sensitivity()
        assert out["sweeps"]["connectivity"]["gain_min"] > 2.0
