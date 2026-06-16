"""
A2 Step 1: Analyze formula bias on NEMAD 618 samples.
Fits linear regression on residuals (NEMAD_Tc - formula_Tc) to find
which compositional terms drive systematic error.
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score

sys.path.insert(0, str(Path(__file__).parent.parent))

from alloy_engine.data.synthetic import physics_based_properties_batch
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


def formula_tc(df: pd.DataFrame) -> np.ndarray:
    """Apply existing physics formula to a NEMAD dataframe."""
    comp = df[OUR_ELEMENTS].values.astype(np.float32)
    # physics_based_properties_batch expects composition in ELEMENTS order
    # OUR_ELEMENTS == ELEMENTS for this project
    tc, _, _, _ = physics_based_properties_batch(comp)
    return tc  # in K


def main():
    df = load_nemad()
    n = len(df)
    print(f"NEMAD samples: {n}")

    # Invar window: Fe 40-75%, Ni 25-45%, Co+Cr+Mn+others < 10%
    fe = df['Fe'].values
    ni = df['Ni'].values
    co = df['Co'].values
    cr = df['Cr'].values
    mn = df['Mn'].values
    cu = df['Cu'].values
    mo = df['Mo'].values
    si = df['Si'].values
    al = df['Al'].values
    v  = df['V'].values

    invar_mask = (fe > 0.40) & (fe < 0.75) & (ni > 0.20) & (ni < 0.45) & \
                 (co + cr + mn + cu + mo + si + al + v < 0.10)
    print(f"Invar window samples (excluded from regression): {invar_mask.sum()}")

    # True Tc in K
    true_K = df['Mean_TC_K'].values.astype(np.float32)

    # Formula prediction
    pred_K = formula_tc(df)

    # Residual: positive = formula under-predicts, negative = over-predicts
    residual = true_K - pred_K

    print(f"\n=== Overall residual stats (all {n} samples) ===")
    print(f"  mean  = {residual.mean():+.1f} K   (formula {'over' if residual.mean()<0 else 'under'}-predicts)")
    print(f"  std   = {residual.std():.1f} K")
    print(f"  median= {np.median(residual):+.1f} K")
    print(f"  min   = {residual.min():+.1f} K")
    print(f"  max   = {residual.max():+.1f} K")

    # Exclude Invar for regression
    mask_reg = ~invar_mask
    print(f"\nRegression set (non-Invar): {mask_reg.sum()} samples")

    fe_r  = fe[mask_reg]
    ni_r  = ni[mask_reg]
    co_r  = co[mask_reg]
    cr_r  = cr[mask_reg]
    mn_r  = mn[mask_reg]
    cu_r  = cu[mask_reg]
    mo_r  = mo[mask_reg]
    si_r  = si[mask_reg]
    al_r  = al[mask_reg]
    v_r   = v[mask_reg]
    res_r = residual[mask_reg]

    mag_total = fe_r + ni_r + co_r
    safe_mag  = np.where(mag_total > 0.01, mag_total, 0.01)

    # Interaction features
    fe_co_interaction = (fe_r * co_r) / (safe_mag ** 2)
    fe_ni_interaction = (fe_r * ni_r) / (safe_mag ** 2)
    ni_co_interaction = (ni_r * co_r) / (safe_mag ** 2)

    feature_names = [
        'Si', 'Al', 'Si+Al', 'Cr', 'Mn', 'Cu', 'Mo', 'V',
        'mag_frac', 'Fe/mag', 'Ni/mag', 'Co/mag',
        'Fe*Co/mag²', 'Fe*Ni/mag²', 'Ni*Co/mag²',
        'Si²', 'Al²', '(Si+Al)²',
    ]
    X = np.column_stack([
        si_r, al_r, si_r + al_r, cr_r, mn_r, cu_r, mo_r, v_r,
        mag_total, fe_r / safe_mag, ni_r / safe_mag, co_r / safe_mag,
        fe_co_interaction, fe_ni_interaction, ni_co_interaction,
        si_r**2, al_r**2, (si_r + al_r)**2,
    ])

    # Fit full regression（係數以全資料擬合，供生產修正使用）
    reg = LinearRegression().fit(X, res_r)
    pred_res = reg.predict(X)
    r2 = r2_score(res_r, pred_res)

    # F-SCI-03：另以 held-out fold 回報 out-of-sample R²，避免 in-sample 循環校驗高估泛化度。
    from sklearn.model_selection import train_test_split as _tts
    if len(res_r) >= 10:
        Xtr, Xte, ytr, yte = _tts(X, res_r, test_size=0.25, random_state=42)
        r2_out = r2_score(yte, LinearRegression().fit(Xtr, ytr).predict(Xte))
    else:
        r2_out = float("nan")

    print(f"\n=== Linear regression on residuals (non-Invar) ===")
    print(f"  R² (in-sample)    = {r2:.4f}  (擬合度；會高估泛化)")
    print(f"  R² (held-out 25%) = {r2_out:.4f}  ← 以此評估泛化 (F-SCI-03，非循環校驗)")
    print(f"  Intercept = {reg.intercept_:+.2f} K")
    print(f"\n  Coefficients (sorted by |coef|):")
    coefs = sorted(zip(feature_names, reg.coef_), key=lambda x: abs(x[1]), reverse=True)
    for name, c in coefs:
        print(f"    {name:<20} {c:+10.2f} K per unit")

    # Per-feature correlation with residuals
    print(f"\n=== Pearson correlation (feature vs residual, non-Invar) ===")
    corrs = []
    for i, name in enumerate(feature_names):
        r = np.corrcoef(X[:, i], res_r)[0, 1]
        corrs.append((name, r))
    corrs.sort(key=lambda x: abs(x[1]), reverse=True)
    for name, r in corrs:
        bar = "#" * int(abs(r) * 30)
        sign = "+" if r > 0 else "-"
        print(f"  {name:<20} r={r:+.4f}  {sign}{bar}")

    # Binned analysis: residual by Si+Al content
    print(f"\n=== Residual by Si+Al bin (all samples) ===")
    sial = si + al
    bins = [0, 0.05, 0.10, 0.15, 0.20, 0.30, 0.50]
    for lo, hi in zip(bins[:-1], bins[1:]):
        m = (sial >= lo) & (sial < hi)
        if m.sum() >= 3:
            print(f"  Si+Al [{lo:.2f},{hi:.2f}): n={m.sum():4d}  "
                  f"mean_resid={residual[m].mean():+7.1f} K  "
                  f"std={residual[m].std():.1f} K")

    print(f"\n=== Residual by Cr bin (all samples) ===")
    bins_cr = [0, 0.05, 0.10, 0.15, 0.25, 0.50]
    for lo, hi in zip(bins_cr[:-1], bins_cr[1:]):
        m = (cr >= lo) & (cr < hi)
        if m.sum() >= 3:
            print(f"  Cr [{lo:.2f},{hi:.2f}):  n={m.sum():4d}  "
                  f"mean_resid={residual[m].mean():+7.1f} K  "
                  f"std={residual[m].std():.1f} K")

    print(f"\n=== Residual by Mn bin (all samples) ===")
    bins_mn = [0, 0.05, 0.10, 0.20, 0.40]
    for lo, hi in zip(bins_mn[:-1], bins_mn[1:]):
        m = (mn >= lo) & (mn < hi)
        if m.sum() >= 3:
            print(f"  Mn [{lo:.2f},{hi:.2f}):  n={m.sum():4d}  "
                  f"mean_resid={residual[m].mean():+7.1f} K  "
                  f"std={residual[m].std():.1f} K")

    print(f"\n=== Residual by mag_frac bin (all samples) ===")
    mag_all = fe + ni + co
    bins_mag = [0, 0.3, 0.5, 0.7, 0.85, 1.0]
    for lo, hi in zip(bins_mag[:-1], bins_mag[1:]):
        m = (mag_all >= lo) & (mag_all < hi)
        if m.sum() >= 3:
            print(f"  mag [{lo:.2f},{hi:.2f}): n={m.sum():4d}  "
                  f"mean_resid={residual[m].mean():+7.1f} K  "
                  f"std={residual[m].std():.1f} K")

    # Spot-check famous alloys
    print(f"\n=== Famous alloy spot check ===")
    famous = {
        "Permalloy Ni80Fe20":         {'Ni':0.80,'Fe':0.20},
        "Sendust Fe85Si9Al6":         {'Fe':0.85,'Si':0.09,'Al':0.06},
        "Hiperco50 Fe50Co50":         {'Fe':0.50,'Co':0.50},
        "Fe65Ni35 (Invar)":           {'Fe':0.65,'Ni':0.35},
        "Alnico5 Fe51Co24Ni14Al8Cu3": {'Fe':0.51,'Co':0.24,'Ni':0.14,'Al':0.08,'Cu':0.03},
    }
    elem_idx = {e: i for i, e in enumerate(OUR_ELEMENTS)}
    for name, comp_dict in famous.items():
        comp_vec = np.zeros((1, len(OUR_ELEMENTS)), dtype=np.float32)
        for e, f in comp_dict.items():
            comp_vec[0, elem_idx[e]] = f
        tc_formula, _, _, _ = physics_based_properties_batch(comp_vec)
        print(f"  {name:<40} formula={tc_formula[0]-273.15:+6.1f} °C")


if __name__ == "__main__":
    main()
