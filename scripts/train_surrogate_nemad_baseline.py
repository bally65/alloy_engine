"""
Stage 1: Pure NEMAD baseline — train Tc model on real cleaned entries.
No synthetic data. Establishes real-data R² baseline for Stage 2 decision.

稀土擴張後：OUR_ELEMENTS 改由 elements.ELEMENTS 衍生（含 Gd/La），清理
不再排除稀土條目，故樣本數會大於舊版的 618（含 Gd-Fe / La-Fe-Si 等）。

Outputs:
  alloy_engine/models/checkpoints/surrogate_nemad_baseline.pt
  results/baseline_pred_vs_actual.png
  results/baseline_residual_by_element.png
"""
import logging
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm_lib
import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from sklearn.metrics import r2_score, mean_absolute_error
from sklearn.model_selection import train_test_split

sys.path.insert(0, str(Path(__file__).parent.parent))

from alloy_engine.config import CHECKPOINT_DIR, DEFAULT_DEVICE
from alloy_engine.data.elements import ELEMENTS
from alloy_engine.features.engineering import composition_to_features_np
from alloy_engine.models.surrogate import PropertyMLP

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("nemad_baseline")

# font
for _fn in ['Microsoft JhengHei', 'Microsoft YaHei', 'DejaVu Sans']:
    if any(_fn in f.name for f in fm_lib.fontManager.ttflist):
        plt.rcParams['font.sans-serif'] = [_fn]
        break
plt.rcParams['axes.unicode_minus'] = False

# 與引擎元素空間同步（單一真實來源），含稀土擴張後的 Gd / La
OUR_ELEMENTS = list(ELEMENTS)
ALL_ELEM_COLS = [
    'H','He','Li','Be','B','C','N','O','F','Ne','Na','Mg','Al','Si','P','S',
    'Cl','Ar','K','Ca','Sc','Ti','V','Cr','Mn','Fe','Co','Ni','Cu','Zn','Ga',
    'Ge','As','Se','Br','Kr','Rb','Sr','Y','Zr','Nb','Mo','Tc','Ru','Rh','Pd',
    'Ag','Cd','In','Sn','Sb','Te','I','Xe','Cs','Ba','La','Ce','Pr','Nd','Pm',
    'Sm','Eu','Gd','Tb','Dy','Ho','Er','Tm','Yb','Lu','Hf','Ta','W','Re','Os',
    'Ir','Pt','Au','Hg','Tl','Pb','Bi','Po','At','Rn','Fr','Ra','Ac','Th','Pa',
    'U','Np','Pu','Am','Cm','Bk','Cf','Es','Fm','Md','No','Lr',
]
OTHER_ELEM = [e for e in ALL_ELEM_COLS if e not in OUR_ELEMENTS]
NEMAD_PATH = Path("external/NEMAD/Dataset/FM_with_curie.csv")
RESULTS_DIR = Path("results")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def load_and_clean() -> pd.DataFrame:
    if not NEMAD_PATH.exists():
        raise FileNotFoundError(
            f"找不到 NEMAD 資料：{NEMAD_PATH}（git-ignored）。請先把資料放到 "
            f"external/NEMAD/Dataset/ 再執行。"
        )
    fm = pd.read_csv(NEMAD_PATH)
    # OTHER_ELEM 已自動排除 Gd/La（OUR_ELEMENTS 含稀土）→ 保留稀土條目
    mask = (fm[OTHER_ELEM] == 0).all(axis=1) & (fm[OUR_ELEMENTS] > 0).any(axis=1)
    df = fm[mask].copy()
    logger.info("After element filter: %d rows", len(df))
    df = df[df['Mean_TC_K'] >= 50]
    df = df[df[OUR_ELEMENTS].max(axis=1) <= 0.95]
    logger.info("After Tc<50K and pure-element removal: %d rows", len(df))
    df = df.copy()
    df['has_Mo'] = df['Mo'] > 0
    df['has_V']  = df['V']  > 0
    df['is_rare'] = df['has_Mo'] | df['has_V']
    return df


