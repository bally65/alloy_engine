"""Diagnose remaining explosion for binary alloys with new 32-dim model."""
import sys, torch, numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from alloy_engine.config import CHECKPOINT_DIR, DEFAULT_DEVICE
from alloy_engine.models.surrogate import SurrogateBundle
from alloy_engine.data.synthetic import generate_training_data
from alloy_engine.features.engineering import composition_to_features_np, composition_to_features_torch
from alloy_engine.data.elements import ELEMENTS, get_element_matrix, PROP_NAMES

device = DEFAULT_DEVICE
bundle = SurrogateBundle.load(CHECKPOINT_DIR / "bundle.pt", device=device)
elem_idx = {e: i for i, e in enumerate(ELEMENTS)}

# Feature labels (block-by-stat)
stat_names = ["wmean", "wvar", "max", "min"]
labels = [f"{s}_{p}" for s in stat_names for p in PROP_NAMES]

# Training feature distribution
comps, *_ = generate_training_data(n_samples=8000, seed=42)
X_train = composition_to_features_np(comps.astype("float32"))
tr_mean = X_train.mean(0)
tr_std  = X_train.std(0)

# Permalloy features
pm = np.zeros((1, len(ELEMENTS)), dtype=np.float32)
pm[0, elem_idx["Ni"]] = 0.80
pm[0, elem_idx["Fe"]] = 0.20
X_pm = composition_to_features_np(pm)[0]

z = (X_pm - tr_mean) / (tr_std + 1e-6)
print("Permalloy z-scores (32-dim, new model):")
print(f"  min z={z.min():.2f}  max z={z.max():.2f}")
print(f"  dims with |z|>10: {(np.abs(z)>10).sum()}")
print(f"  dims with |z|>50: {(np.abs(z)>50).sum()}")
print("\nTop 8 most extreme dims:")
for i in np.argsort(np.abs(z))[::-1][:8]:
    print(f"  dim {i:2d} ({labels[i]:<15}): z={z[i]:+10.2f}  val={X_pm[i]:.6f}  tr_mean={tr_mean[i]:.6f}  tr_std={tr_std[i]:.6f}")

# Alnico5 for comparison
al5 = np.zeros((1, len(ELEMENTS)), dtype=np.float32)
al5[0, elem_idx["Fe"]] = 0.51
al5[0, elem_idx["Co"]] = 0.24
al5[0, elem_idx["Ni"]] = 0.14
al5[0, elem_idx["Al"]] = 0.08
al5[0, elem_idx["Cu"]] = 0.03
X_al5 = composition_to_features_np(al5)[0]
z_al5 = (X_al5 - tr_mean) / (tr_std + 1e-6)
print(f"\nAlnico5 z-scores:  min={z_al5.min():.2f}  max={z_al5.max():.2f}  |z|>10: {(np.abs(z_al5)>10).sum()}")

# Check the scaler dims from new bundle
sc_tc = bundle._sc_tc_g
xm, xs, ym, ys, log_t = sc_tc
print(f"\nBundle Tc scaler:")
print(f"  y_mean={ym.item():.2f}  y_std={ys.item():.2f}  log_t={log_t}")
xs_np = xs.cpu().numpy()
print(f"  x_std min={xs_np.min():.8f}  (scaler, not training data std)")
near_zero = [(i, labels[i], xs_np[i]) for i in range(len(xs_np)) if xs_np[i] < 0.01]
if near_zero:
    print(f"  Scaler x_std < 0.01:")
    for i, lbl, s in near_zero:
        print(f"    dim {i} ({lbl}): scaler_std={s:.8f}")

# Hand-trace Permalloy through the MLP
pm_t = torch.from_numpy(pm).to(device)
with torch.no_grad():
    feats = composition_to_features_torch(pm_t, torch.from_numpy(get_element_matrix()).to(device))
    norm = (feats - xm) / xs
    print(f"\nPermalloy normalized features (via scaler):")
    print(f"  min={norm.min().item():.2f}  max={norm.max().item():.2f}")
    out_norm = bundle.mlp_tc(norm)
    print(f"  raw mlp output (normalized): {out_norm.item():.6f}")
    tc_out = out_norm.item() * ys.item() + ym.item()
    print(f"  final Tc = {out_norm.item():.4f} * {ys.item():.2f} + {ym.item():.2f} = {tc_out:.2f}")
