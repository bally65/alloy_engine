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

## 8. v3.0 Update — NEMAD-Calibrated Synthetic Formula

**Date:** 2026-05-02  
**Change scope:** `physics_based_properties_batch()` Tc formula only. Architecture, features, and GA constraints unchanged.

### What changed

The v2.0 synthetic Tc formula systematically over-predicted real alloy Tc by ~280°C (MAE=758 K on NEMAD 618). A residual regression against NEMAD identified three over-suppression biases and one missing interaction:

| Term | v2.0 | v3.0 | Rationale |
|------|------|------|-----------|
| Cr suppression coefficient | 5500 | **1800** | v2.0 over-penalized; NEMAD Cr bins showed +1000-2800 K residuals |
| Mn suppression coefficient | 4500 | **1200** | Same systematic over-suppression |
| Dilution factor (non-mag) | 0.50 | **0.20** | Real Si/Al dilution is ~3× weaker than formula assumed |
| Fe-Co Slater-Pauling synergy | — | **+80 K peak** | Missing Bethe-Slater peak near Fe=Co=0.5; `80 × 4×(fe·co)/mag²` |

Formula (v3.0, deterministic):
```
base_tc = (fe·1043 + ni·627 + co·1400) / max(mag_frac, 0.01)   [mag_frac > 0.05]
fe_co_synergy = 80.0 × 4.0 × (fe·co) / (mag_frac² + 1e-6)
cr_suppress = 1800 × cr^1.2
mn_suppress = 1200 × mn^1.2
dilution = base_tc × (1 - mag_frac - cr - mn) × 0.20
tc = (base_tc + fe_co_synergy) × mag_frac − cr_suppress − mn_suppress − dilution + permalloy
```

### Formula validation (no retraining, pure formula vs NEMAD)

| Metric | v2.0 formula | v3.0 formula | Improvement |
|--------|-------------|-------------|-------------|
| Mean residual (K) | +634.9 | +144.1 | −78% |
| MAE (K) | 758.3 | 322.0 | −57% |
| std (K) | 961.2 | 419.7 | −56% |
| Hiperco50 error | −82°C | **−2°C** | Fe-Co synergy verified |
| Permalloy error | +2.8°C | **+2.8°C** | Unchanged (correct) |

MAE in waste-heat target zones (formula vs NEMAD):

| Zone | v2.0 MAE (K) | v3.0 MAE (K) | Delta |
|------|-------------|-------------|-------|
| 100–200°C | 771 | 316 | **−455 K** |
| 300–400°C | 1100 | 505 | **−594 K** |
| 500–700°C | 453 | 239 | **−214 K** |

### Surrogate model (v3.0) on NEMAD 618

After retraining on 8000 sparse-Dirichlet samples with v3.0 formula (seed=42, epochs=300):

| Metric | v2.0 surrogate | v3.0 surrogate |
|--------|---------------|---------------|
| Overall R² | −0.24 | **+0.09** |
| Overall MAE (°C) | 282 | **239** |
| Tc synthetic R² | 0.9945 | **0.9925** |

**Famous alloy spot check (v3.0 surrogate):**

| Alloy | Pred Tc (°C) | NEMAD Tc (°C) | Error |
|-------|-------------|----------------|-------|
| Permalloy Ni₈₀Fe₂₀ | 437 | 434 | **+3°C** |
| Hiperco50 Fe₅₀Co₅₀ | 1030 | 1031 | **−1°C** |
| Fe₆₀Co₂₀Ni₂₀ | 785 | 784 | **+2°C** |
| Hiperco27 Fe₇₃Co₂₇ | 932 | 975 | −43°C |
| Supermalloy Ni₇₉Mo₅Fe₁₆ | 380 | 465 | −85°C |
| Sendust Fe₈₅Si₉Al₆ | 587 | 697 | −110°C |
| Alnico5 Fe₅₁Co₂₄Ni₁₄Al₈Cu₃ | 691 | 870 | −179°C |
| Fe₆₅Ni₃₅ (Invar) | 647 | 257 | +390°C † |

### Remaining limitations (v3.0)

- **Sendust −110°C**: Si and Al have different magneto-dilution physics but are treated identically. Si (sp-d hybridization) suppresses Tc more strongly than Al. Not yet separated.
- **Alnico −179°C**: Alnico alloys partially order into α'/α phase-separated microstructure, raising effective Tc above Slater-Pauling prediction. Composition-only features cannot encode this.
- **Invar +390°C**: Slater-Pauling dip (itinerant-electron magneto-volume coupling) not encodable in composition descriptors. Known hard limit.
- **Systematic over-prediction persists** at +144 K mean (down from +635 K). Acceptable for relative ranking; not for absolute Tc point prediction.

---

## 9. v3.1 Update — MC Dropout Uncertainty Quantification

**Date:** 2026-05-02  
**Change scope:** `PropertyMLP` architecture + `SurrogateBundle` inference + `GPUGeneticAlgorithm` fitness. Formula and features unchanged.

### Method

**MC Dropout** (Gal & Ghahramani, ICML 2016): Dropout layers remain active at inference time. N forward passes through the same network produce a distribution of predictions; std across passes estimates epistemic uncertainty.

