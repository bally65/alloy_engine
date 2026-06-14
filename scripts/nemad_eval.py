"""
Tasks 1 & 3: Evaluate synthetic-trained surrogate on real NEMAD data,
and spot-check famous alloys.
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
from sklearn.metrics import r2_score, mean_absolute_error

sys.path.insert(0, str(Path(__file__).parent.parent))

from alloy_engine.config import CHECKPOINT_DIR, DEFAULT_DEVICE
from alloy_engine.data.elements import ELEMENTS
from alloy_engine.models.surrogate import SurrogateBundle

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("nemad_eval")

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
NEMAD_PATH  = Path("external/NEMAD/Dataset/FM_with_curie.csv")
RESULTS_DIR = Path("results")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# ── Famous alloys within our element space（含稀土 MCE 基準）────────────────────
# composition given as atomic fractions summing to 1.0
FAMOUS_ALLOYS = {
    "Gadolinium (Gd, MCE 基準)": {"Gd": 1.0},
    "La-Fe-Si (La7Fe80Si13)":  {"La": 0.07, "Fe": 0.80, "Si": 0.13},
    "Permalloy (Ni80Fe20)":    {"Fe": 0.20, "Ni": 0.80},
    "Supermalloy (Ni79Mo5Fe16)": {"Fe": 0.16, "Ni": 0.79, "Mo": 0.05},
    "Mu-Metal (Ni77Fe14Cu5Mo4)": {"Fe": 0.14, "Ni": 0.77, "Cu": 0.05, "Mo": 0.04},
    "Sendust (Fe85Si9Al6)":    {"Fe": 0.85, "Si": 0.09, "Al": 0.06},
    "Hiperco50 (Fe50Co50)":    {"Fe": 0.50, "Co": 0.50},
    "Hiperco27 (Fe73Co27)":    {"Fe": 0.73, "Co": 0.27},
    "Fe65Ni35 (Invar region)": {"Fe": 0.65, "Ni": 0.35},
    "Alnico5 (Fe51Co24Ni14Al8Cu3)": {"Fe": 0.51, "Co": 0.24, "Ni": 0.14, "Al": 0.08, "Cu": 0.03},
    "Ni50Fe50":                {"Fe": 0.50, "Ni": 0.50},
    "Fe60Co20Ni20":            {"Fe": 0.60, "Co": 0.20, "Ni": 0.20},
}


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
    df = df[df['Mean_TC_K'] >= 50]
    df = df[df[OUR_ELEMENTS].max(axis=1) <= 0.95]
    df = df.copy()
    df['has_Mo'] = df['Mo'] > 0
    df['tc_C']   = df['Mean_TC_K'] - 273.15
    return df.reset_index(drop=True)


def predict_tc_C(bundle: SurrogateBundle, compositions: np.ndarray,
                 device: torch.device) -> np.ndarray:
    """compositions: (N, NUM_ELEMENTS) float32 atomic fractions → predicted Tc in degC."""
    comp_t = torch.from_numpy(compositions).to(device)
    with torch.no_grad():
        props = bundle.predict_properties(comp_t)
    # bundle outputs Tc in K (trained on synthetic K values)
    # convert to degC for comparison with NEMAD (Mean_TC_K - 273.15)
    return props["Tc"].cpu().numpy() - 273.15


def report_subset(label: str, mask: np.ndarray, true_C, pred_C) -> dict:
    n = mask.sum()
    if n < 3:
        logger.info("  %-30s n=%d (too few)", label, n)
        return {"label": label, "n": n, "r2": None, "mae": None}
    r2  = r2_score(true_C[mask], pred_C[mask])
    mae = mean_absolute_error(true_C[mask], pred_C[mask])
    logger.info("  %-30s R²=%7.4f  MAE=%6.1f degC  (n=%d)", label, r2, mae, n)
    return {"label": label, "n": n, "r2": r2, "mae": mae}


def task1_eval(bundle: SurrogateBundle, df: pd.DataFrame, device: torch.device) -> tuple:
    compositions = df[OUR_ELEMENTS].values.astype(np.float32)
    pred_C = predict_tc_C(bundle, compositions, device)
    true_C = df['tc_C'].values

    logger.info("=" * 65)
    logger.info("TASK 1 — Synthetic surrogate evaluated on NEMAD 618 real samples")
    logger.info("=" * 65)

    results = []
    results.append(report_subset("(a) Overall",                  np.ones(len(df), dtype=bool), true_C, pred_C))
    results.append(report_subset("(b) No Mo",                    ~df['has_Mo'].values,          true_C, pred_C))
    results.append(report_subset("(c) Mo > 0",                   df['has_Mo'].values,            true_C, pred_C))
    results.append(report_subset("(e1) 100-200 degC target",     (true_C >= 100) & (true_C < 200), true_C, pred_C))
    results.append(report_subset("(e2) 300-400 degC target",     (true_C >= 300) & (true_C < 400), true_C, pred_C))
    results.append(report_subset("(e3) 500-700 degC target",     (true_C >= 500) & (true_C < 700), true_C, pred_C))
    logger.info("=" * 65)

    return true_C, pred_C, results


def plot_sim_to_real(true_C, pred_C, df: pd.DataFrame, save_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 8))

    zone_defs = [
        ("100-200 degC",  (true_C >= 100)  & (true_C < 200),  'tab:green'),
        ("300-400 degC",  (true_C >= 300)  & (true_C < 400),  'tab:orange'),
        ("500-700 degC",  (true_C >= 500)  & (true_C < 700),  'tab:red'),
        ("Other",
         ~((true_C >= 100) & (true_C < 200)) &
         ~((true_C >= 300) & (true_C < 400)) &
         ~((true_C >= 500) & (true_C < 700)),
         'steelblue'),
    ]
    for label, mask, color in zone_defs:
        ax.scatter(true_C[mask], pred_C[mask], c=color, s=30, alpha=0.65, label=label)

    lim = [min(true_C.min(), pred_C.min()) - 50,
           max(true_C.max(), pred_C.max()) + 50]
    ax.plot(lim, lim, 'k--', lw=1.2, alpha=0.5, label='y = x')
    ax.set_xlim(lim); ax.set_ylim(lim)

    r2_all  = r2_score(true_C, pred_C)
    mae_all = mean_absolute_error(true_C, pred_C)
    ax.set_xlabel("Actual Tc — NEMAD experimental (degC)", fontsize=12)
    ax.set_ylabel("Predicted Tc — synthetic-trained model (degC)", fontsize=12)
    ax.set_title(
        f"Synthetic-trained model evaluated on real NEMAD data\n"
        f"R²={r2_all:.4f}  MAE={mae_all:.1f} degC  (n={len(true_C)})",
        fontsize=12
    )
    ax.legend(fontsize=10); ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close()
    logger.info("Saved %s", save_path)


def task3_famous_alloys(bundle: SurrogateBundle, df: pd.DataFrame,
                         device: torch.device) -> pd.DataFrame:
    logger.info("=" * 65)
    logger.info("TASK 3 — Famous alloy sanity check")
    logger.info("=" * 65)

    rows = []
    for name, comp in FAMOUS_ALLOYS.items():
        vec = np.zeros((1, len(OUR_ELEMENTS)), dtype=np.float32)
        for elem, frac in comp.items():
            if elem in OUR_ELEMENTS:
                vec[0, OUR_ELEMENTS.index(elem)] = frac

        pred_tc_C = predict_tc_C(bundle, vec, device)[0]

        # find closest match in NEMAD
        nemad_comps = df[OUR_ELEMENTS].values
        diffs = np.abs(nemad_comps - vec).sum(axis=1)
        best_idx = diffs.argmin()
        best_diff = diffs[best_idx]
        if best_diff < 0.10:
            nemad_tc   = df.iloc[best_idx]['tc_C']
            nemad_match = f"{nemad_tc:.1f} (dist={best_diff:.3f})"
            error_C = pred_tc_C - nemad_tc
        else:
            nemad_match = "no close match"
            error_C = None

        logger.info("  %-40s  pred=%6.1f degC  NEMAD=%s  err=%s",
                    name, pred_tc_C, nemad_match,
                    f"{error_C:+.1f} degC" if error_C is not None else "—")
        rows.append({
            "alloy": name,
            "pred_Tc_C": round(float(pred_tc_C), 1),
            "nemad_Tc_C": round(float(df.iloc[best_idx]['tc_C']), 1) if best_diff < 0.10 else None,
            "error_C": round(float(error_C), 1) if error_C is not None else None,
            "nemad_dist": round(float(best_diff), 4),
        })
    logger.info("=" * 65)
    return pd.DataFrame(rows)


def inspect_bundle(bundle: SurrogateBundle) -> None:
    for prop, sc in [("Tc", bundle.sc_tc), ("Hc", bundle.sc_hc),
                     ("Br", bundle.sc_br), ("strength", bundle.sc_strength)]:
        x_mean, x_std, y_mean, y_std, log_t = sc
        logger.info("  %s — y_mean=%.2f  y_std=%.2f  log_transform=%s",
                    prop, y_mean, y_std, log_t)


def main() -> None:
    device = DEFAULT_DEVICE
    logger.info("Device: %s", device)

    # load synthetic surrogate
    ckpt_path = CHECKPOINT_DIR / "bundle.pt"
    logger.info("Loading surrogate from %s", ckpt_path)
    bundle = SurrogateBundle.load(ckpt_path, device=device)
    inspect_bundle(bundle)

    # load NEMAD
    df = load_and_clean()
    logger.info("NEMAD cleaned: %d samples", len(df))

    # Task 1
    true_C, pred_C, _ = task1_eval(bundle, df, device)
    plot_sim_to_real(true_C, pred_C, df,
                     RESULTS_DIR / "sim_to_real_gap.png")

    # Task 3
    famous_df = task3_famous_alloys(bundle, df, device)
    print()
    print(famous_df.to_string(index=False))


if __name__ == "__main__":
    main()
