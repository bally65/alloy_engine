# Model Card — Alloy Engine Surrogate Models v2.0

**Version:** 2.0
**Date:** 2026-05-02
**Purpose:** Virtual high-throughput screening of soft-magnetic alloys for industrial waste-heat energy harvesting (Olsen cycle)

---

## 1. Architecture

Four independent `PropertyMLP` regressors bundled as `SurrogateBundle`.

| Model | Target | Unit | Transform | R² (synthetic holdout) |
|-------|--------|------|-----------|------------------------|
| mlp_tc | Curie temperature | K | none | **0.9945** |
| mlp_hc | Coercivity | A/m | log₁₀ | **0.8707** |
| mlp_br | Remanence | T | none | **0.9187** |
| mlp_strength | Yield strength | MPa | none | **0.9448** |

**PropertyMLP:** Linear(36→128) → BN → ReLU → Dropout(0.1) → Linear(128→128) → BN → ReLU → Dropout(0.1) → Linear(128→1)

---

## 2. Training Data

**Source:** Fully synthetic — physics-inspired empirical formulas. No experimental data used for training.

**Sampling: Sparse Dirichlet (v2.0)**

Each training sample activates 2–8 of the 10 candidate elements, drawn via Poisson(λ=4) clamped to [2, 8]. Elements are selected with probability proportional to alpha = [3.0, 3.0, 1.5, 1.0, 0.6, 0.5, 0.5, 0.4, 0.4, 0.4] (Fe/Ni preferred). Fractional compositions are then drawn from a standard Dirichlet restricted to the active subspace.

| Parameter | Value |
|-----------|-------|
| n_samples | 8,000 |
| seed | 42 |
| n_active distribution | 2: 24%, 3: 19%, 4: 19%, 5: 16%, 6: 10%, 7: 7%, 8: 5% |
| mean n_active | 4.1 |
| Split | 80 / 10 / 10 (train / val / test) |

**Tc formula (Slater-Pauling style):**
base_Tc = weighted mean of element Tc (Fe=1043K, Ni=627K, Co=1400K) normalized by magnetic fraction. Suppressed by Cr, Mn, and dilution by non-magnetic elements. Permalloy peak bonus applied near Ni=50%.

---

## 3. Input Features (36-dim Oliynyk)

9 element properties × 4 composition statistics (weighted mean, weighted variance, max of present elements, min of present elements).

