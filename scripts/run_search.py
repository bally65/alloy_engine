"""
載入 checkpoint → 執行 GA 搜尋 → 匯出 CSV + 圖表。

使用範例：
  python scripts/run_search.py
  python scripts/run_search.py --scenario 低溫廢熱_150C
  python scripts/run_search.py --scenario all --population-size 50000 --n-generations 50
  python scripts/run_search.py --no-chemistry-constraints --output-dir results/no_constraints
  python scripts/run_search.py --diversity-filter --diversity-k 5
"""
import argparse
import logging
import sys
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless：存檔不開視窗

import numpy as np
import pandas as pd
import torch

sys.path.insert(0, str(Path(__file__).parent.parent))

from alloy_engine.config import (
    CHECKPOINT_DIR,
    DEFAULT_DEVICE,
    DEFAULT_N_GENERATIONS,
    DEFAULT_POPULATION_SIZE,
)
from alloy_engine.data.elements import ELEMENTS
from alloy_engine.ga.gpu_ga import GPUGeneticAlgorithm, diversity_select
from alloy_engine.models.surrogate import SurrogateBundle
from alloy_engine.scenarios import SCENARIOS
from alloy_engine.visualization import plot_composition_heatmap, plot_convergence

logger = logging.getLogger("run_search")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="執行 GA 合金搜尋")
    p.add_argument(
        "--scenario", type=str, default="all",
        help=f"情境名稱或 all，可選：{list(SCENARIOS.keys())} / all",
    )
    p.add_argument("--population-size",          type=int,  default=DEFAULT_POPULATION_SIZE)
    p.add_argument("--n-generations",            type=int,  default=DEFAULT_N_GENERATIONS)
    p.add_argument("--checkpoint",               type=Path, default=CHECKPOINT_DIR / "bundle.pt")
    p.add_argument("--output-dir",               type=Path, default=Path("results"))
    p.add_argument("--device",                   type=str,  default=None)
    p.add_argument("--top-n",                    type=int,  default=10,
                   help="每個情境保留前 N 名（diversity-filter 啟用時以 --diversity-k 覆蓋）")
    p.add_argument("--no-chemistry-constraints", action="store_true",
                   help="停用化學可合成性懲罰（對照實驗用）")
    p.add_argument("--diversity-filter",         action="store_true",
                   help="啟用 K-means 多樣性篩選：從每個 cluster 取 fitness 最高的 1 個")
    p.add_argument("--diversity-k",              type=int,  default=5,
                   help="K-means 聚類數 = 輸出候選數（--diversity-filter 時生效）")
    p.add_argument("--diversity-pool",           type=int,  default=1000,
                   help="聚類母體大小（先取 fitness 前 N 名再做 K-means）")
    p.add_argument("--mode",                     type=str, default="softmag",
                   choices=["softmag", "thermomagnetic"],
                   help="GA fitness mode: softmag (default) or thermomagnetic")
    p.add_argument("--enable-uncertainty",       action="store_true",
                   help="啟用 MC Dropout uncertainty penalty（每 step 30 倍慢，建議搭配小族群）")
    p.add_argument("--n-mc-samples",             type=int,  default=20,
                   help="MC Dropout 取樣次數（--enable-uncertainty 時生效）")
    p.add_argument("--uncertainty-weight",       type=float, default=0.10,
                   help="Uncertainty penalty 最大佔 fitness 比例（預設 0.10）")
    p.add_argument("--min-delta-m-threshold",    type=float, default=0.20,
                   help="delta_M 硬約束下限 (sweep 分析用，預設 0.20)")
    p.add_argument("--w-device",                  type=float, default=0.0,
                   help="整機級目標權重（>0 時 GA 直接最佳化發電機功率密度×效率；"
                        "thermomagnetic mode 生效）")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    device = torch.device(args.device) if args.device else DEFAULT_DEVICE
    logger.info("運算裝置: %s", device)
    logger.info("化學約束: %s", "停用" if args.no_chemistry_constraints else "啟用")
    logger.info("多樣性篩選: %s", f"啟用 (K={args.diversity_k})" if args.diversity_filter else "停用")
    logger.info("GA mode: %s", args.mode)
    logger.info("Uncertainty penalty: %s", f"啟用 (n_mc={args.n_mc_samples}, w={args.uncertainty_weight})" if args.enable_uncertainty else "停用")

    # 1. 載入 checkpoint
    if not args.checkpoint.exists():
        logger.error("找不到 checkpoint：%s  請先執行 train_surrogate.py", args.checkpoint)
        sys.exit(1)
    bundle = SurrogateBundle.load(args.checkpoint, device=device)
    logger.info("已載入 checkpoint：%s", args.checkpoint)

    # 2. 決定要跑哪些情境
    if args.scenario == "all":
        scenarios_to_run = SCENARIOS
    elif args.scenario in SCENARIOS:
        scenarios_to_run = {args.scenario: SCENARIOS[args.scenario]}
    else:
        logger.error("未知情境：%s", args.scenario)
        sys.exit(1)

    # 3. 執行 GA
    results: dict = {}
    for name, cfg in scenarios_to_run.items():
        logger.info("=" * 70)
        logger.info("情境: %s  |  目標 Tc = %d°C  |  σy ≥ %d MPa",
                    name, cfg["target_tc_celsius"], cfg["min_strength_mpa"])
        logger.info("=" * 70)

        ga = GPUGeneticAlgorithm(
            predict_fn=bundle.predict_properties,
            device=device,
            population_size=args.population_size,
            enable_chemistry_constraints=not args.no_chemistry_constraints,
            enable_uncertainty=args.enable_uncertainty,
            predict_fn_uncertainty=(bundle.predict_properties_with_uncertainty
                                    if args.enable_uncertainty else None),
            n_mc_samples=args.n_mc_samples,
            uncertainty_weight=args.uncertainty_weight,
            mode=args.mode,
            min_delta_m_threshold=args.min_delta_m_threshold,
            w_device=args.w_device,
            **cfg,
        )
        t0 = time.time()
        pop, fit, info = ga.run(n_gen=args.n_generations, verbose=True)
        elapsed = time.time() - t0

        total_evals = args.population_size * args.n_generations
        logger.info("耗時: %.1f 秒  |  總評估: %.1f M  |  吞吐: %.2f M/s",
                    elapsed, total_evals / 1e6, total_evals / elapsed / 1e6)

        # 4. 選取 Top N（有無 diversity filter）
        pop_np = pop.cpu().numpy()
        fit_np = fit.cpu().numpy()

        if args.diversity_filter:
            top_idx = diversity_select(
                pop_np, fit_np,
                n_clusters=args.diversity_k,
                pool_size=args.diversity_pool,
            )
            # 在 cluster 代表中依 fitness 降序排列
            top_idx = top_idx[np.argsort(fit_np[top_idx])[::-1]]
            logger.info("多樣性篩選：從前 %d 名中聚 %d 類，選出 %d 個代表",
                        args.diversity_pool, args.diversity_k, len(top_idx))
        else:
            top_idx = np.argsort(fit_np)[::-1][: args.top_n]

        res_entry = {
            "config":    cfg,
            "top_comps": pop_np[top_idx],
            "top_fit":   fit_np[top_idx],
            "top_tc_C":  (info["tc"].cpu().numpy()[top_idx] - 273.15),
            "top_hc":    info["hc"].cpu().numpy()[top_idx],
            "top_br":    info["br"].cpu().numpy()[top_idx],
            "top_str":   info["strength"].cpu().numpy()[top_idx],
            "top_tc_std": info["tc_std"].cpu().numpy()[top_idx],
            "history":   dict(ga.history),
        }
        if "delta_M" in info:
            res_entry["top_delta_M"]  = info["delta_M"].cpu().numpy()[top_idx]
            res_entry["top_kappa"]    = info["kappa"].cpu().numpy()[top_idx]
            res_entry["top_M_at_low"] = info["M_at_low"].cpu().numpy()[top_idx]
            res_entry["top_M_at_high"]= info["M_at_high"].cpu().numpy()[top_idx]
        if "device_score" in info:
            res_entry["top_device_eta"]   = info["device_eta"].cpu().numpy()[top_idx]
            res_entry["top_device_power"] = info["device_power_W_m3"].cpu().numpy()[top_idx]
        results[name] = res_entry

    # 5. 視覺化
    plot_convergence(results, save_path=args.output_dir / "ga_convergence.png")
    plot_composition_heatmap(results, save_path=args.output_dir / "top_compositions.png")

    # 6. 匯出 CSV
    rows = []
    for name, res in results.items():
        for i in range(len(res["top_comps"])):
            c   = res["top_comps"][i]
            row = {"scenario": name, "rank": i + 1}
            for j, e in enumerate(ELEMENTS):
                row[f"{e}_at%"] = round(c[j] * 100, 2)
            row["Tc_C"]        = round(float(res["top_tc_C"][i]),  1)
            row["Hc_A_m"]      = round(float(res["top_hc"][i]),    2)
            row["Br_T"]        = round(float(res["top_br"][i]),     3)
            row["sigma_y_MPa"] = round(float(res["top_str"][i]),    0)
            row["Tc_std_C"]    = round(float(res["top_tc_std"][i]), 2)
            if "top_delta_M" in res:
                row["delta_M_T"]   = round(float(res["top_delta_M"][i]),   4)
                row["kappa_WmK"]   = round(float(res["top_kappa"][i]),     1)
                row["M_at_low_T"]  = round(float(res["top_M_at_low"][i]),  4)
                row["M_at_high_T"] = round(float(res["top_M_at_high"][i]), 4)
            if "top_device_eta" in res:
                row["device_eta_%"]     = round(float(res["top_device_eta"][i]) * 100, 4)
                row["device_P_kW_m3"]   = round(float(res["top_device_power"][i]) / 1e3, 1)
            row["fitness"]     = round(float(res["top_fit"][i]),    4)
            rows.append(row)

    csv_path = args.output_dir / "top_alloy_candidates.csv"
    pd.DataFrame(rows).to_csv(csv_path, index=False, encoding="utf-8-sig")
    logger.info("已匯出 %d 筆候選合金 → %s", len(rows), csv_path)


if __name__ == "__main__":
    main()
