"""A3-4: MC Dropout uncertainty validation on NEMAD 618 samples."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import torch
from scipy import stats

sys.path.insert(0, str(Path(__file__).parent.parent))

from alloy_engine.config import CHECKPOINT_DIR, DEFAULT_DEVICE
from alloy_engine.models.surrogate import SurrogateBundle

OUR_ELEMENTS = ['Fe', 'Ni', 'Co', 'Cr', 'Mn', 'Cu', 'Mo', 'Si', 'Al', 'V']
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


def load_nemad():
    fm = pd.read_csv(NEMAD_PATH)
    mask = (fm[OTHER_ELEM] == 0).all(axis=1) & (fm[OUR_ELEMENTS] > 0).any(axis=1)
    df = fm[mask].copy()
    df = df[df['Mean_TC_K'] >= 50]
    df = df[df[OUR_ELEMENTS].max(axis=1) <= 0.95]
    return df.reset_index(drop=True)


def comp_tensor(comp_dict, device):
    vec = np.zeros((1, len(OUR_ELEMENTS)), dtype=np.float32)
    for e, f in comp_dict.items():
        vec[0, OUR_ELEMENTS.index(e)] = f
    return torch.from_numpy(vec).to(device)


def main():
    bundle = SurrogateBundle.load(CHECKPOINT_DIR / 'bundle.pt', device=DEFAULT_DEVICE)
    df = load_nemad()
    comp_np = df[OUR_ELEMENTS].values.astype(np.float32)
    true_K = df['Mean_TC_K'].values
    true_C = true_K - 273.15

    # ── (a) Famous alloys ─────────────────────────────────────────────────────
    print("=== (a) Famous alloy Tc_mean +/- Tc_std ===")
    print(f"  {'Alloy':<42}  {'n_elem':>6}  {'mean(C)':>8}  {'std(C)':>7}  {'NEMAD(C)':>9}  {'err':>7}")

    famous = [
        ("Permalloy Ni80Fe20",          {'Ni': 0.80, 'Fe': 0.20},          434.2),
        ("Hiperco50 Fe50Co50",           {'Fe': 0.50, 'Co': 0.50},          1030.6),
        ("Sendust Fe85Si9Al6",           {'Fe': 0.85, 'Si': 0.09, 'Al': 0.06}, 696.9),
        ("Alnico5 Fe51Co24Ni14Al8Cu3",  {'Fe': 0.515, 'Co': 0.242, 'Ni': 0.141,
                                          'Al': 0.081, 'Cu': 0.030},         870.0),
        ("Invar Fe65Ni35",              {'Fe': 0.65, 'Ni': 0.35},           256.9),
    ]
    for name, cd, nemad_C in famous:
        t = comp_tensor(cd, DEFAULT_DEVICE)
        res = bundle.predict_properties_with_uncertainty(t, n_samples=30)
        mn_C = res['Tc_mean'].item() - 273.15
        sd_C = res['Tc_std'].item()
        n_elem = len(cd)
        err = mn_C - nemad_C
        print(f"  {name:<42}  {n_elem:>6}  {mn_C:>+8.1f}  {sd_C:>7.1f}  {nemad_C:>+9.1f}  {err:>+7.1f}")

    # ── NEMAD 618 batch MC ────────────────────────────────────────────────────
    print("\nRunning MC Dropout on NEMAD 618 (n_samples=30)...")
    comp_t = torch.from_numpy(comp_np).to(DEFAULT_DEVICE)
    res = bundle.predict_properties_with_uncertainty(comp_t, n_samples=30)
    pred_mean_C = res['Tc_mean'].cpu().numpy() - 273.15
    pred_std_C  = res['Tc_std'].cpu().numpy()

    abs_err = np.abs(true_C - pred_mean_C)
    n_elem_arr = (comp_np > 1e-6).sum(axis=1)

    # ── (b) std vs n_elem ─────────────────────────────────────────────────────
    print("\n=== (b) Tc_std vs element count ===")
    r_b, p_b = stats.pearsonr(n_elem_arr, pred_std_C)
    print(f"  Pearson r(n_elem, Tc_std) = {r_b:+.4f}  (p={p_b:.3f})")
    print(f"  {'n_elem':>6}  {'n':>4}  {'mean_std(C)':>12}")
    for ne in sorted(set(n_elem_arr)):
        mask = n_elem_arr == ne
        label = f"{ne}+" if ne >= 6 else str(ne)
        if mask.sum() > 0:
            print(f"  {label:>6}  {mask.sum():>4}  {pred_std_C[mask].mean():>12.2f}")

    # ── (c) std vs absolute error (calibration) ───────────────────────────────
    print("\n=== (c) Calibration: Tc_std vs absolute error ===")
    r_c, p_c = stats.pearsonr(pred_std_C, abs_err)
    print(f"  Pearson r(Tc_std, |error|) = {r_c:+.4f}  (p={p_c:.3f})")

    print(f"\n  Quartile analysis (by Tc_std):")
    print(f"  {'Quartile':>10}  {'std range(C)':>16}  {'mean |err|(C)':>14}  {'mean std(C)':>12}  {'n':>4}")
    order = np.argsort(pred_std_C)
    q_size = len(order) // 4
    for qi, label in enumerate(['Q1 (low std)', 'Q2', 'Q3', 'Q4 (high std)']):
        if qi < 3:
            idx = order[qi * q_size:(qi + 1) * q_size]
        else:
            idx = order[qi * q_size:]
        std_lo = pred_std_C[idx].min()
        std_hi = pred_std_C[idx].max()
        mae_q  = abs_err[idx].mean()
        mstd_q = pred_std_C[idx].mean()
        print(f"  {label:>14}  {std_lo:>6.1f}-{std_hi:<6.1f}   {mae_q:>14.1f}  {mstd_q:>12.1f}  {len(idx):>4}")

    # ── (d) std by waste-heat zone ────────────────────────────────────────────
    print("\n=== (d) Tc_std by waste-heat zone ===")
    print(f"  {'Zone':>12}  {'n':>4}  {'mean_std(C)':>12}  {'mean_err(C)':>12}")
    for name, lo, hi in [("100-200C", 100, 200), ("300-400C", 300, 400), ("500-700C", 500, 700)]:
        mask = (true_C >= lo) & (true_C < hi)
        if mask.sum() > 0:
            print(f"  {name:>12}  {mask.sum():>4}  {pred_std_C[mask].mean():>12.2f}  {abs_err[mask].mean():>12.1f}")

    # Overall summary
    print(f"\n=== Overall ===")
    print(f"  mean Tc_std (all 618): {pred_std_C.mean():.2f} C")
    print(f"  min / max Tc_std:      {pred_std_C.min():.2f} / {pred_std_C.max():.2f} C")
    print(f"  mean |error|:          {abs_err.mean():.1f} C")


if __name__ == "__main__":
    main()
