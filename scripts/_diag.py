"""Four diagnostics for surrogate inference bug."""
import sys
from pathlib import Path
import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).parent.parent))

from alloy_engine.config import CHECKPOINT_DIR, DEFAULT_DEVICE
from alloy_engine.data.synthetic import generate_training_data
from alloy_engine.features.engineering import composition_to_features_np, composition_to_features_torch
from alloy_engine.models.surrogate import SurrogateBundle
from alloy_engine.data.elements import ELEMENTS, get_element_matrix

device = DEFAULT_DEVICE
print(f"Device: {device}")

bundle = SurrogateBundle.load(CHECKPOINT_DIR / "bundle.pt", device=device)

# ── Diag 1: Synthetic holdout ──────────────────────────────────────────────────
print("\n=== DIAG 1: Synthetic holdout ===")
from sklearn.metrics import r2_score
comp_np, tc_actual, hc_actual, br_actual, sy_actual = generate_training_data(n_samples=100, seed=999)
comp_np = comp_np.astype(np.float32)
tc_actual = tc_actual.astype(np.float32)
print(f"Synthetic Tc  min={tc_actual.min():.1f}  max={tc_actual.max():.1f}  mean={tc_actual.mean():.1f}  (unit?)")

comp_t = torch.from_numpy(comp_np).to(device)
with torch.no_grad():
    props = bundle.predict_properties(comp_t)
tc_pred = props["Tc"].cpu().numpy()
print(f"Predicted Tc  min={tc_pred.min():.1f}  max={tc_pred.max():.1f}  mean={tc_pred.mean():.1f}")

r2 = r2_score(tc_actual, tc_pred)
print(f"R² = {r2:.6f}")
print("Sample (actual, predicted):")
for i in range(5):
    print(f"  [{i}] actual={tc_actual[i]:.2f}  pred={tc_pred[i]:.2f}")

# ── Diag 2: Manual trace for simplified Alnico5 ───────────────────────────────
print("\n=== DIAG 2: Manual trace — simplified Alnico5 ===")
elem_idx = {e: i for i, e in enumerate(ELEMENTS)}
comp = np.zeros((1, 10), dtype=np.float32)
comp[0, elem_idx['Fe']] = 0.54
comp[0, elem_idx['Ni']] = 0.15
comp[0, elem_idx['Co']] = 0.25
comp[0, elem_idx['Al']] = 0.06
print(f"Sum check: {comp.sum():.4f}")
print(f"1) raw composition: {comp[0]}")

em = get_element_matrix()
em_t = torch.from_numpy(em).to(device)
comp_t = torch.from_numpy(comp).to(device)
feats_t = composition_to_features_torch(comp_t, em_t)
feats = feats_t.cpu().numpy()[0]
print(f"2) features shape: {feats.shape}")
print(f"   features min={feats.min():.4f}  max={feats.max():.4f}")
print(f"   features[:8] = {feats[:8]}")

# get x_mean/x_std from Tc scaler
sc_tc = bundle.sc_tc
x_mean, x_std, y_mean, y_std, log_t = sc_tc
print(f"\n3) Tc scaler:")
print(f"   x_mean shape={x_mean.shape}  x_mean[:5]={x_mean[:5]}")
print(f"   x_std  shape={x_std.shape}   x_std[:5]={x_std[:5]}")
print(f"   y_mean={y_mean:.4f}  y_std={y_std:.4f}  log_t={log_t}")

xm_np = x_mean if isinstance(x_mean, np.ndarray) else x_mean.cpu().numpy()
xs_np = x_std  if isinstance(x_std,  np.ndarray) else x_std.cpu().numpy()
feats_norm = (feats - xm_np) / xs_np
print(f"3) normalized features min={feats_norm.min():.4f}  max={feats_norm.max():.4f}")
print(f"   normalized[:8] = {feats_norm[:8]}")

# Use GPU scaler for normalization like predict_properties does
sc_g = bundle._sc_tc_g
xm_g, xs_g, ym_g, ys_g, log_t_g = sc_g
with torch.no_grad():
    feats_full = composition_to_features_torch(comp_t, em_t)
    raw_out = bundle.mlp_tc((feats_full - xm_g) / xs_g)
print(f"4) raw model output (no scaler): {raw_out.cpu().numpy()}")

# full prediction via predict_properties
with torch.no_grad():
    props2 = bundle.predict_properties(comp_t)
tc_out = props2["Tc"].cpu().numpy()
print(f"5) Final Tc output: {tc_out}")
print(f"6) log_t flag: {log_t}")

# ── Diag 3: Show predict_properties source ────────────────────────────────────
print("\n=== DIAG 3: Inspect GpuScaler contents ===")
# _sc_tc_g is the GpuScaler (namedtuple or tuple after __post_init__)
sc_g = bundle._sc_tc_g
print(f"_sc_tc_g type: {type(sc_g)}")
print(f"_sc_tc_g contents: {sc_g}")

# ── Diag 4: Permalloy feature distribution shift ──────────────────────────────
print("\n=== DIAG 4: Permalloy vs training distribution ===")
# Generate 8000 synthetic compositions to get feature stats
comp_big, *_ = generate_training_data(n_samples=8000, seed=42)
comp_big = comp_big.astype(np.float32)
X_big = composition_to_features_np(comp_big, device=None)
feat_mean = X_big.mean(0)
feat_std  = X_big.std(0) + 1e-9

# Permalloy Ni80Fe20
pm = np.zeros((1, 10), dtype=np.float32)
pm[0, elem_idx['Ni']] = 0.80
pm[0, elem_idx['Fe']] = 0.20
X_pm = composition_to_features_np(pm, device=None)[0]
z_scores = (X_pm - feat_mean) / feat_std
print(f"Permalloy feature z-scores: min={z_scores.min():.2f}  max={z_scores.max():.2f}")
print(f"Dims outside ±3σ: {(np.abs(z_scores) > 3).sum()} / 40")
print(f"Dims outside ±10σ: {(np.abs(z_scores) > 10).sum()} / 40")
worst_dims = np.argsort(np.abs(z_scores))[::-1][:5]
print("Top 5 most extreme dims (idx, z-score, feat_val, train_mean, train_std):")
for d in worst_dims:
    print(f"  dim {d:2d}: z={z_scores[d]:+8.2f}  val={X_pm[d]:.4f}  mean={feat_mean[d]:.4f}  std={feat_std[d]:.4f}")
