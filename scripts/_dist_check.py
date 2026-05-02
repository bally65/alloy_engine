import pandas as pd
import numpy as np

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

fm = pd.read_csv('external/NEMAD/Dataset/FM_with_curie.csv')
mask = (fm[OTHER_ELEM] == 0).all(axis=1) & (fm[OUR_ELEMENTS] > 0).any(axis=1)
df = fm[mask].copy()
df = df[df['Mean_TC_K'] >= 50]
df = df[df[OUR_ELEMENTS].max(axis=1) <= 0.95]
print(f"Cleaned samples: {len(df)}")

print()
print("=== Element abundance (618 samples) ===")
print(f"  {'Elem':<6} {'Count':>8} {'Freq%':>7} {'mean_pct':>10} {'max_pct':>10}")
for e in OUR_ELEMENTS:
    present = (df[e] > 0).sum()
    mean_v = df[df[e] > 0][e].mean() * 100 if present > 0 else 0
    max_v  = df[e].max() * 100
    print(f"  {e:<6} {present:>8} {present/len(df)*100:>7.1f} {mean_v:>10.1f} {max_v:>10.1f}")

print()
print("=== Tc distribution (degC) ===")
tc_c = df['Mean_TC_K'] - 273.15
print(f"  min:    {tc_c.min():.1f}")
print(f"  max:    {tc_c.max():.1f}")
print(f"  mean:   {tc_c.mean():.1f}")
print(f"  median: {tc_c.median():.1f}")
print(f"  std:    {tc_c.std():.1f}")
print()
bins = [(-300,0),(0,100),(100,200),(200,300),(300,400),(400,500),(500,600),(600,700),(700,900)]
for lo, hi in bins:
    n = ((tc_c >= lo) & (tc_c < hi)).sum()
    print(f"  {lo:5d} ~ {hi:<5d} degC : {n:4d}  ({n/len(df)*100:.1f}%)")