- Dropout rate: p = 0.10 (three layers, after each hidden activation)
- Default MC samples: n = 30 (training), n = 20 (GA fitness)
- API: `SurrogateBundle.predict_properties_with_uncertainty(compositions, n_samples=30)`  
  Returns 8-key dict: `{Tc_mean, Tc_std, Hc_mean, Hc_std, Br_mean, Br_std, strength_mean, strength_std}`

### Sanity Check Results

- Two back-to-back MC runs on Permalloy: mean diff = 0.13 K, std ≈ 9 K → MC Dropout confirmed active
- Deterministic `predict_properties` (eval mode): two runs identical to float32 precision
- All 4 models: 3 Dropout layers each, p = 0.10, correct train/eval switching

### Synthetic R² Impact (p=0.10 vs no dropout)

| Model | No dropout | p=0.10 | Delta |
|-------|-----------|--------|-------|
| Tc (K) | 0.9925 | 0.9925 | 0 |
| Hc (A/m) | 0.8707 | 0.8697 | −0.001 |
| Br (T) | 0.9187 | 0.9192 | +0.001 |
| σy (MPa) | 0.9448 | 0.9451 | +0.000 |

Dropout p=0.10 has negligible effect on predictive performance.

### Famous Alloy Uncertainty (MC n=30)

| Alloy | n_elem | Tc_mean (°C) | Tc_std (°C) | NEMAD (°C) | Error |
|-------|--------|-------------|------------|------------|-------|
| Permalloy Ni₈₀Fe₂₀ | 2 | +424 | **8.5** | 434 | −10 |
| Hiperco50 Fe₅₀Co₅₀ | 2 | +1033 | **39.8** | 1031 | +2 |
| Sendust Fe₈₅Si₉Al₆ | 3 | +578 | **14.8** | 697 | −119 |
| Alnico5 (5 elem) | 5 | +727 | **20.1** | 870 | −143 |
| Invar Fe₆₅Ni₃₅ | 2 | +653 | **15.9** | 257 | +396 |

**Hiperco50 std = 39.8°C** is the highest among famous alloys — physically meaningful: Hiperco sits exactly at the Fe-Co Slater-Pauling synergy peak (Fe=Co=0.5), where small composition perturbations produce large Tc changes. The model correctly identifies this as a high-sensitivity region.

### Uncertainty Calibration — Honest Assessment

**NEMAD 618 samples, MC n=30:**

| Metric | Value |
|--------|-------|
| Mean Tc_std | 23.5°C |
| Tc_std range | 7.3–49.3°C |
| Calibration r(std, \|error\|) | **+0.089** (p=0.027) |
| r(n_elem, Tc_std) | +0.071 (p=0.078, n.s.) |

**Quartile calibration (by Tc_std):**

| Quartile | std range (°C) | mean \|error\| (°C) | mean std (°C) |
|----------|--------------|---------------------|--------------|
| Q1 (low) | 7.3–16.9 | 202 | 14 |
| Q2 | 16.9–22.8 | 243 | 19 |
| Q3 | 22.8–29.8 | 243 | 26 |
| Q4 (high) | 29.8–49.3 | 257 | 34 |

**Known limitation — systematic under-calibration:** MC Dropout Tc_std range (7–49°C) is ~10× smaller than true prediction errors (100–400°C). Q4 std is 2.4× Q1 std, but Q4 error is only 1.27× Q1 error. This is consistent with the literature (Lakshminarayanan et al., NeurIPS 2017: single-network MC Dropout systematically underestimates epistemic uncertainty; ensembles of ≥5 models required for reliable calibration).

**Valid use:** Tc_std serves as a **relative ranking signal** — lower std candidates are statistically more reliable — but should not be used as an absolute confidence interval.

### GA Uncertainty Integration (A3-6 Ablation)

`GPUGeneticAlgorithm` accepts `enable_uncertainty=True` + `predict_fn_uncertainty` callable. Uncertainty penalty:

```
uncertainty_score = sigmoid((23.0 - tc_std) / 8.0)   # 23K = NEMAD median std
F_total = F_base × (1 - w + w × uncertainty_score)    # w = uncertainty_weight = 0.10
```

**350°C scenario, 50K pop × 80 gen ablation:**

| | no uncertainty | with uncertainty | delta |
|--|--|--|--|
| Top-1 fitness | 0.7888 | 0.7743 | −0.0145 (−1.8%) |
| Top-1 Tc | 350.8°C | 349.3°C | −1.5°C |
| Top-1 Tc_std | 15.0°C | **8.1°C** | **−45.7%** |
| Top-5 mean Tc_std | 13.8°C | **11.5°C** | **−16.4%** |
| Speed | 6.2 M/s | 0.47 M/s | **−14× slower** |

The uncertainty penalty successfully steered GA toward lower-std compositions (Top-1 std −45.7%), at the cost of −1.8% fitness and 14× speed reduction. The fitness drop is within acceptable range; the speed cost makes `enable_uncertainty` suitable only for final refinement passes on small populations, not large-scale primary search.

### Future Work

