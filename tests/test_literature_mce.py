"""文獻磁熱校準 + 最低成本分析測試。"""
import importlib.util
from pathlib import Path

from alloy_engine.thermomagnetic import literature_mce as lm


class TestLiteratureData:
    def test_all_materials_present(self):
        assert set(lm.LITERATURE_MCE) >= {"Gd", "Gd5Si2Ge2", "La(Fe,Si)13H", "(Mn,Fe)2(P,Si)"}

    def test_first_order_higher_entropy_than_gd(self):
        # 一階巨磁熱材料 ΔS 應遠大於二階 Gd
        gd = lm.get("Gd").dS_2T
        for n in ("La(Fe,Si)13H", "(Mn,Fe)2(P,Si)", "Gd5Si2Ge2"):
            assert lm.get(n).dS_2T > gd

    def test_field_monotonic(self):
        # ΔS@5T 應 ≥ ΔS@2T（場越大熵變越大）
        for m in lm.LITERATURE_MCE.values():
            assert m.dS_5T >= m.dS_2T

    def test_mnfepsi_rare_earth_free(self):
        assert lm.get("(Mn,Fe)2(P,Si)").rare_earth_free
        assert not lm.get("Gd").rare_earth_free


class TestCostAnalysis:
    def test_ge_makes_gd5sige_expensive(self):
        # Ge ~$1200/kg → Gd5Si2Ge2 應為最貴
        costs = {n: lm.get(n).cost_usd_kg() for n in lm.LITERATURE_MCE}
        assert max(costs, key=costs.get) == "Gd5Si2Ge2"

    def test_lafesi_and_mnfep_cheapest(self):
        costs = {n: lm.get(n).cost_usd_kg() for n in lm.LITERATURE_MCE}
        cheap = sorted(costs, key=costs.get)[:2]
        assert set(cheap) == {"La(Fe,Si)13H", "(Mn,Fe)2(P,Si)"}

    def test_value_per_cost_beats_rare_earth(self):
        # La-Fe-Si / Mn-Fe-P 的效能/成本應遠高於 Gd / Gd5SiGe（>50×）
        fom = {n: lm.get(n).figure_of_merit_per_cost() for n in lm.LITERATURE_MCE}
        assert min(fom["La(Fe,Si)13H"], fom["(Mn,Fe)2(P,Si)"]) > 50 * max(fom["Gd"], fom["Gd5Si2Ge2"])

    def test_ranking_top_is_lafesi(self):
        assert lm.rank_by_value_per_cost()[0][0] == "La(Fe,Si)13H"


class TestScript:
    def test_script_runs(self):
        spec = importlib.util.spec_from_file_location(
            "lowest_cost_material",
            Path(__file__).resolve().parent.parent / "scripts" / "lowest_cost_material.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.main()  # 不應拋例外
