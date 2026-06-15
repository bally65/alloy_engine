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


class TestTransitionWidthCalibration:
    def test_first_order_sharper_than_gd(self):
        # 一階材料 w 應遠小於二階 Gd（更陡的相變）
        w_gd = lm.get("Gd").transition_width_w_K()
        for n in ("Gd5Si2Ge2", "La(Fe,Si)13H", "(Mn,Fe)2(P,Si)"):
            assert lm.get(n).transition_width_w_K() < w_gd

    def test_first_order_w_physical_range(self):
        # 一階 w 落在 ~2–10K（與 D5 docstring 的 ~5K 一致）
        for n in ("Gd5Si2Ge2", "La(Fe,Si)13H", "(Mn,Fe)2(P,Si)"):
            w = lm.get(n).transition_width_w_K()
            assert 2.0 < w < 10.0

    def test_w_scales_with_fwhm(self):
        # w 與 FWHM 單調
        ms = sorted(lm.LITERATURE_MCE.values(), key=lambda m: m.dSm_fwhm_K)
        ws = [m.transition_width_w_K() for m in ms]
        assert ws == sorted(ws)

    def test_calibrated_w_sharpens_delta_m(self):
        # 用文獻 w 的一階 logistic，比平均場在 Tc 附近給更大 delta_M
        import torch
        from alloy_engine.thermomagnetic.properties import magnetic_thermodynamic_score
        Ms = torch.tensor([1.0]); Tc = torch.tensor([293.0])  # 室溫 Tc(K) ≈ 20°C
        T_target_C, win = 20.0, 15.0                          # 循環跨越 Tc
        w = lm.get("La(Fe,Si)13H").transition_width_w_K()
        mean_field = magnetic_thermodynamic_score(Ms, Tc, T_target_C=T_target_C, delta_T_window=win)
        first_order = magnetic_thermodynamic_score(Ms, Tc, T_target_C=T_target_C,
                                                   delta_T_window=win, transition_width_K=w)
        assert first_order["delta_M"].item() > mean_field["delta_M"].item()


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


class TestRecommend:
    def _recs(self, **kw):
        from alloy_engine.thermomagnetic.recommend import recommend_material
        return recommend_material(**kw)

    def test_cheap_tunable_wins(self):
        recs = self._recs(T_operating_C=80, field_T=2.0)
        # 便宜 + 可調 + 高 ΔS 的一階材料應排前二
        assert {recs[0].name, recs[1].name} == {"La(Fe,Si)13H", "(Mn,Fe)2(P,Si)"}

    def test_expensive_ranks_last(self):
        recs = self._recs(T_operating_C=80, field_T=2.0)
        # Gd5Si2Ge2（Ge 貴）應墊底
        assert recs[-1].name == "Gd5Si2Ge2"

    def test_rare_earth_free_preference_boosts_mnfep(self):
        from alloy_engine.thermomagnetic.recommend import recommend_material
        base = {r.name: r.score for r in recommend_material(25, field_T=1.5)}
        pref = {r.name: r.score for r in recommend_material(25, field_T=1.5, prefer_rare_earth_free=True)}
        # 偏好無稀土 → Mn-Fe-P 分數相對提升
        assert pref["(Mn,Fe)2(P,Si)"] / pref["La(Fe,Si)13H"] > base["(Mn,Fe)2(P,Si)"] / base["La(Fe,Si)13H"]

    def test_higher_field_higher_score(self):
        lo = self._recs(T_operating_C=80, field_T=1.0)[0].dS_at_field
        hi = self._recs(T_operating_C=80, field_T=2.0)[0].dS_at_field
        assert hi > lo

    def test_w_attached_from_literature(self):
        # 推薦結果帶 D5 校準 w
        r = self._recs(T_operating_C=80)[0]
        assert 2.0 < r.w_K < 10.0