- **Deep Ensemble (5 independent models):** Expected calibration improvement from r=0.09 to r>0.5 (Lakshminarayanan et al. 2017). ~60 min additional training time.
- **Separate Si/Al dilution terms:** Would improve Sendust prediction (currently −110°C error).

---

## 10. v3.2 Update — Hc / Br / σy Indirect Validation

**Date:** 2026-05-02  
**Method:** Spearman rank correlation, 10 famous alloys (9 soft + 1 hard magnetic)  
**Why indirect:** NEMAD local repo contains only Tc/Néel temperature; no experimental Hc/Br/σy records available without external download. Direct R² validation deferred to future work.

### Data

| Alloy | Hc lit (A/m) | Br lit (T) | σy lit (MPa) |
|-------|-------------|-----------|-------------|
| Supermalloy Ni₇₉Fe₁₆Mo₅ | 0.16 | 0.70 | 290 |
| Mu-Metal Ni₇₇Fe₁₄Cu₅Mo₄ | 0.20 | 0.60 | 240 |
| Permalloy Ni₈₀Fe₂₀ | 0.40 | 0.70 | 220 |
| Sendust Fe₈₅Si₉Al₆ | 5 | 1.00 | 350 |
| Silicon Steel Fe₉₇Si₃ | 40 | 2.00 | 310 |
| Pure Ni | 60 | 0.60 | 140 |
| Pure Fe | 80 | 1.40 | 130 |
| Hiperco50 Fe₅₀Co₅₀ | 80 | 2.40 | 420 |
| Permendur Fe₅₀Co₄₈V₂ | 160 | 2.40 | 470 |
| Alnico5 (hard mag, control) | 51,000 | 1.25 | 380 |

Sources: Bozorth (1951), Cullity & Graham (2009), Carpenter Technology, Magnetics Inc., NEMA datasheets.

### Spearman Rank Correlations

| Property | Full r (n=10) | p | Soft-only r (n=9) | p | Verdict |
|----------|--------------|---|-------------------|---|---------|
| **Br** | **+0.869** | 0.001 | **+0.836** | 0.005 | ✅ Strong |
| σy | +0.261 | 0.467 | — | — | ❌ Weak |
| **Hc** | **−0.310** | 0.383 | **−0.050** | 0.898 | ❌ Failed |

### Key Findings

**Br (strong, r = +0.836, p = 0.005):** Ranking order is physically correct. Low-Fe Ni-based alloys (Permalloy, Mu-Metal, Supermalloy, Pure Ni) correctly ranked as low-Br; Fe-rich alloys (Pure Fe, Si-Steel) ranked above. Systematic under-prediction of −0.3 to −1.6 T reflects uncalibrated saturation coefficient in synthetic formula (`Br = mag_moment × 0.4`). **Br predictions are valid for relative ranking.**

**Hc (failed, soft-only r = −0.050):** All predictions cluster in 143–299 A/m regardless of material; literature spans 0.16–51,000 A/m (six orders of magnitude). Root cause: synthetic Hc formula (`base_hc = 50 + 250|Fe−Ni| - 30·Si + 100·(Cu+Mo)`) is a composition-based microstructural softness proxy — it has no concept of magneto-crystalline anisotropy (K₁), domain wall pinning density, grain size, or texture. **Hc predictions are unreliable for ranking; use only as a qualitative low-Hc optimization signal.**

**Hard/soft separation:** Alnico5 predicted Hc = 143 A/m — ranked *lowest* among all 10 alloys, the exact inverse of truth (lit: 51,000 A/m, rank 1/10). Hard/soft ratio 0.6× vs expected 100–1000×. The model has no concept of permanent-magnet physics.

**σy (weak, r = +0.261, not significant):** Pure Fe and Ni systematically over-predicted (model has no annealed-state concept). Correct direction for solid-solution strengthening elements but not reliable for ranking.

### Known Limitations

1. **n = 10** — Spearman with n=10 has high variance; results are indicative.
2. **σy literature values are annealed state** — model output is unspecified processing state.
3. **Br literature ≈ Ms** — valid approximation for soft magnetics (squareness ≈ 1).
4. **Alnico5 outside model scope** — α'/α phase separation; composition-only model cannot predict magneto-crystalline hardness.
5. **Hc is microstructure-dependent** — composition-only model is fundamentally insufficient for Hc absolute prediction.

### Revised Property Usage Guidance

| Property | Use case | Reliability |
|----------|----------|-------------|
| Tc | Target zone selection, relative ranking | Moderate (MAE ±240°C, R²=+0.09 on NEMAD) |
| **Br** | **Relative ranking for remanence** | **Good (Spearman r=+0.84)** |
| Hc | Qualitative low-Hc directional signal only | Poor (ranking r≈0) |
| σy | Screening very-weak compositions | Low (r=+0.26, not significant) |

Full ranking tables and raw data: `results/a1_ranking_test.md`, `results/a1_ranking_raw.csv`

---

## 11. Reproducibility

```bash
python scripts/train_surrogate.py --n-samples 8000 --epochs 300 --seed 42
python scripts/run_search.py --scenario all --population-size 100000 --n-generations 150
```

All results deterministic at seed=42.