def train(X: np.ndarray, y: np.ndarray, device: torch.device,
          epochs: int = 500, batch_size: int = 32, hidden: int = 128,
          patience: int = 50) -> tuple:
    # F-SCI-05：先切分，再「僅用訓練集」擬合 scaler（避免 val/test 統計洩漏進正規化）。
    X_tr_raw, X_te_raw, y_tr_raw, y_te_raw, idx_tr, idx_te = train_test_split(
        X, y, np.arange(len(X)), test_size=0.10, random_state=42
    )
    X_tr_raw, X_va_raw, y_tr_raw, y_va_raw = train_test_split(
        X_tr_raw, y_tr_raw, test_size=1/9, random_state=42
    )

    x_mean = X_tr_raw.mean(0).astype(np.float32)
    x_std  = (X_tr_raw.std(0) + 1e-6).astype(np.float32)
    y_mean = float(y_tr_raw.mean())
    y_std  = float(y_tr_raw.std() + 1e-6)

    nx = lambda A: ((A - x_mean) / x_std).astype(np.float32)
    ny = lambda b: ((b - y_mean) / y_std).astype(np.float32)
    X_tr, X_va, X_te = nx(X_tr_raw), nx(X_va_raw), nx(X_te_raw)
    y_tr, y_va, y_te = ny(y_tr_raw), ny(y_va_raw), ny(y_te_raw)
    logger.info("Split: train=%d  val=%d  test=%d", len(X_tr), len(X_va), len(X_te))

    to_t = lambda a: torch.from_numpy(a).to(device)
    Xtr, ytr = to_t(X_tr), to_t(y_tr)
    Xva, yva = to_t(X_va), to_t(y_va)
    Xte       = to_t(X_te)

    model = PropertyMLP(X.shape[1], hidden=hidden).to(device)
    opt   = torch.optim.AdamW(model.parameters(), lr=1.5e-3, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)

    best_val_loss, best_state, wait = np.inf, None, 0
    for ep in range(epochs):
        model.train()
        perm = torch.randperm(len(Xtr), device=device)
        for i in range(0, len(Xtr), batch_size):
            idx  = perm[i: i + batch_size]
            loss = F.smooth_l1_loss(model(Xtr[idx]), ytr[idx])
            opt.zero_grad(); loss.backward(); opt.step()
        sched.step()

        model.eval()
        with torch.no_grad():
            val_loss = F.smooth_l1_loss(model(Xva), yva).item()

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            wait = 0
        else:
            wait += 1
            if wait >= patience:
                logger.info("Early stop at epoch %d", ep + 1)
                break

        if (ep + 1) % 100 == 0:
            logger.info("  epoch %3d | val_loss=%.4f (best=%.4f)", ep + 1, val_loss, best_val_loss)

    model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        pred_norm = model(Xte).cpu().numpy().ravel()
    pred_K = pred_norm * y_std + y_mean
    true_K = y_te   * y_std + y_mean

    scaler = (x_mean, x_std, y_mean, y_std, False)
    return model, scaler, pred_K, true_K, idx_te


def plot_pred_vs_actual(pred_C, true_C, has_mo_test, save_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 7))
    no_mo = ~has_mo_test
    ax.scatter(true_C[no_mo],    pred_C[no_mo],    c='steelblue', s=35, alpha=0.75, label='No Mo')
    ax.scatter(true_C[has_mo_test], pred_C[has_mo_test],
               c='orange', s=60, marker='D', alpha=0.9, label='Contains Mo')
    lim = [min(true_C.min(), pred_C.min()) - 30,
           max(true_C.max(), pred_C.max()) + 30]
    ax.plot(lim, lim, 'k--', lw=1, alpha=0.5)
    r2  = r2_score(true_C, pred_C)
    mae = mean_absolute_error(true_C, pred_C)
    ax.set_xlim(lim); ax.set_ylim(lim)
    ax.set_xlabel('Actual Tc (degC)')
    ax.set_ylabel('Predicted Tc (degC)')
    ax.set_title(f'NEMAD Baseline — Test Set\nR²={r2:.4f}  MAE={mae:.1f} degC')
    ax.legend(); ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close()
    logger.info("Saved %s", save_path)


