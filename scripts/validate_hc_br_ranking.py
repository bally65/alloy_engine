"""A1-2: Hc / Br / sigma_y indirect validation via ranking test (n=10 famous alloys)."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import torch
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).parent.parent))
from alloy_engine.config import CHECKPOINT_DIR, DEFAULT_DEVICE
from alloy_engine.models.surrogate import SurrogateBundle

ELEMENTS = ['Fe', 'Ni', 'Co', 'Cr', 'Mn', 'Cu', 'Mo', 'Si', 'Al', 'V']

# ── Literature values ─────────────────────────────────────────────────────────
# Sources: Bozorth, Cullity, Carpenter datasheet, Magnetics datasheet, NEMA datasheet
ALLOYS = [
    # name,               composition,                              Hc(A/m), Br(T), sy(MPa), soft?
    ("Pure Fe",           {"Fe": 1.00},                            80,    1.40,  130,   True),
    ("Permalloy",         {"Ni": 0.80, "Fe": 0.20},                0.4,   0.70,  220,   True),
    ("Mu-Metal",          {"Ni": 0.77, "Fe": 0.14, "Cu": 0.05, "Mo": 0.04}, 0.2, 0.60, 240, True),
    ("Sendust",           {"Fe": 0.85, "Si": 0.09, "Al": 0.06},   5,     1.00,  350,   True),
    ("Hiperco50",         {"Fe": 0.50, "Co": 0.50},                80,    2.40,  420,   True),
    ("Supermalloy",       {"Ni": 0.79, "Fe": 0.16, "Mo": 0.05},   0.16,  0.70,  290,   True),
    ("Silicon Steel",     {"Fe": 0.97, "Si": 0.03},                40,    2.00,  310,   True),
    ("Permendur",         {"Fe": 0.50, "Co": 0.48, "V": 0.02},    160,   2.40,  470,   True),
    ("Alnico5",           {"Fe": 0.51, "Co": 0.24, "Ni": 0.14, "Al": 0.08, "Cu": 0.03}, 51000, 1.25, 380, False),
    ("Pure Ni",           {"Ni": 1.00},                            60,    0.60,  140,   True),
]


def comp_vec(comp_dict, device):
    v = np.zeros((1, len(ELEMENTS)), dtype=np.float32)
    for e, f in comp_dict.items():
        v[0, ELEMENTS.index(e)] = f
    return torch.from_numpy(v).to(device)


def main():
    bundle = SurrogateBundle.load(CHECKPOINT_DIR / "bundle.pt", device=DEFAULT_DEVICE)

    rows = []
    for name, comp_d, lit_hc, lit_br, lit_sy, is_soft in ALLOYS:
        t = comp_vec(comp_d, DEFAULT_DEVICE)

        # deterministic prediction
        det = bundle.predict_properties(t)
        pred_tc_C  = det["Tc"].item()  - 273.15
        pred_hc    = det["Hc"].item()
        pred_br    = det["Br"].item()
        pred_sy    = det["strength"].item()

        # MC Dropout
        mc = bundle.predict_properties_with_uncertainty(t, n_samples=30)
        hc_mean = mc["Hc_mean"].item()
        hc_std  = mc["Hc_std"].item()
        br_mean = mc["Br_mean"].item()
        br_std  = mc["Br_std"].item()
        sy_mean = mc["strength_mean"].item()
        sy_std  = mc["strength_std"].item()

        n_elem = len(comp_d)
        rows.append({
            "alloy":    name,
            "type":     "soft" if is_soft else "hard",
            "n_elem":   n_elem,
            "lit_Hc":   lit_hc,
            "pred_Hc":  round(pred_hc,  2),
            "hc_mean":  round(hc_mean,  2),
            "hc_std":   round(hc_std,   2),
            "lit_Br":   lit_br,
            "pred_Br":  round(pred_br,  3),
            "br_mean":  round(br_mean,  3),
            "br_std":   round(br_std,   4),
            "lit_sy":   lit_sy,
            "pred_sy":  round(pred_sy,  1),
            "sy_mean":  round(sy_mean,  1),
            "sy_std":   round(sy_std,   1),
            "pred_Tc_C": round(pred_tc_C, 1),
        })

    df = pd.DataFrame(rows)

    # ── Print full table ──────────────────────────────────────────────────────
    print("=== Full prediction table ===")
    print(f"{'Alloy':<16} {'Type':<5} {'litHc':>8} {'predHc':>8} {'ratioHc':>8} "
          f"{'litBr':>6} {'predBr':>7} {'litSy':>7} {'predSy':>7}")
    for _, r in df.iterrows():
        ratio_hc = r["pred_Hc"] / r["lit_Hc"] if r["lit_Hc"] > 0 else float("nan")
        print(f"  {r['alloy']:<16} {r['type']:<5} {r['lit_Hc']:>8.2f} {r['pred_Hc']:>8.2f} "
              f"{ratio_hc:>8.3f} {r['lit_Br']:>6.2f} {r['pred_Br']:>7.3f} "
              f"{r['lit_sy']:>7.0f} {r['pred_sy']:>7.1f}")

    # ── Spearman correlations ─────────────────────────────────────────────────
    all_mask  = [True] * len(df)
    soft_mask = df["type"] == "soft"

    def sp(a, b):
        r, p = spearmanr(a, b)
        return r, p

    r_all_hc,  p_all_hc  = sp(df["pred_Hc"],  df["lit_Hc"])
    r_soft_hc, p_soft_hc = sp(df.loc[soft_mask, "pred_Hc"],
                               df.loc[soft_mask, "lit_Hc"])

    r_all_br,  p_all_br  = sp(df["pred_Br"],  df["lit_Br"])
    r_soft_br, p_soft_br = sp(df.loc[soft_mask, "pred_Br"],
                               df.loc[soft_mask, "lit_Br"])

    r_all_sy,  p_all_sy  = sp(df["pred_sy"],  df["lit_sy"])

    print("\n=== Spearman rank correlations ===")
    print(f"  {'Property':<8}  {'Full r':>7}  {'Full p':>7}  "
          f"{'Soft r':>7}  {'Soft p':>7}  n_soft")
    print(f"  {'Hc':<8}  {r_all_hc:>+7.4f}  {p_all_hc:>7.4f}  "
          f"{r_soft_hc:>+7.4f}  {p_soft_hc:>7.4f}  {soft_mask.sum()}")
    print(f"  {'Br':<8}  {r_all_br:>+7.4f}  {p_all_br:>7.4f}  "
          f"{r_soft_br:>+7.4f}  {p_soft_br:>7.4f}  {soft_mask.sum()}")
    print(f"  {'sigma_y':<8}  {r_all_sy:>+7.4f}  {p_all_sy:>7.4f}  "
          f"{'N/A':>7}  {'N/A':>7}  N/A")

    # ── Hard vs soft Hc separation ────────────────────────────────────────────
    soft_mean_hc = df.loc[soft_mask, "pred_Hc"].mean()
    hard_mean_hc = df.loc[~soft_mask, "pred_Hc"].mean()
    ratio = hard_mean_hc / soft_mean_hc if soft_mean_hc > 0 else float("nan")
    alnico_rank = int(df.sort_values("pred_Hc", ascending=False)["alloy"].tolist().index("Alnico5")) + 1

    print(f"\n=== Hard vs soft Hc separation ===")
    print(f"  Soft-mag mean pred Hc: {soft_mean_hc:.2f} A/m")
    print(f"  Hard-mag pred Hc:      {hard_mean_hc:.2f} A/m  (Alnico5)")
    print(f"  Hard/soft ratio:       {ratio:.1f}×  (expected ~100-1000×)")
    print(f"  Alnico5 rank by pred Hc (1=highest): {alnico_rank}/10")
    lit_alnico_rank = int(df.sort_values("lit_Hc", ascending=False)["alloy"].tolist().index("Alnico5")) + 1
    print(f"  Alnico5 rank by lit  Hc (1=highest): {lit_alnico_rank}/10")

    # ── MC uncertainty on Hc ─────────────────────────────────────────────────
    print(f"\n=== MC Dropout Hc_mean +/- Hc_std (n=30) ===")
    print(f"  {'Alloy':<16}  {'Hc_mean':>8}  {'Hc_std':>7}  {'lit_Hc':>8}  "
          f"{'abs_err':>8}  {'std/err':>8}  note")
    for _, r in df.sort_values("lit_Hc").iterrows():
        abs_err = abs(r["hc_mean"] - r["lit_Hc"])
        ratio_ue = r["hc_std"] / abs_err if abs_err > 0.01 else float("nan")
        note = ""
        if ratio_ue < 0.1:
            note = "over-confident"
        elif ratio_ue > 2:
            note = "well-calibrated"
        print(f"  {r['alloy']:<16}  {r['hc_mean']:>8.2f}  {r['hc_std']:>7.2f}  "
              f"{r['lit_Hc']:>8.2f}  {abs_err:>8.2f}  {ratio_ue:>8.3f}  {note}")

    # ── MC Br ─────────────────────────────────────────────────────────────────
    print(f"\n=== MC Dropout Br_mean +/- Br_std (n=30) ===")
    print(f"  {'Alloy':<16}  {'Br_mean':>7}  {'Br_std':>6}  {'lit_Br':>7}  {'abs_err':>8}")
    for _, r in df.sort_values("lit_Br").iterrows():
        print(f"  {r['alloy']:<16}  {r['br_mean']:>7.3f}  {r['br_std']:>6.4f}  "
              f"{r['lit_Br']:>7.3f}  {abs(r['br_mean'] - r['lit_Br']):>8.3f}")

    # save df
    df.to_csv("results/a1_ranking_raw.csv", index=False)
    print("\n  Raw data saved to results/a1_ranking_raw.csv")

    # Return key numbers for report writing
    return {
        "r_all_hc": r_all_hc, "p_all_hc": p_all_hc,
        "r_soft_hc": r_soft_hc, "p_soft_hc": p_soft_hc,
        "r_all_br": r_all_br, "p_all_br": p_all_br,
        "r_soft_br": r_soft_br, "p_soft_br": p_soft_br,
        "r_all_sy": r_all_sy, "p_all_sy": p_all_sy,
        "hard_soft_ratio": ratio,
        "alnico_rank": alnico_rank,
        "df": df,
    }


if __name__ == "__main__":
    main()
