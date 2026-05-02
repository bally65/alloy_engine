"""Check feature labels correctly (features are block-by-stat, not interleaved)."""
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from alloy_engine.data.synthetic import generate_training_data
from alloy_engine.features.engineering import composition_to_features_np
from alloy_engine.data.elements import PROP_NAMES, NUM_PROPS, ELEMENT_PROPERTIES, ELEMENTS

# Correct label order: block-by-stat (wmean x9, wvar x9, max x9, min x9)
stat_names = ["wmean", "wvar", "max", "min"]
prop_stat = [f"{s}_{p}" for s in stat_names for p in PROP_NAMES]

comps, *_ = generate_training_data(n_samples=8000, seed=42)
X = composition_to_features_np(comps.astype("float32"))
stds = X.std(0)
means = X.mean(0)

print("Degenerate dims after Tc removal (std < 0.1):")
print(f"  {'dim':>4}  {'label':<20}  {'mean':>12}  {'std':>12}")
for i in range(len(stds)):
    if stds[i] < 0.1:
        print(f"  {i:4d}  {prop_stat[i]:<20}  {means[i]:12.6f}  {stds[i]:12.6f}")

print(f"\nElement mu values: ", {e: ELEMENT_PROPERTIES[e]['mu'] for e in ELEMENTS})
print(f"\nFor a binary FeNi alloy (Fe=0.2, Ni=0.8):")
import torch
from alloy_engine.features.engineering import composition_to_features_torch
from alloy_engine.data.elements import get_element_matrix, NUM_ELEMENTS
em = torch.from_numpy(get_element_matrix()).float()
comp = torch.zeros(1, NUM_ELEMENTS)
comp[0, 0] = 0.20  # Fe
comp[0, 1] = 0.80  # Ni
feats = composition_to_features_torch(comp, em).numpy()[0]
print(f"  mu_wmean (dim 6):  {feats[6]:.6f}")
print(f"  mu_wvar  (dim 15): {feats[15]:.6f}")
print(f"  mu_max   (dim 24): {feats[24]:.6f}  (training mean={means[24]:.6f}, std={stds[24]:.6f})")
print(f"  mu_min   (dim 33): {feats[33]:.6f}  (training mean={means[33]:.6f}, std={stds[33]:.6f})")
if stds[24] < 1e-3:
    print(f"  -> mu_max z-score for FeNi: {(feats[24]-means[24])/(stds[24]+1e-6):.2e}  EXPLOSION RISK")
if stds[33] < 1e-3:
    print(f"  -> mu_min z-score for FeNi: {(feats[33]-means[33])/(stds[33]+1e-6):.2e}  EXPLOSION RISK")
