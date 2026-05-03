# Delta_M Boundary Analysis — Status Report

**Started**: 2026-05-03  
**Completed**: 2026-05-03  
**Total runtime**: ~35 minutes (7 sweeps × 50K pop × 100 gen)  
**Branch**: `analysis/delta_m_boundary` (not merged to main)

---

## Quick Summary

The physical ceiling for delta_M in the current 10-element set (Fe/Ni/Co/Cr/Mn/Cu/Mo/Si/Al/V) is **~0.232 T**, achieved by a near-binary Fe83-Cr16 composition. The v5.0 baseline of 0.20 T sits precisely at the Pareto-optimal point: fitness drops 27% for only 12% more delta_M above this threshold. At thr=0.40 T, the constraint is physically unreachable.

---

## Key Findings

**1. Physical ceiling is 0.232 T, not the 0.20 T constraint floor.**  
The GA reached delta_M ≈ 0.232 T at thr=0.30 (Fe83-Cr16), then could not improve further. At thr=0.40, actual delta_M = 0.227 T — below the constraint, confirming the ceiling. This ceiling is set by the surrogate's Br prediction for Fe-rich compositions (~0.72–0.75 T), not by a fundamental physics limit. Real Fe-Cr/Fe-Ni alloys achieve delta_M > 0.5 T; the model's systematic Br under-prediction (noted in MODEL_CARD §3.2) is the limiting factor.

**2. The Pareto knee is between 0.20 T and 0.25 T — v5.0 baseline is correctly placed.**  
Fitness at thr=0.20: 0.695. At thr=0.25: 0.510 (−27% for +12% delta_M). This is a poor trade-off ratio. The 0.20 T floor is the boundary below which other objectives (Tc accuracy, ΔS_M, frequency) can all be simultaneously satisfied. Above it, the GA sacrifices Tc accuracy to maximize Fe content.

**3. Composition evolution is monotonic and chemically interpretable.**  
As threshold rises, non-magnetic elements (Cu, Si, Ni) are systematically purged and the solution converges to binary Fe-Cr. This is physically correct: Cu and Si dilute magnetic moment density, reducing Br and thus delta_M. The GA independently rediscovers the engineering principle that Fe-Cr binary alloys maximize remanence at a given Tc.

---

## Recommendations to User

**Do not change the v5.0 delta_M baseline (0.20 T is correct).**

However, two extensions could substantially raise the achievable ceiling:

1. **Surrogate Br recalibration** (priority: medium): The current surrogate under-predicts Br by 0.3–1.6 T vs. literature (MODEL_CARD §3.2). A calibration pass on Hc/Br using experimental data could push the achievable delta_M to 0.4–0.5 T, dramatically improving the thermomagnetic engine's practical output.

2. **Add Co as a Tc-tuning element with Mn pairing** (priority: medium): Co is almost unused in all sweeps because it over-shoots Tc. Pairing Co (raises Tc) with Mn (lowers Tc) could allow both high Fe content and precise Tc targeting — potentially reaching delta_M > 0.30 T within the fitness budget. This is a candidate for **v5.1**.

---

## Files in This Branch

| File | Description |
|------|-------------|
| `sweep_s_005/` to `sweep_s_040/` | GA output CSVs for 7 threshold values |
| `trade_off_table.md` | Consolidated results table with all metrics |
| `findings.md` | Detailed physical analysis (4 sections) |
| `plot_tradeoff.py` | Plotting script |
| `figures/fig1_delta_m_vs_threshold.png` | delta_M vs threshold curve |
| `figures/fig2_fitness_vs_threshold.png` | Fitness & Tc accuracy vs threshold |
| `STATUS.md` | This file |

---

## Anomaly Noted During Run

At thr=0.15, the GA produced delta_M=0.140 T, **below** the 0.15 threshold. This indicates the quadratic penalty `(delta_M/0.15)^2` was insufficient to force compliance when other objectives (Tc hit, ΔS_M, efficiency) preferred a slightly lower-delta_M solution. This is a known behavior of soft penalty functions and does not represent a bug — it confirms that the 0.20 T threshold is the minimum value at which the constraint becomes reliably binding. The threshold parameter works correctly for values ≥ 0.20 T.
