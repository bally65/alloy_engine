import sys, pandas as pd, numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

df = pd.read_csv("results/top_alloy_candidates.csv")
elem_cols = ["Fe_at%","Ni_at%","Co_at%","Cr_at%","Mn_at%","Cu_at%","Mo_at%","Si_at%","Al_at%","V_at%"]
df["n_active"] = (df[elem_cols] > 0.5).sum(axis=1)

print("GA配方非零元素數分佈 (>0.5 at%):")
print(df["n_active"].value_counts().sort_index().to_string())
print(f"\nMean n_active: {df['n_active'].mean():.2f}")

print("\nTop 3 per scenario:")
for sc in df["scenario"].unique():
    sub = df[df["scenario"]==sc].head(3)
    print(f"  {sc}:")
    for _, r in sub.iterrows():
        nonzero = {c.replace("_at%",""): round(r[c],1) for c in elem_cols if r[c] > 0.5}
        print(f"    rank{int(r['rank'])}: {nonzero}  Tc={r['Tc_C']:.1f}C  fitness={r['fitness']:.4f}")
