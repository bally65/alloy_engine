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


def test_run_returns_aligned_pop_fit_info():
    """回歸（F-ENG-01）：run() 回傳的 pop 必須與 fit/info 同源。

    對回傳 pop 重新預測性質，應與 info 完全一致。舊版 run() 回傳「演化後
    族群（offspring）」卻搭配「演化前 fit/info」，在此會失敗——匯出的最佳
    合金成分與其旁邊的 Tc/Br/fitness 屬於不同個體。
    """
    def comp_dependent_predict(c):
        n = c.shape[0]
        return {
            "Tc":       300.0 + 1000.0 * c[:, 0],          # 依 Fe 分率
            "Hc":       torch.full((n,), 50.0, device=DEVICE),
            "Br":       0.5 + c[:, 1],                      # 依第二元素分率
            "strength": torch.full((n,), 500.0, device=DEVICE),
        }

    ga = GPUGeneticAlgorithm(
        predict_fn=comp_dependent_predict, device=DEVICE,
        population_size=SMALL_N, target_tc_celsius=350.0, min_strength_mpa=400.0,
    )
    pop, fit, info = ga.run(n_gen=5, verbose=False)

    re = comp_dependent_predict(pop)
    assert torch.allclose(re["Tc"], info["tc"], atol=1e-4), \
        "回傳 pop 的 Tc 與 info['tc'] 不一致 → pop/info 不同源 (F-ENG-01)"
    assert torch.allclose(re["Br"], info["br"], atol=1e-4), \
        "回傳 pop 的 Br 與 info['br'] 不一致 → pop/info 不同源 (F-ENG-01)"
    # argmax 同源：fitness 最高者的成分重新預測 = info 中對應值
    bi = int(fit.argmax())
    assert abs(float(comp_dependent_predict(pop[bi:bi + 1])["Tc"][0])
               - float(info["tc"][bi])) < 1e-4


def test_sparse_projection_caps_active_elements():
    """P1-d：預設啟用稀疏投影，族群非零元素數應 ≤ max_active_elements
    （與 surrogate 訓練支撐一致）；停用則允許稠密 Dirichlet。"""
    ga = GPUGeneticAlgorithm(
        predict_fn=_dummy_predict, device=DEVICE, population_size=SMALL_N,
        target_tc_celsius=350.0, max_active_elements=8,
    )
    assert int((ga.population > 0).sum(dim=1).max()) <= 8, "初始族群應已投影"
    pop, _, _ = ga.run(n_gen=3, verbose=False)
    assert int((pop > 0).sum(dim=1).max()) <= 8, "演化後族群仍應在支撐內"

    ga_dense = GPUGeneticAlgorithm(
        predict_fn=_dummy_predict, device=DEVICE, population_size=SMALL_N,
        target_tc_celsius=350.0, sparse_projection=False,
    )
    assert int((ga_dense.population > 0).sum(dim=1).max()) > 8, \
        "停用投影應允許稠密族群（>8 非零）"
