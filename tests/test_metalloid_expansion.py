"""
類金屬擴張測試（P / Ge，缺陷 D8）：(Mn,Fe)2(P,Si)、La(Fe,Si,Ge)13、氫化 Tc 上修。
執行: python -m pytest tests/test_metalloid_expansion.py -v
"""
import numpy as np
import torch

from alloy_engine.data.elements import (
    ELEMENTS, NUM_ELEMENTS, ELEMENT_PROPERTIES, get_element_matrix,
)
from alloy_engine.data.synthetic import (
    physics_based_properties_batch, hydrogenation_tc_shift_K,
    alpha_vector, BR_ELEM_CONTRIB,
)
from alloy_engine.thermomagnetic.properties import (
    KAPPA_PURE, CP_PURE_MOLAR, RHO_PURE_KG_M3,
)


def _comp(d: dict) -> np.ndarray:
    v = np.zeros((1, NUM_ELEMENTS), dtype=np.float32)
    for k, x in d.items():
        v[0, ELEMENTS.index(k)] = x
    return v


class TestElementSpace:
    def test_p_ge_present(self):
        assert "P" in ELEMENTS and "Ge" in ELEMENTS
        assert NUM_ELEMENTS == 14

    def test_p_ge_nonmagnetic(self):
        assert ELEMENT_PROPERTIES["P"]["mu"] == 0.0
        assert ELEMENT_PROPERTIES["Ge"]["mu"] == 0.0

    def test_all_order_dependent_arrays_aligned(self):
        # 字典建構保證對齊；防止未來加元素時靜默漂移
        assert KAPPA_PURE.shape[0] == NUM_ELEMENTS
        assert CP_PURE_MOLAR.shape[0] == NUM_ELEMENTS
        assert RHO_PURE_KG_M3.shape[0] == NUM_ELEMENTS
        assert get_element_matrix().shape[0] == NUM_ELEMENTS
        assert alpha_vector().shape[0] == NUM_ELEMENTS

    def test_p_low_kappa(self):
        # P 熱導率極低 → 強化「一階低 κ」物理（Mn-Fe-P 系 κ 低）
        assert KAPPA_PURE[ELEMENTS.index("P")] < 5.0


class TestMetalloidPhysics:
    def test_mn_fe_p_si_near_room_tc(self):
        # (Mn,Fe)2(P,Si) 一階相把 Tc 拉向近室溫（≪ 純 Fe 的 ~1043K）
        # 現實配比：金屬 ~2/3 (Mn≈Fe)、類金屬 (P+Si) ~1/3
        tc, _, _, _ = physics_based_properties_batch(
            _comp({"Mn": 0.33, "Fe": 0.34, "P": 0.18, "Si": 0.15}))
        assert 150.0 < tc[0] < 450.0

    def test_ge_substitutes_si_in_lafesi(self):
        # La(Fe,Si,Ge)13：以 Ge 部分替代 Si 仍能形成近室溫 1:13 相
        tc_ge, _, _, _ = physics_based_properties_batch(
            _comp({"La": 0.07, "Fe": 0.80, "Si": 0.07, "Ge": 0.06}))
        tc_pure_fe, _, _, _ = physics_based_properties_batch(_comp({"Fe": 0.93, "Si": 0.07}))
        assert tc_ge[0] < tc_pure_fe[0]

    def test_hydrogenation_raises_lafesi_tc(self):
        # 氫化對 La-Fe-Si 1:13 相有正 Tc 上移；對非 1:13 相幾乎為 0
        shift_lafesi = hydrogenation_tc_shift_K(_comp({"La": 0.07, "Fe": 0.80, "Si": 0.12}))
        shift_plain = hydrogenation_tc_shift_K(_comp({"Fe": 0.70, "Co": 0.30}))
        assert shift_lafesi[0] > 50.0
        assert shift_plain[0] < 5.0

    def test_p_ge_no_remanence(self):
        # P/Ge 非磁性 → 不在 Br 貢獻字典（或為 0）
        assert BR_ELEM_CONTRIB.get("P", 0.0) == 0.0
        assert BR_ELEM_CONTRIB.get("Ge", 0.0) == 0.0


class TestGAWithMetalloids:
    def test_metalloid_brittleness_penalised(self):
        from alloy_engine.ga.gpu_ga import GPUGeneticAlgorithm

        def _predict(c):
            n = c.shape[0]
            return {k: torch.full((n,), v) for k, v in
                    (("Tc", 600.0), ("Hc", 50.0), ("Br", 1.0), ("strength", 500.0))}

        ga = GPUGeneticAlgorithm(predict_fn=_predict, device=torch.device("cpu"),
                                 population_size=8, target_tc_celsius=300.0,
                                 enable_chemistry_constraints=True)

        def comp(d):
            v = torch.zeros(1, NUM_ELEMENTS)
            for k, x in d.items():
                v[0, ELEMENTS.index(k)] = x
            return v

        # 隔離脆性懲罰（足夠鐵磁基底避免基底不足懲罰）：高 P 比無 P down-rank
        brittle = ga._chemistry_penalty(comp({"Fe": 0.55, "P": 0.15, "Si": 0.10, "Co": 0.20}))
        clean   = ga._chemistry_penalty(comp({"Fe": 0.55, "Co": 0.45}))
        assert brittle[0] < clean[0]          # P/Si 類金屬被罰
        assert 0.5 < brittle[0].item() < 1.0  # down-rank 但不歸零

    def test_population_width_14(self):
        from alloy_engine.ga.gpu_ga import GPUGeneticAlgorithm

        def _predict(c):
            n = c.shape[0]
            return {k: torch.full((n,), v) for k, v in
                    (("Tc", 600.0), ("Hc", 50.0), ("Br", 1.0), ("strength", 500.0))}

        ga = GPUGeneticAlgorithm(predict_fn=_predict, device=torch.device("cpu"),
                                 population_size=50, target_tc_celsius=300.0)
        assert ga.population.shape == (50, NUM_ELEMENTS)
