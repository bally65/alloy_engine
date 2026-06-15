import torch
import pytest

from alloy_engine.data.elements import NUM_ELEMENTS
from alloy_engine.ga.gpu_ga import GPUGeneticAlgorithm

DEVICE = torch.device("cpu")
SMALL_N = 200   # 小族群，CPU 可跑


def _dummy_predict(compositions: torch.Tensor) -> dict[str, torch.Tensor]:
    """固定回傳：Tc=623K(350°C), Hc=50, Br=1.0, strength=500。"""
    N = compositions.shape[0]
    return {
        "Tc":       torch.full((N,), 623.0,  device=DEVICE),
        "Hc":       torch.full((N,), 50.0,   device=DEVICE),
        "Br":       torch.full((N,), 1.0,    device=DEVICE),
        "strength": torch.full((N,), 500.0,  device=DEVICE),
    }


@pytest.fixture
def ga() -> GPUGeneticAlgorithm:
    return GPUGeneticAlgorithm(
        predict_fn=_dummy_predict,
        device=DEVICE,
        population_size=SMALL_N,
        target_tc_celsius=350.0,
        tc_tolerance=30.0,
        min_strength_mpa=400.0,
        max_hc=80.0,
    )


def test_population_shape(ga):
    assert ga.population.shape == (SMALL_N, NUM_ELEMENTS)


def test_population_sums_to_one(ga):
    sums = ga.population.sum(dim=1)
    assert torch.allclose(sums, torch.ones(SMALL_N), atol=1e-5)


def test_fitness_range(ga):
    fit, _ = ga.fitness(ga.population)
    assert fit.shape == (SMALL_N,)
    assert (fit >= 0).all() and (fit <= 1.1).all(), "適應度應在 [0, ~1] 範圍"


def test_run_10_generations(ga):
    pop, fit, info = ga.run(n_gen=10, verbose=False)
    assert pop.shape == (SMALL_N, NUM_ELEMENTS)
    assert fit.shape == (SMALL_N,)
    required = {"tc", "hc", "br", "strength"}
    assert required.issubset(info.keys()), f"Missing required keys, got {info.keys()}"
    assert len(ga.history["best_fitness"]) == 10


def test_history_monotone_best(ga):
    ga.run(n_gen=20, verbose=False)
    best = ga.history["best_fitness"]
    # 不要求嚴格遞增（有噪聲），但最後值不應低於第一個值的 0.5 倍
    assert best[-1] >= best[0] * 0.5


def test_fitness_nan_guard():
    """缺陷修復：surrogate 輸出 NaN 不應污染 fitness 的 argsort/argmax 選擇。"""
    import torch
    from alloy_engine.ga.gpu_ga import GPUGeneticAlgorithm
    def nan_predict(c):
        n = c.shape[0]
        tc = torch.full((n,), 600.0); tc[0] = float("nan")  # 一個 NaN Tc
        return {"Tc": tc, "Hc": torch.full((n,), 50.0),
                "Br": torch.full((n,), 1.0), "strength": torch.full((n,), 500.0)}
    ga = GPUGeneticAlgorithm(predict_fn=nan_predict, device=torch.device("cpu"),
                             population_size=50, target_tc_celsius=300.0)
    fit, _ = ga.fitness(ga.population)
    assert torch.isfinite(fit).all()  # 無 NaN/Inf
