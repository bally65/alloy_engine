"""
v5.1 Pareto Knee Sweep
Threshold range: 0.25 → 0.50 T (6 points)
Scenario: 中溫廢熱_350C | Pop: 50,000 | Gen: 100
"""
import sys, json, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import torch
import numpy as np
import pandas as pd

from alloy_engine.config import DEFAULT_DEVICE
from alloy_engine.data.elements import ELEMENTS
from alloy_engine.ga.gpu_ga import GPUGeneticAlgorithm
from alloy_engine.models.surrogate import SurrogateBundle
from alloy_engine.scenarios import SCENARIOS

CHECKPOINT = Path("alloy_engine/models/checkpoints/bundle.pt")
OUT_DIR    = Path("analysis/v5.1_pareto_knee")
SCENARIO   = "中溫廢熱_350C"
POP_SIZE   = 50_000
N_GEN      = 100
THRESHOLDS = [0.25, 0.30, 0.35, 0.40, 0.45, 0.50]

device = DEFAULT_DEVICE
bundle = SurrogateBundle.load(CHECKPOINT, device=device)
cfg    = SCENARIOS[SCENARIO]

results = []

for thr in THRESHOLDS:
    tag = f"sweep_v51_{int(thr*100):03d}"
    print(f"\n{'='*65}")
    print(f"Threshold = {thr:.2f} T  [{tag}]")
    print(f"{'='*65}")

    ga = GPUGeneticAlgorithm(
        predict_fn=bundle.predict_properties,
        device=device,
        population_size=POP_SIZE,
        enable_chemistry_constraints=True,
        mode="thermomagnetic",
        min_delta_m_threshold=thr,
        **cfg,
    )

    t0 = time.time()
    pop, fit, info = ga.run(n_gen=N_GEN, verbose=False)
    elapsed = time.time() - t0

    pop_np = pop.cpu().numpy()
    fit_np = fit.cpu().numpy()
    top_idx = int(np.argmax(fit_np))

    comp = pop_np[top_idx]
    tc_c = float(info["tc"].cpu().numpy()[top_idx]) - 273.15
    delta_m = float(info["delta_M"].cpu().numpy()[top_idx])
    kappa   = float(info["kappa"].cpu().numpy()[top_idx])
    strength= float(info["strength"].cpu().numpy()[top_idx])
    hc      = float(info["hc"].cpu().numpy()[top_idx])
    br      = float(info["br"].cpu().numpy()[top_idx])

    # composition highlights
    fe = comp[ELEMENTS.index("Fe")] * 100
    ni = comp[ELEMENTS.index("Ni")] * 100
    co = comp[ELEMENTS.index("Co")] * 100
    cr = comp[ELEMENTS.index("Cr")] * 100
    cu = comp[ELEMENTS.index("Cu")] * 100
    mn = comp[ELEMENTS.index("Mn")] * 100

    # build composition string (only elements > 1%)
    comp_parts = [(e, comp[i]*100) for i, e in enumerate(ELEMENTS) if comp[i]*100 >= 1.0]
    comp_parts.sort(key=lambda x: -x[1])
    comp_str = "-".join(f"{e}{v:.1f}" for e, v in comp_parts)

    top_fit = float(np.max(fit_np))

    row = dict(
        threshold=thr,
        tag=tag,
        top_fit=round(top_fit, 4),
        actual_delta_M=round(delta_m, 4),
        tc_C=round(tc_c, 1),
        tc_offset=round(tc_c - cfg["target_tc_celsius"], 1),
        hc=round(hc, 1),
        br_T=round(br, 3),
        kappa=round(kappa, 1),
        strength_MPa=round(strength, 0),
        Fe=round(fe, 1), Ni=round(ni, 1), Co=round(co, 1),
        Cr=round(cr, 1), Cu=round(cu, 1), Mn=round(mn, 1),
        comp_str=comp_str,
        elapsed_s=round(elapsed, 1),
        reached=(delta_m >= thr),
    )
    results.append(row)

    print(f"  Fitness   : {top_fit:.4f}")
    print(f"  delta_M   : {delta_m:.4f} T  ({'OK reached' if delta_m >= thr else 'BELOW threshold'})")
    print(f"  Tc        : {tc_c:.1f}°C  (offset {tc_c - cfg['target_tc_celsius']:+.1f}°C)")
    print(f"  Br        : {br:.3f} T")
    print(f"  Comp      : {comp_str}")

    # save per-sweep CSV
    sweep_dir = OUT_DIR / tag
    sweep_dir.mkdir(exist_ok=True)
    pd.DataFrame([row]).to_csv(sweep_dir / "top1.csv", index=False)

# Save summary
df = pd.DataFrame(results)
df.to_csv(OUT_DIR / "sweep_summary.csv", index=False)
print("\n\nSWEEP SUMMARY:")
print(df[["threshold","top_fit","actual_delta_M","tc_C","tc_offset","Co","Fe","Cr","reached"]].to_string(index=False))
print(f"\nSaved to {OUT_DIR / 'sweep_summary.csv'}")
