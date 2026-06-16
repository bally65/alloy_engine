"""比較飛輪式 vs 活塞式架構：各跑 GA（整機 device-level 目標），
輸出各架構各情境的最佳合金 + 預測功率密度/效率。

架構 ↔ 材料共同設計：同一 surrogate，但不同架構的 ε / util / L / B_app
（見 thermomagnetic/architectures.py）會讓 GA 選出不同最佳配方與不同 P/η。

用法：
  python scripts/compare_architectures.py --checkpoint models/checkpoints/bundle.pt \
      --scenario all --population-size 20000 --n-generations 60 --seed 42 --device cpu
"""
from __future__ import annotations

import argparse
import logging
import random
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).parent.parent))

from alloy_engine.config import CHECKPOINT_DIR, DEFAULT_DEVICE
from alloy_engine.data.elements import ELEMENTS
from alloy_engine.ga.gpu_ga import GPUGeneticAlgorithm
from alloy_engine.models.surrogate import SurrogateBundle
from alloy_engine.scenarios import SCENARIOS
from alloy_engine.thermomagnetic.architectures import ARCHITECTURES

logging.basicConfig(level=logging.WARNING)


def set_seed(s: int) -> None:
    random.seed(s); np.random.seed(s); torch.manual_seed(s)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(s)


def formula(comp: np.ndarray, top: int = 4) -> str:
    idx = np.argsort(comp)[::-1]
    return "".join(f"{ELEMENTS[i]}{comp[i]*100:.0f}" for i in idx[:top] if comp[i] > 0.01)


def main() -> None:
    p = argparse.ArgumentParser(description="飛輪 vs 活塞架構 GA 對比")
    p.add_argument("--checkpoint", type=Path, default=CHECKPOINT_DIR / "bundle.pt")
    p.add_argument("--scenario", type=str, default="all")
    p.add_argument("--population-size", type=int, default=20000)
    p.add_argument("--n-generations", type=int, default=60)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--w-device", type=float, default=0.5)
    p.add_argument("--device", type=str, default="cpu")
    args = p.parse_args()

    device = torch.device(args.device)
    bundle = SurrogateBundle.load(args.checkpoint, device=device)
    scen = SCENARIOS if args.scenario == "all" else {args.scenario: SCENARIOS[args.scenario]}

    rows = []
    for sname, cfg in scen.items():
        for akey, arch in ARCHITECTURES.items():
            set_seed(args.seed)
            ga = GPUGeneticAlgorithm(
                predict_fn=bundle.predict_properties, device=device,
                population_size=args.population_size, mode="thermomagnetic",
                w_device=args.w_device, **arch.ga_kwargs(), **cfg,
            )
            _pop, fit, info = ga.run(n_gen=args.n_generations, verbose=False)
            bi = int(fit.argmax())
            comp = _pop[bi].cpu().numpy()
            rows.append(dict(
                scenario=sname, arch=akey, formula=formula(comp),
                Tc_C=float(info["tc"][bi]) - 273.15,
                delta_M=float(info["delta_M"][bi]),
                eta_pct=(float(info["device_eta"][bi]) * 100 if "device_eta" in info else float("nan")),
                P_kW_m3=(float(info["device_power_W_m3"][bi]) / 1e3 if "device_power_W_m3" in info else float("nan")),
                fitness=float(fit[bi]),
            ))

    print(f"\n{'scenario':<18}{'arch':<9}{'best_formula':<22}"
          f"{'Tc_C':>7}{'dM_T':>7}{'eta%':>7}{'P_kW/m3':>10}{'fitness':>9}")
    print("-" * 89)
    for r in rows:
        print(f"{r['scenario']:<18}{r['arch']:<9}{r['formula']:<22}"
              f"{r['Tc_C']:>7.0f}{r['delta_M']:>7.3f}{r['eta_pct']:>7.2f}"
              f"{r['P_kW_m3']:>10.1f}{r['fitness']:>9.4f}")


if __name__ == "__main__":
    main()
