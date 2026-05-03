# Delta_M Boundary Analysis — Physical Findings

**Analysis date**: 2026-05-03  
**Scenario**: 中溫廢熱_350C | **Element set**: Fe/Ni/Co/Cr/Mn/Cu/Mo/Si/Al/V  
**Method**: GA threshold sweep, 7 runs (thr = 0.05 → 0.40), 50K pop × 100 gen each

---

## 1. Physical Ceiling of delta_M

**Maximum achievable delta_M: ~0.232 T**

This ceiling was reached at thr=0.30 with composition **Fe83.1-Cr16.3** (near-binary).  
At thr=0.40, the GA produced delta_M=0.227 T — still below the 0.40 T threshold — confirming the physical limit is approximately **0.23–0.24 T** for our element set.

**What drives this ceiling?**

The thermomagnetic delta_M is computed as:
```
delta_M = M(T_target - 30K) - M(T_target + 30K)
M(T) = Ms × sqrt(max(1 - T/Tc, 0))   [mean-field β=0.5]
```

To maximize delta_M, we need:
- **High Ms (Br)**: Maximized by Fe-rich composition (~80–83% Fe)
- **Tc slightly above T_target**: The function is steepest near Tc, so Tc ≈ T_target + 20–30 K is optimal
- **Narrow window straddles the steep M(T) slope**: Always satisfied by design

The physical limit is therefore set by **surrogate-predicted Br** for Fe-rich compositions at Tc near 350°C. Fe82-Cr16 gives Br ≈ 0.72–0.75 T, and with M(T) = Br × sqrt(...), the maximum delta_M achievable is ~0.23 T.

**Compositions reaching the ceiling are chemically reasonable:**
- Fe83% is a standard ferritic iron composition
- Cr 12–16% is within the stainless steel / Fe-Cr soft magnetic family
- No exotic elements, no phase instability flags from chemistry constraint

---

## 2. Trade-off Shape

### delta_M vs. Threshold

| Threshold | Actual delta_M | Status |
|-----------|---------------|--------|
| 0.05–0.15 | 0.140–0.178 T | GA ignores constraint (other objectives dominate) |
| 0.20 | 0.201 T | Constraint is **binding** — just barely met |
| 0.25 | 0.225 T | Constraint drives composition change |
| 0.30 | **0.232 T** | Physical ceiling reached |
| 0.40 | 0.227 T | **Unreachable** — GA cannot satisfy constraint |

The delta_M curve is **not simply monotonic**: at thr=0.15 the GA found a solution *below* the threshold (delta_M=0.140), indicating that below 0.20 T the quadratic penalty is soft enough that other objectives dominate.

### Fitness vs. Threshold (Pareto knee analysis)

```
thr=0.05:  fit=0.698
thr=0.10:  fit=0.699
thr=0.15:  fit=0.699  ← sweet spot (delta_M not yet binding)
thr=0.20:  fit=0.695  ← v5.0 baseline, minimal fitness cost
thr=0.25:  fit=0.510  ← -27% fitness drop: PARETO KNEE
thr=0.30:  fit=0.361  ← -48% drop: severe Tc accuracy loss
thr=0.40:  fit=0.200  ← -71% drop: unreachable
```

**The Pareto knee is between 0.20 T and 0.25 T.** At thr=0.25, fitness drops by 0.185 points (−27%) while delta_M only gains 0.024 T. The marginal cost per T of delta_M rises sharply.

### What is sacrificed for higher delta_M?

Examining Top-1 results as threshold rises:

1. **Tc accuracy**: At thr=0.20, Tc offset = +15°C (within tc_tolerance=30°C). At thr=0.30, offset = +29°C (near the soft boundary). The GA trades Tc accuracy for magnetic flux density.

2. **Composition simplification**: Multi-element alloys (thr=0.05–0.20: 3–5 active elements) collapse to binary Fe-Cr (thr=0.25–0.40: 2–3 active elements). This sacrifices delta_S_M diversity but is chemically stable.

3. **Hc increases slightly** (192 → 238 A/m), still well within soft magnetic range (< 400 A/m).

4. **ΔS_M stays constant** (~6.7–6.9 J/(kg·K)) above thr=0.20, because the Fe-rich high-delta_M compositions have nearly identical magnetic moment densities.

---

## 3. GA Behavior: Composition Evolution

| Threshold | Fe | Co | Ni | Cr | Cu | Si | Pattern |
|-----------|----|----|----|----|----|----|---------|
| 0.05 | 74% | 3% | 0% | 13% | 6% | 3% | Diverse, uses Co/Cu for softness |
| 0.10 | 77% | 1% | 1% | 13% | 8% | 0% | Cu increases (high κ bonus) |
| 0.15 | 73% | 1% | 4% | 12% | 4% | 4% | Diverse, delta_M not the driver |
| 0.20 | 81% | 0% | 1% | 14% | 0% | 0% | Cu/Si purged, Fe dominant |
| 0.25 | 82% | 0% | 0% | 12% | 0% | 0% | Near-binary Fe-Cr |
| 0.30 | 83% | 0% | 0% | 16% | 0% | 0% | Binary Fe-Cr |
| 0.40 | 82% | 0% | 0% | 12% | 0% | 0% | Same, cannot improve |

**Pattern**: Below thr=0.20, GA uses the full element palette (Co for Tc boosting, Cu for kappa, Si for Hc reduction). At and above thr=0.20, non-magnetic elements (Cu, Si, Al) are systematically purged since they dilute Ms and therefore reduce delta_M. The solution converges to pure Fe-Cr, which is the highest-Fe composition that can be made with the right Tc via Cr content.

**Notably absent in all solutions**: Co is almost never used (max 3% at thr=0.05). This is surprising — Co has the highest magnetic moment of all elements in the set. The reason: Co raises Tc too aggressively (Co Tc=1400°C), pushing Tc far above 350°C target and hurting tc_hit_score. The Tc penalty dominates.

---

## 4. Feedback to v5.0 Design

### Is v5.0 baseline of 0.20 T correct?

**Yes, 0.20 T is the right baseline.** Quantitative justification:

- At thr=0.20: fitness=0.695, delta_M=0.201 T, Tc offset=+15°C → excellent balance
- At thr=0.25: fitness=0.510 (−27%), delta_M=0.225 T (+12%) → poor trade-off ratio

The fitness cost of raising to 0.25 T is ~27%, while the physical gain is only 12% more delta_M. The current 0.20 T represents the **Pareto-optimal operating point** for our element set.

### Should we propose v5.1?

**Conditional recommendation:**

1. **Do not change the 0.20 T floor.** It is well-calibrated.

2. **Consider adding Co to the element set** if higher delta_M is needed. Co's low representation suggests the current set is Co-limited for delta_M maximization — adding Co as a Tc-boosting element alongside a Tc-lowering element (e.g., Mn) could allow both high delta_M and precise Tc targeting.

3. **The 0.232 T ceiling is the model's limit, not physics' limit.** Real Fe-Ni/Fe-Co alloys achieve delta_M > 0.5 T (Permalloy, Hiperco). The limitation is our surrogate's Br under-prediction (systematic −0.3 to −1.6 T vs. literature, noted in MODEL_CARD v3.2). A recalibrated surrogate with better Br prediction would likely push the achievable delta_M above 0.40 T.

4. **v5.1 candidate:** Surrogate Br calibration + Co concentration freedom (relax the Tc penalty for Co to allow higher delta_M at target Tc). Estimated effort: 1 day (retrain + ablation).