def plot_residual_by_element(pred_C, true_C, df_test: pd.DataFrame, save_path: Path) -> None:
    residual = pred_C - true_C
    elements = ['Mo', 'V', 'Cu', 'Si']
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    for ax, elem in zip(axes.ravel(), elements):
        x = df_test[elem].values * 100  # convert to at%
        ax.scatter(x, residual, s=25, alpha=0.6, c='steelblue')
        ax.axhline(0, color='k', lw=1, ls='--')
        ax.set_xlabel(f'{elem} (at%)')
        ax.set_ylabel('Residual (pred - actual) degC')
        ax.set_title(f'Residual vs {elem} content')
        ax.grid(alpha=0.3)
    plt.suptitle('NEMAD Baseline — Residuals by Element', fontsize=13)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close()
    logger.info("Saved %s", save_path)


def report_subset_r2(label: str, mask: np.ndarray, true_C, pred_C) -> None:
    n = mask.sum()
    if n < 3:
        logger.info("  %s: n=%d (too few)", label, n)
        return
    r2  = r2_score(true_C[mask], pred_C[mask])
    mae = mean_absolute_error(true_C[mask], pred_C[mask])
    logger.info("  %s: R²=%.4f  MAE=%.1f degC  (n=%d)", label, r2, mae, n)


def main() -> None:
    device = DEFAULT_DEVICE
    logger.info("Device: %s", device)

    df = load_and_clean()
    logger.info("Total after cleaning: %d  (Mo: %d, V: %d, Mo|V: %d)",
                len(df), df.has_Mo.sum(), df.has_V.sum(), df.is_rare.sum())

    # Oliynyk 統計特徵 (NUM_PROPS×4=36 維，與元素數無關)
    compositions = df[OUR_ELEMENTS].values.astype(np.float32)
    X = composition_to_features_np(compositions, device=None)
    y = df['Mean_TC_K'].values.astype(np.float32)

    logger.info("Feature shape: %s", X.shape)
    logger.info("Tc stats (K): min=%.1f  max=%.1f  mean=%.1f  std=%.1f",
                y.min(), y.max(), y.mean(), y.std())
    logger.info("Training (epochs=500, patience=50) ...")

    model, scaler, pred_K, true_K, idx_te = train(X, y, device)

    # convert to degC for all analysis
    pred_C = pred_K - 273.15
    true_C = true_K - 273.15

    df_test = df.iloc[idx_te].reset_index(drop=True)
    has_mo_test = df_test['has_Mo'].values
    has_v_test  = df_test['has_V'].values

    r2_all  = r2_score(true_C, pred_C)
    mae_all = mean_absolute_error(true_C, pred_C)

    logger.info("=" * 60)
    logger.info("(a) Overall test R²     : %.4f  MAE=%.1f degC", r2_all, mae_all)
    report_subset_r2("(b) No-Mo subset  ", ~has_mo_test, true_C, pred_C)
    report_subset_r2("(c) Mo subset     ", has_mo_test,  true_C, pred_C)
    report_subset_r2("(d) V subset      ", has_v_test,   true_C, pred_C)

    logger.info("  --- Tc range subsets ---")
    report_subset_r2("(e1) 100-200 degC", ((true_C >= 100) & (true_C < 200)), true_C, pred_C)
    report_subset_r2("(e2) 300-400 degC", ((true_C >= 300) & (true_C < 400)), true_C, pred_C)
    report_subset_r2("(e3) 500-700 degC", ((true_C >= 500) & (true_C < 700)), true_C, pred_C)
    logger.info("=" * 60)

    plot_pred_vs_actual(pred_C, true_C, has_mo_test,
                        RESULTS_DIR / "baseline_pred_vs_actual.png")
    plot_residual_by_element(pred_C, true_C, df_test,
                             RESULTS_DIR / "baseline_residual_by_element.png")

    x_mean, x_std, y_mean, y_std, _ = scaler
    out_path = CHECKPOINT_DIR / "surrogate_nemad_baseline.pt"
    torch.save({
        "model_state": model.state_dict(),
        "scaler": scaler,
        "in_dim": X.shape[1],
        "hidden": 128,
        "elements": OUR_ELEMENTS,
        "target": "Tc_K",
        "n_train": len(X) - len(idx_te),
        "test_r2_degC": float(r2_all),
        "test_mae_degC": float(mae_all),
    }, out_path)
    logger.info("Checkpoint saved: %s", out_path)


if __name__ == "__main__":
    main()
