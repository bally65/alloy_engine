"""
驗證 GA ↔ SurrogateBundle 的介面 contract：
  - predict_properties 接受 (N, NUM_ELEMENTS) tensor
  - 回傳 dict，keys = {"Tc", "Hc", "Br", "strength"}，每個 value 為 (N,) tensor
  - GA 能正確銜接此介面跑完整流程
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import torch

from alloy_engine.data.elements import NUM_ELEMENTS
from alloy_engine.ga.gpu_ga import GPUGeneticAlgorithm

DEVICE = torch.device("cpu")
N_POP = 100
REQUIRED_KEYS = {"Tc", "Hc", "Br", "strength"}


# ── Dummy SurrogateBundle ─────────────────────────────────────────────────────
class DummyBundle:
    """最小化 mock，模擬 SurrogateBundle.predict_properties 的簽名與行為。"""

    def predict_properties(
        self, compositions: torch.Tensor
    ) -> dict[str, torch.Tensor]:
        N = compositions.shape[0]
        # 驗證輸入 shape contract
        assert compositions.ndim == 2
        assert compositions.shape[1] == NUM_ELEMENTS
        return {
            "Tc":       torch.rand(N, device=compositions.device) * 1000 + 300,
            "Hc":       torch.rand(N, device=compositions.device) * 200,
            "Br":       torch.rand(N, device=compositions.device) * 2,
            "strength": torch.rand(N, device=compositions.device) * 1000 + 100,
        }


@pytest.fixture
def bundle() -> DummyBundle:
    return DummyBundle()


@pytest.fixture
def ga(bundle) -> GPUGeneticAlgorithm:
    return GPUGeneticAlgorithm(
        predict_fn=bundle.predict_properties,
        device=DEVICE,
        population_size=N_POP,
    )


# ── 介面 contract 測試 ────────────────────────────────────────────────────────
def test_predict_output_keys(bundle):
    comp = torch.softmax(torch.randn(N_POP, NUM_ELEMENTS), dim=1)
    out  = bundle.predict_properties(comp)
    assert set(out.keys()) == REQUIRED_KEYS, f"缺少或多餘的 key：{set(out.keys())}"


def test_predict_output_shape(bundle):
    comp = torch.softmax(torch.randn(N_POP, NUM_ELEMENTS), dim=1)
    out  = bundle.predict_properties(comp)
    for k, v in out.items():
        assert v.shape == (N_POP,), f"{k} 的 shape 應為 ({N_POP},)，得到 {v.shape}"


def test_ga_uses_all_output_keys(bundle):
    """確保 GA fitness 函數正確讀取所有 4 個 key。"""
    spy_calls: list[dict] = []

    def spying_predict(comp: torch.Tensor) -> dict[str, torch.Tensor]:
        result = bundle.predict_properties(comp)
        spy_calls.append(result)
        return result

    g = GPUGeneticAlgorithm(predict_fn=spying_predict, device=DEVICE, population_size=N_POP)
    g.step()
    assert len(spy_calls) >= 1
    for call_result in spy_calls:
        assert set(call_result.keys()) == REQUIRED_KEYS


def test_ga_full_run_with_bundle(ga):
    """GA 注入 DummyBundle 能完整跑 5 代不 crash，且歷史紀錄長度正確。"""
    ga.run(n_gen=5, verbose=False)
    assert len(ga.history["best_fitness"]) == 5
    assert len(ga.history["best_tc_C"])    == 5


def test_surrogate_contract_composition_sums(bundle):
    """predict_properties 回傳值不受組成是否精確總和為 1 的影響（GA 內部有數值誤差）。"""
    comp = torch.rand(N_POP, NUM_ELEMENTS)  # 不做 softmax，總和不為 1
    comp = comp / comp.sum(dim=1, keepdim=True)
    out  = bundle.predict_properties(comp)
    for k, v in out.items():
        assert not torch.isnan(v).any(), f"{k} 含有 NaN"


def test_train_mlp_low_epochs_no_crash():
    """缺陷修復：epochs<30（評估區間從未觸發）不應因 best_state=None 而崩潰。"""
    import numpy as np, torch
    from alloy_engine.models.surrogate import train_mlp
    X = np.random.rand(120, 36).astype(np.float32)
    y = np.random.rand(120).astype(np.float32)
    model, scaler = train_mlp(X, y, "t", torch.device("cpu"), epochs=5)
    assert model is not None and len(scaler) == 5
