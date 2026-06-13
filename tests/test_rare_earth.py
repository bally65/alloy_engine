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
        assert NUM_ELEMENTS == 12

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
