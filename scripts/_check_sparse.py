"""Step 2: Validate sparse Dirichlet distribution."""
import sys, numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from alloy_engine.data.synthetic import generate_training_data
from alloy_engine.data.elements import ELEMENTS, PROP_NAMES, NUM_PROPS
from alloy_engine.features.engineering import composition_to_features_np

# Generate 8000 sparse samples
comps_sp, *_ = generate_training_data(n_samples=8000, seed=42, sparse=True)
comps_dense, *_ = generate_training_data(n_samples=8000, seed=42, sparse=False)

print("=== n_active distribution (sparse) ===")
n_active = (comps_sp > 0).sum(axis=1)
for k in range(1, 10):
    cnt = (n_active == k).sum()
    bar = "#" * (cnt // 20)
    print(f"  {k} elements: {cnt:5d} ({cnt/80:.1f}%)  {bar}")

print("\n=== Element presence frequency ===")
print(f"  {'Elem':<6}  {'Sparse %':>10}  {'Dense %':>10}  {'Sparse mean':>12}  {'Dense mean':>12}")
for i, e in enumerate(ELEMENTS):
    sp_freq  = (comps_sp[:,i] > 0).mean() * 100
    dn_freq  = (comps_dense[:,i] > 0).mean() * 100
    sp_mean  = comps_sp[:,i].mean()
    dn_mean  = comps_dense[:,i].mean()
    print(f"  {e:<6}  {sp_freq:>10.1f}  {dn_freq:>10.1f}  {sp_mean:>12.4f}  {dn_mean:>12.4f}")

print("\n=== Feature std check after sparse training (36-dim) ===")
X_sp = composition_to_features_np(comps_sp)
stds_sp = X_sp.std(0)
print(f"  Feature shape: {X_sp.shape}")
print(f"  std: min={stds_sp.min():.6f}  max={stds_sp.max():.2f}")
n_bad = (stds_sp < 0.01).sum()
print(f"  dims with std < 0.01: {n_bad}")
if n_bad > 0:
    stat_names = ["wmean", "wvar", "max", "min"]
    labels = [f"{s}_{p}" for s in stat_names for p in PROP_NAMES]
    for i, s in enumerate(stds_sp):
        if s < 0.01:
            print(f"    dim {i} ({labels[i]}): std={s:.8f}")

print("\n=== Permalloy z-score check ===")
from alloy_engine.data.elements import NUM_ELEMENTS
stat_names = ["wmean", "wvar", "max", "min"]
labels = [f"{s}_{p}" for s in stat_names for p in PROP_NAMES]

pm = np.zeros((1, NUM_ELEMENTS), dtype=np.float32)
pm[0, ELEMENTS.index("Ni")] = 0.80
pm[0, ELEMENTS.index("Fe")] = 0.20
X_pm = composition_to_features_np(pm)[0]
tr_mean = X_sp.mean(0)
tr_std  = X_sp.std(0)
z = (X_pm - tr_mean) / (tr_std + 1e-6)
print(f"  Permalloy z-scores: min={z.min():.2f}  max={z.max():.2f}")
print(f"  |z| > 10: {(np.abs(z)>10).sum()} dims")
print(f"  |z| > 5 : {(np.abs(z)>5).sum()} dims")
worst = np.argsort(np.abs(z))[::-1][:5]
print("  Top 5 most extreme:")
for i in worst:
    print(f"    dim {i:2d} ({labels[i]:<15}): z={z[i]:+7.2f}  val={X_pm[i]:.4f}  mean={tr_mean[i]:.4f}  std={tr_std[i]:.4f}")
