"""Check new 36-dim features for degenerate dimensions."""
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from alloy_engine.data.synthetic import generate_training_data
from alloy_engine.features.engineering import composition_to_features_np
from alloy_engine.data.elements import PROP_NAMES, NUM_PROPS

print(f"PROP_NAMES ({len(PROP_NAMES)}): {PROP_NAMES}")
print(f"Feature dims: {NUM_PROPS} props × 4 stats = {NUM_PROPS * 4}")

comps, *_ = generate_training_data(n_samples=8000, seed=42)
X = composition_to_features_np(comps.astype("float32"))
print(f"X shape: {X.shape}")

stds = X.std(0)
means = X.mean(0)
stat_names = ["wmean", "wvar", "max", "min"]
prop_stat = [f"{p}_{s}" for p in PROP_NAMES for s in stat_names]

print(f"\nDegenerate dims (std < 0.01):")
degenerate = [(i, prop_stat[i], means[i], stds[i]) for i in range(len(stds)) if stds[i] < 0.01]
if degenerate:
    for i, name, m, s in degenerate:
        print(f"  dim {i:2d} ({name}): mean={m:.6f}  std={s:.6f}")
else:
    print("  None — all dims have std >= 0.01")

print(f"\nAll dims summary:")
print(f"  std min={stds.min():.6f}  max={stds.max():.2f}  mean={stds.mean():.4f}")
print(f"\nBottom 5 stds:")
for i in np.argsort(stds)[:5]:
    print(f"  dim {i:2d} ({prop_stat[i]}): std={stds[i]:.6f}  mean={means[i]:.4f}")
