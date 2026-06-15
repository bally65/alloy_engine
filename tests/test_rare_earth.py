"""
稀土元素空間擴張測試（Gd / La）
執行: python -m pytest tests/test_rare_earth.py -v
"""
import numpy as np
import torch

from alloy_engine.data.elements import (
    ELEMENTS, NUM_ELEMENTS, get_element_matrix, ELEMENT_PROPERTIES,
)
from alloy_engine.data.synthetic import physics_based_properties_batch
from alloy_engine.thermomagnetic.properties import (
    KAPPA_PURE, CP_PURE_MOLAR, RHO_PURE_KG_M3,
)


def _comp(d: dict) -> np.ndarray:
    v = np.zeros((1, NUM_ELEMENTS), dtype=np.float32)
    for k, x in d.items():
        v[0, ELEMENTS.index(k)] = x
    return v


class TestElementSpace:
    def test_gd_la_present(self):
        assert "Gd" in ELEMENTS and "La" in ELEMENTS
        assert NUM_ELEMENTS == 14   # 10 base + Gd/La (D2) + P/Ge (D8)

    def test_gd_high_moment(self):
        # Gd 高磁矩是其室溫 MCE 的關鍵
        assert ELEMENT_PROPERTIES["Gd"]["mu"] > 7.0
        assert ELEMENT_PROPERTIES["La"]["mu"] == 0.0

    def test_property_arrays_match_element_count(self):
        # 防止未來加元素時忘了同步更新純元素物性向量
        assert KAPPA_PURE.shape[0] == NUM_ELEMENTS
        assert CP_PURE_MOLAR.shape[0] == NUM_ELEMENTS
        assert RHO_PURE_KG_M3.shape[0] == NUM_ELEMENTS

    def test_element_matrix_shape(self):
        em = get_element_matrix()
        assert em.shape[0] == NUM_ELEMENTS


class TestRareEarthPhysics:
    def test_gd_rich_lower_tc_than_fe(self):
        # Gd 為低 Tc 鐵磁體（293K），Gd-rich 應遠低於 Fe-rich
        tc_gd, _, _, _ = physics_based_properties_batch(_comp({"Gd": 0.9, "Fe": 0.1}))
        tc_fe, _, _, _ = physics_based_properties_batch(_comp({"Fe": 0.9, "Co": 0.1}))
        assert tc_gd[0] < tc_fe[0]

    def test_gd_contributes_remanence(self):
        # Gd 有磁矩 → Br 顯著；La 非磁性 → 與惰性元素相當
        _, _, br_gd, _ = physics_based_properties_batch(_comp({"Gd": 0.6, "Fe": 0.4}))
        _, _, br_la, _ = physics_based_properties_batch(_comp({"La": 0.6, "Cu": 0.4}))
        assert br_gd[0] > br_la[0]

    def test_la_fe_si_pulls_tc_down(self):
        # La-Fe-Si 1:13 相把 Tc 拉向近室溫，應低於同 Fe 量但無 La 的合金
        tc_lafesi, _, _, _ = physics_based_properties_batch(
            _comp({"La": 0.07, "Fe": 0.80, "Si": 0.13}))
        tc_fesi, _, _, _ = physics_based_properties_batch(
            _comp({"Fe": 0.87, "Si": 0.13}))
        assert tc_lafesi[0] < tc_fesi[0]

    def test_batch_width_matches_elements(self):
        comp = np.zeros((5, NUM_ELEMENTS), dtype=np.float32)
        comp[:, 0] = 1.0
        tc, hc, br, sy = physics_based_properties_batch(comp)
        assert tc.shape == (5,)


class TestRareEarthManufacturability:
    """D9：稀土氧化/一階脆裂可製造性懲罰（GA 化學約束）。"""

    def _ga(self):
        from alloy_engine.ga.gpu_ga import GPUGeneticAlgorithm

        def _predict(c):
            n = c.shape[0]
            return {k: torch.full((n,), v) for k, v in
                    (("Tc", 623.0), ("Hc", 50.0), ("Br", 1.0), ("strength", 500.0))}

        return GPUGeneticAlgorithm(
            predict_fn=_predict, device=torch.device("cpu"),
            population_size=8, target_tc_celsius=350.0,
            enable_chemistry_constraints=True,
        )

    def _pop(self, d: dict) -> torch.Tensor:
        v = torch.zeros(1, NUM_ELEMENTS)
        for k, x in d.items():
            v[0, ELEMENTS.index(k)] = x
        return v

    def test_rare_earth_free_alloy_unpenalised(self):
        # Fe-Co 系不含稀土 → 不受 D9 懲罰（懲罰 = 1.0）
        ga = self._ga()
        p = ga._chemistry_penalty(self._pop({"Fe": 0.65, "Co": 0.35}))
        assert torch.isclose(p[0], torch.tensor(1.0), atol=1e-6)

    def test_pure_gd_penalised_but_viable(self):
        # 純 Gd：受氧化懲罰但仍保留可觀可製造分（~0.75，>0.5）
        ga = self._ga()
        p = ga._chemistry_penalty(self._pop({"Gd": 1.0}))
        # mag_base = Gd = 1.0 ≥ 0.40 → 無基底懲罰，僅氧化懲罰
        assert 0.70 < p[0].item() < 0.80

    def test_rare_earth_heavy_penalised_more_than_light(self):
        # 稀土含量越高，可製造懲罰越重（單調）
        ga = self._ga()
        light = ga._chemistry_penalty(self._pop({"La": 0.07, "Fe": 0.80, "Si": 0.13}))
        heavy = ga._chemistry_penalty(self._pop({"La": 0.50, "Fe": 0.40, "Si": 0.10}))
        assert heavy[0] < light[0]

    def test_la_fe_si_retains_competitive_score(self):
        # La-Fe-Si（有效一階 MCE 材料）僅被輕罰（>0.90），不被排除
        ga = self._ga()
        p = ga._chemistry_penalty(self._pop({"La": 0.07, "Fe": 0.80, "Si": 0.13}))
        assert p[0].item() > 0.90

    def test_brittle_interaction_active(self):
        # 稀土 ×(Fe+Si) 交互：同等稀土量下，與 Fe+Si 共存比與 Cu 共存更脆 → 更重罰
        ga = self._ga()
        with_fesi = ga._chemistry_penalty(self._pop({"Gd": 0.20, "Fe": 0.70, "Si": 0.10}))
        with_cu   = ga._chemistry_penalty(self._pop({"Gd": 0.20, "Fe": 0.50, "Cu": 0.30}))
        assert with_fesi[0] < with_cu[0]
