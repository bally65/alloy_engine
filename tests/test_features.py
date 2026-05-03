import numpy as np
import pytest

from alloy_engine.data.elements import ELEMENTS, ELEMENT_PROPERTIES, NUM_ELEMENTS, NUM_PROPS
from alloy_engine.features.engineering import composition_to_features_np


@pytest.fixture
def pure_fe() -> np.ndarray:
    """純 Fe 組成向量（one-hot）"""
    c = np.zeros((1, NUM_ELEMENTS), dtype=np.float32)
    c[0, ELEMENTS.index("Fe")] = 1.0
    return c


def test_output_shape():
    rng  = np.random.default_rng(0)
    comp = rng.dirichlet(np.ones(NUM_ELEMENTS), size=16).astype(np.float32)
    feat = composition_to_features_np(comp)
    assert feat.shape == (16, NUM_PROPS * 4), f"期望 (16, {NUM_PROPS*4})，得到 {feat.shape}"


def test_pure_element_weighted_mean(pure_fe):
    """純 Fe 的加權平均應等於 Fe 的屬性值。"""
    feat    = composition_to_features_np(pure_fe)          # (1, 40)
    w_mean  = feat[0, :NUM_PROPS]                           # 前 10 維
    fe_props = np.array(
        [ELEMENT_PROPERTIES["Fe"][p] for p in
         ["Z", "M", "r", "EN", "Vel", "IE", "mu", "rho", "E"]],
        dtype=np.float32,
    )
    np.testing.assert_allclose(w_mean, fe_props, rtol=1e-4)


def test_weighted_var_pure_element(pure_fe):
    """純元素的加權變異數應為 0。"""
    feat   = composition_to_features_np(pure_fe)
    w_var  = feat[0, NUM_PROPS : 2 * NUM_PROPS]
    np.testing.assert_allclose(w_var, 0.0, atol=1e-5)


def test_no_nan():
    rng  = np.random.default_rng(42)
    comp = rng.dirichlet(np.ones(NUM_ELEMENTS), size=64).astype(np.float32)
    feat = composition_to_features_np(comp)
    assert not np.isnan(feat).any(), "特徵中含有 NaN"
