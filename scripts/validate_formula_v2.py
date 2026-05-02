"""
A2 Step 2A: Validate revised Tc formula against NEMAD (no retraining).
Compares v1 (old) vs v2 (new) formula directly.
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from alloy_engine.data.elements import ELEMENTS

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


def load_nemad() -> pd.DataFrame:
    fm = pd.read_csv(NEMAD_PATH)
    mask = (fm[OTHER_ELEM] == 0).all(axis=1) & (fm[OUR_ELEMENTS] > 0).any(axis=1)
    df = fm[mask].copy()
    df = df[df['Mean_TC_K'] >= 50]
    df = df[df[OUR_ELEMENTS].max(axis=1) <= 0.95]
    return df.reset_index(drop=True)


def formula_v1(comp: np.ndarray) -> np.ndarray:
    """Original formula."""
    fe = comp[:, OUR_ELEMENTS.index("Fe")]
    ni = comp[:, OUR_ELEMENTS.index("Ni")]
    co = comp[:, OUR_ELEMENTS.index("Co")]
    cr = comp[:, OUR_ELEMENTS.index("Cr")]
    mn = comp[:, OUR_ELEMENTS.index("Mn")]
    nonmag_elem = [e for e in OUR_ELEMENTS if e not in ("Fe","Ni","Co","Cr","Mn")]
    nonmag_comp = sum(comp[:, OUR_ELEMENTS.index(e)] for e in nonmag_elem)

    mag_frac = fe + ni + co
    base_tc = np.where(
        mag_frac > 0.05,
        (fe * 1043 + ni * 627 + co * 1400) / np.maximum(mag_frac, 0.01),
        50.0,
    )
    cr_suppress = 5500 * np.power(cr, 1.2)
    mn_suppress = 4500 * np.power(mn, 1.2)
    nonmag      = 1 - mag_frac - cr - mn
    dilution    = base_tc * nonmag * 0.5
    permalloy   = np.where(
        (ni > 0.3) & (ni < 0.6) & (fe > 0.3),
        100 * np.exp(-((ni - 0.5) ** 2) / 0.02),
        0,
    )
    tc = base_tc * mag_frac - cr_suppress - mn_suppress - dilution + permalloy
    return tc


def formula_v2(comp: np.ndarray) -> np.ndarray:
    """Revised formula (this module imports the updated version)."""
    from alloy_engine.data.synthetic import physics_based_properties_batch
    # physics_based_properties_batch adds noise; re-implement deterministically
    fe = comp[:, OUR_ELEMENTS.index("Fe")]
    ni = comp[:, OUR_ELEMENTS.index("Ni")]
    co = comp[:, OUR_ELEMENTS.index("Co")]
    cr = comp[:, OUR_ELEMENTS.index("Cr")]
    mn = comp[:, OUR_ELEMENTS.index("Mn")]

    mag_frac = fe + ni + co
    base_tc = np.where(
        mag_frac > 0.05,
        (fe * 1043 + ni * 627 + co * 1400) / np.maximum(mag_frac, 0.01),
        50.0,
    )
    fe_co_synergy = 80.0 * 4.0 * (fe * co) / (mag_frac ** 2 + 1e-6)
    cr_suppress   = 1800 * np.power(cr, 1.2)
    mn_suppress   = 1200 * np.power(mn, 1.2)
    nonmag        = 1 - mag_frac - cr - mn
    dilution      = base_tc * nonmag * 0.20
    permalloy     = np.where(
        (ni > 0.3) & (ni < 0.6) & (fe > 0.3),
        100 * np.exp(-((ni - 0.5) ** 2) / 0.02),
        0,
    )
    tc = (base_tc + fe_co_synergy) * mag_frac - cr_suppress - mn_suppress - dilution + permalloy
    return tc


def residual_stats(label, true_K, pred_K):
    r = true_K - pred_K
    print(f"  {label}: mean={r.mean():+.1f}  median={np.median(r):+.1f}  "
          f"std={r.std():.1f}  MAE={np.abs(r).mean():.1f}  (n={len(r)})")
    return r


def bin_residuals(label, groups, true_K, pred_v1, pred_v2):
    r1 = true_K - pred_v1
    r2 = true_K - pred_v2
    print(f"\n  {label}")
    print(f"  {'Bin':<18}  {'n':>4}  {'v1 mean':>8}  {'v2 mean':>8}  {'delta':>8}")
    for name, mask in groups:
        if mask.sum() < 3:
            continue
        m1 = r1[mask].mean()
        m2 = r2[mask].mean()
        print(f"  {name:<18}  {mask.sum():>4}  {m1:>+8.1f}  {m2:>+8.1f}  {m2-m1:>+8.1f}")


def main():
    df = load_nemad()
    comp = df[OUR_ELEMENTS].values.astype(np.float32)
    true_K = df['Mean_TC_K'].values

    p1 = formula_v1(comp)
    p2 = formula_v2(comp)

    print("=== Overall residual stats (true - formula, K) ===")
    residual_stats("v1 (old)", true_K, p1)
    residual_stats("v2 (new)", true_K, p2)

    # Famous alloys
    print("\n=== Famous alloy spot check ===")
    print(f"  {'Alloy':<42}  {'True Tc':>8}  {'v1 pred':>8}  {'v2 pred':>8}  {'v1 err':>8}  {'v2 err':>8}")
    famous = {
        "Permalloy Ni80Fe20":           {'Ni':0.80,'Fe':0.20},
        "Sendust Fe85Si9Al6":           {'Fe':0.85,'Si':0.09,'Al':0.06},
        "Hiperco50 Fe50Co50":           {'Fe':0.50,'Co':0.50},
        "Hiperco27 Fe73Co27":           {'Fe':0.73,'Co':0.27},
        "Fe65Ni35 (Invar)":             {'Fe':0.65,'Ni':0.35},
        "Alnico5 Fe51Co24Ni14Al8Cu3":   {'Fe':0.51,'Co':0.24,'Ni':0.14,'Al':0.08,'Cu':0.03},
        "Fe60Co20Ni20":                 {'Fe':0.60,'Co':0.20,'Ni':0.20},
    }
    elem_idx = {e: i for i, e in enumerate(OUR_ELEMENTS)}
    for name, comp_dict in famous.items():
        vec = np.zeros((1, len(OUR_ELEMENTS)), dtype=np.float32)
        for e, f in comp_dict.items():
            vec[0, elem_idx[e]] = f
        # find NEMAD match
        diffs = np.abs(comp - vec).sum(axis=1)
        best  = diffs.argmin()
        nemad_tc = true_K[best] if diffs[best] < 0.05 else None
        v1c = formula_v1(vec)[0]
        v2c = formula_v2(vec)[0]
        nemad_str = f"{nemad_tc-273.15:+7.1f}" if nemad_tc else "     N/A"
        print(f"  {name:<42}  {nemad_str}C  "
              f"{v1c-273.15:>+7.1f}C  {v2c-273.15:>+7.1f}C  "
              f"{(v1c-nemad_tc if nemad_tc else 0):>+7.1f}  "
              f"{(v2c-nemad_tc if nemad_tc else 0):>+7.1f}")

    # Binned residuals
    fe = comp[:, OUR_ELEMENTS.index("Fe")]
    ni = comp[:, OUR_ELEMENTS.index("Ni")]
    co = comp[:, OUR_ELEMENTS.index("Co")]
    cr = comp[:, OUR_ELEMENTS.index("Cr")]
    mn = comp[:, OUR_ELEMENTS.index("Mn")]
    si = comp[:, OUR_ELEMENTS.index("Si")]
    al = comp[:, OUR_ELEMENTS.index("Al")]
    mag = fe + ni + co
    sial = si + al

    print("\n=== Binned residuals: v1 vs v2 ===")

    bin_residuals("mag_frac (Fe+Ni+Co)", [
        ("0.00-0.30", (mag < 0.30)),
        ("0.30-0.50", (mag >= 0.30) & (mag < 0.50)),
        ("0.50-0.70", (mag >= 0.50) & (mag < 0.70)),
        ("0.70-0.85", (mag >= 0.70) & (mag < 0.85)),
        ("0.85-1.00", (mag >= 0.85)),
    ], true_K, p1, p2)

    bin_residuals("Si+Al content", [
        ("0.00-0.05", (sial < 0.05)),
        ("0.05-0.10", (sial >= 0.05) & (sial < 0.10)),
        ("0.10-0.20", (sial >= 0.10) & (sial < 0.20)),
        ("0.20-0.30", (sial >= 0.20) & (sial < 0.30)),
        ("0.30-0.50", (sial >= 0.30)),
    ], true_K, p1, p2)

    bin_residuals("Cr content", [
        ("0.00-0.05", (cr < 0.05)),
        ("0.05-0.10", (cr >= 0.05) & (cr < 0.10)),
        ("0.10-0.20", (cr >= 0.10) & (cr < 0.20)),
        ("0.20-0.35", (cr >= 0.20) & (cr < 0.35)),
        ("0.35-0.55", (cr >= 0.35)),
    ], true_K, p1, p2)

    bin_residuals("Mn content", [
        ("0.00-0.05", (mn < 0.05)),
        ("0.05-0.15", (mn >= 0.05) & (mn < 0.15)),
        ("0.15-0.25", (mn >= 0.15) & (mn < 0.25)),
        ("0.25-0.50", (mn >= 0.25)),
    ], true_K, p1, p2)

    # MAE improvement per zone
    r1_all = true_K - p1
    r2_all = true_K - p2
    print(f"\n=== MAE change v1→v2 by waste-heat zone (K) ===")
    tc_C = true_K - 273.15
    for name, lo, hi in [("100-200C", 100, 200), ("300-400C", 300, 400), ("500-700C", 500, 700)]:
        m = (tc_C >= lo) & (tc_C < hi)
        mae1 = np.abs(r1_all[m]).mean()
        mae2 = np.abs(r2_all[m]).mean()
        print(f"  {name}: v1 MAE={mae1:.1f} K  v2 MAE={mae2:.1f} K  delta={mae2-mae1:+.1f} K  (n={m.sum()})")


if __name__ == "__main__":
    main()