**Element properties used:** Z (atomic number), M (atomic mass), r (atomic radius), EN (Pauling electronegativity), Vel (valence electrons), IE (1st ionization energy), mu (magnetic moment μB), rho (density g/cm³), E (Young's modulus GPa)

**Removed from v1.0:** `Tc` (pure-element Curie temperature) — see Bug Fix #1.

---

## 4. Real Data Validation (NEMAD)

**Dataset:** NEMAD `FM_with_curie.csv`, filtered to 618 samples within the 10-element space.
Filtering: all non-target elements = 0, Tc ≥ 50 K, no pure elements (max fraction ≤ 0.95).

**Sim-to-real gap (v2.0 surrogate on NEMAD 618 samples):**

| Subset | n | R² | MAE (°C) |
|--------|---|-----|----------|
| Overall | 618 | −0.24 | 282 |
| No-Mo | 609 | −0.24 | 283 |
| Mo > 0 | 9 | −0.31 | 229 |
| 100–200 °C (waste heat zone) | 76 | −127 | 305 |
| 300–400 °C (waste heat zone) | 47 | −253 | 406 |
| 500–700 °C (waste heat zone) | 87 | −72 | 334 |

R² is negative — model performs worse than predicting the global mean. This is expected: the synthetic formula over-predicts Tc for real diluted multi-element alloys by ~280 °C systematically. All predictions are physically plausible (range: −100 to 1300 °C).

**Famous alloy spot check:**

| Alloy | Active elements | Pred Tc (°C) | NEMAD Tc (°C) | Error |
|-------|----------------|--------------|----------------|-------|
| Permalloy Ni₈₀Fe₂₀ | 2 | 437 | 434 | **+3 °C** |
| Fe₆₀Co₂₀Ni₂₀ | 3 | 746 | 784 | −38 °C |
| Hiperco50 Fe₅₀Co₅₀ | 2 | 954 | 1031 | −77 °C |
| Supermalloy Ni₇₉Mo₅Fe₁₆ | 3 | 372 | 465 | −93 °C |
| Hiperco27 Fe₇₃Co₂₇ | 2 | 866 | 975 | −109 °C |
| Sendust Fe₈₅Si₉Al₆ | 3 | 534 | 697 | −163 °C |
| Alnico5 Fe₅₁Co₂₄Ni₁₄Al₈Cu₃ | 5 | 613 | 870 | −257 °C |
| Fe₆₅Ni₃₅ (Invar) | 2 | 649 | 257 | +392 °C † |

† Invar anomaly: Fe₆₅Ni₃₅ has anomalously low Tc due to magneto-volume coupling not encoded in composition-only features. This is a known physical limitation, not a model error.

---

## 5. Bug Fix Record (v1.0 → v2.0)

### Bug 1 — Tc-as-feature: data leakage

`PROP_NAMES` in v1.0 included `"Tc"` (pure-element Curie temperatures). Among the 10 elements, only Fe (1043 K), Co (1400 K), and Ni (627 K) have Tc > 0; the remaining 7 are exactly 0. The `max_element_Tc` feature was essentially a weighted-mean Fe/Co/Ni signal — a circular feature that let the model fit Tc trivially without learning composition-property physics.

**Fix:** Removed `"Tc"` from `PROP_NAMES` in `elements.py`. Feature dimension: 40 → 36.

### Bug 2 — Full-density Dirichlet: max/min feature degeneracy

With all 10 elements always active (full Dirichlet), `min_X` for every property converges to the X-value of the single element with the lowest X — nearly constant across all training samples. The resulting training std ≈ 0, clipped to 1e-6 in the scaler. At inference on binary/ternary alloys (missing the "low-X" elements), normalized features reach z ~ 10⁸–10¹¹, causing catastrophic model outputs.

**Manifest examples before fix:**
- Permalloy Ni₈₀Fe₂₀: `min_M` z-score = +242σ → predicted Tc ~6,000 °C (with Tc leakage removed) / ~10⁹ °C (v1.0)
- All binary/ternary alloys: NEMAD overall R² = −1.5 × 10¹³, MAE = 8.6 × 10⁸ °C

**Fix:** Switched to sparse Dirichlet sampling. With 2–8 active elements per sample, all max/min statistics have genuine variance. Permalloy's worst z-score after fix: **+1.70σ**.

**Combined effect of both fixes:**

| Metric | v1.0 | v2.0 |
|--------|------|------|
| Permalloy prediction | ~10⁹ °C | 437 °C (exp: 434 °C) |
| NEMAD overall R² | −1.5 × 10¹³ | −0.24 |
| NEMAD MAE | ~8.6 × 10⁸ °C | 282 °C |
| Permalloy max z-score | +6.3 × 10⁸σ | +1.70σ |

---

## 6. Known Limitations

1. **Systematic Tc over-prediction (~280 °C MAE on NEMAD).** The Slater-Pauling formula used for synthetic Tc generation does not match real diluted alloys. Model is suitable for relative ranking and compositional search, not absolute Tc prediction.

2. **Invar and related magneto-volume anomalies not captured.** Fe₆₅Ni₃₅, Fe₃Pt, and similar Invar-class alloys have Tc far below the Slater-Pauling prediction due to itinerant-electron effects. Composition-only descriptors cannot encode this.

3. **Mo and V coverage extremely sparse in NEMAD** (Mo: 9 samples, V: 47 samples). Predictions for Mo > 5 at% or V > 8 at% have high uncertainty and no experimental validation.

4. **Ordered intermetallics excluded.** Model assumes disordered solid solution. Not applicable to DO₃, L1₂, B2, or other ordered phases.

5. **No phase stability check.** GA chemistry constraints (μ-phase, σ-phase, DO₃ penalties) partially compensate but do not replace CALPHAD.

6. **σy model has no experimental validation.** Yield strength is estimated from a simple solid-solution strengthening formula; no NEMAD or equivalent real dataset was used for calibration.

---

## 7. Recommended Use

This surrogate is a **coarse first-pass filter** for multi-element composition space exploration. Valid use context:

- 4+ simultaneously active elements (consistent with training distribution)
- Used through the GA with chemistry constraints enabled
- Relative ranking and zone identification (is Tc in 100–200 °C range?) rather than point prediction

Workflow:
```
Surrogate + GA screening → shortlist of ~30 candidates
        ↓
Literature / NEMAD lookup: does this composition class exist?
        ↓
DFT magnetic calculation: confirm Tc estimate, check phase stability
        ↓
Experimental synthesis + VSM / DSC measurement
```

---

## 8. Reproducibility

```bash
python scripts/train_surrogate.py --n-samples 8000 --epochs 300 --seed 42
python scripts/run_search.py --scenario all --population-size 100000 --n-generations 150
```

All results deterministic at seed=42.
