# Release Notes

## v4.1 — Thermomagnetic Engine Edition (Calibrated)

**Released**: 2026-05-02 (late evening)
**Tag**: v4.1
**Commits**: dd426d3

### Summary

This release marks the project's pivot from generic soft magnetic alloys to specifically thermomagnetic engine materials (Curie motors). It also fixes a "reward hacking" issue where v4.0 GA found Cu-rich (35%) trivial solutions that maximized thermal conductivity at the expense of magnetic performance.

### Key Changes from v4.0

| Aspect | v4.0 | v4.1 | Effect |
|---|---|---|---|
| delta_M normalization | clamp(/1.0) | clamp(/0.5)^0.7 | Permalloy-grade reference |
| kappa normalization | (k-30)/170 | (k-50)/80, capped at 130 | No reward for Cu pile-up |
| delta_M hard floor | none | < 0.20 T penalized quadratically | Industrial usability gate |
| Cu chemistry constraint | none | Cu > 20% penalized | Anti-dilution |
| Weight redistribution | w_tc=0.45 | w_tc=0.30, w_tc_window=0.20 | Tc placement nudged to +25°C |

### v4.1 Validation Results

#### Three thermal scenarios

| Scenario | Top-1 Composition | Tc offset | delta_M | kappa | Industrial analog |
|---|---|---|---|---|---|
| 150°C | Fe69-Cr21-Si2... | +15°C | 0.20 T | ~110 W/mK | Silicon Steel family |
| 350°C | Fe77-Cr11... | +20°C | 0.20 T | ~110 W/mK | Fe-Cr soft magnetic |
| 500°C | Fe83-Cu11-Cr4... | +24°C | 0.20 T | ~110 W/mK | Permendur variant |

All three scenarios converged near (not at) industrial soft magnetic alloy families. This is interpreted as a positive sign: the GA discovered functional analogs to known engineering materials without explicit guidance.

### Positive Findings

- All three scenarios show delta_M precisely at the 0.20 T constraint floor — this indicates the constraint is binding, suggesting 0.20 T is the achievable upper bound within our element selection (Fe/Ni/Co/Cr/Mn/Cu/Mo/Si/Al/V).
- Cu content stabilized at 8-11% (Mu-Metal-like, post anti-Cu chemistry penalty)
- Tc offsets of +15 to +24°C land within the engineering sweet zone (T_target + 20-30K) per the tc_window_score design

### Known Limitations (carried to future work)

1. **No Gd or rare earth elements**: Gd's Tc ≈ 20°C makes it ideal for room-temperature thermomagnetic devices, but our element set excludes it. Future work: extend ELEMENTS to include Gd, Tb, Dy.

2. **Second-order phase transitions only**: Our M(T) ∝ (1-T/Tc)^0.5 approximation assumes Heisenberg-class phase transition. First-order materials (MnAs, Fe-Rh) have sharper transitions and higher delta_M, but require different physics.

3. **delta_M = 0.20 T is industrial threshold but not optimal**: Industrial Gd reaches ~0.6 T in Tc cycling. Our Fe-Cr-Cu family is constrained by composition.

4. **Thermal conductivity κ uses linear mixture**: Underestimates real alloy κ by 30-50% (Nordheim scattering). Relative ranking valid but absolute values not for cycle frequency prediction.

5. **σy threshold relaxed to 150 MPa**: Appropriate for thin-sheet thermomagnetic actuators but excludes structural applications. Different mode='softmag' retains 400 MPa requirement.

### Reproducibility

```bash
git checkout v4.1
pip install -r requirements.txt

# Train surrogate (uses v3.0 NEMAD-calibrated formula)
python scripts/train_surrogate.py --n-samples 8000 --epochs 300 --seed 42

# Search in thermomagnetic mode
python scripts/run_search.py --scenario all --population-size 100000 --n-generations 150 --mode thermomagnetic

# Or run softmag mode for backward compatibility (matches v3.x behavior)
python scripts/run_search.py --scenario all --population-size 100000 --n-generations 150 --mode softmag
```

---

## v3.0 — NEMAD-Calibrated Synthetic Formula

**Released**: 2026-05-02  
**Tag**: v3.0  
**Commits**: 0be59ce (formula), 24824b0 (GA validation)

### Summary

This release addresses the systematic underestimation of Tc revealed by NEMAD validation in v2.0. Through residual analysis on 618 real magnetic alloys, we identified three over-strong terms in the physics-inspired formula and added a Slater-Pauling Fe-Co synergy term.

### Key Changes

| Parameter | v2.0 | v3.0 | Justification |
|---|---|---|---|
| Cr suppression coef | 5500 | 1800 | NEMAD Cr=20% bin showed actual ~300K vs predicted 850K |
| Mn suppression coef | 4500 | 1200 | Same analysis showed Mn=20% bin actual ~200K |
| Dilution coef | 0.5 | 0.20 | Si+Al >15% bin showed +260K systematic underestimation |
| Fe-Co synergy | (none) | 80K × 4×Fe×Co/mag² | Slater-Pauling peak at Fe:Co=50:50 |

### Validation Results

#### Formula validation (NEMAD 618 alloys, formula-only)
- MAE: 758K → 322K (−57%)
- Hiperco50 residual: −82°C → −2°C (Fe-Co synergy verified)
- Permalloy residual: +3°C → +3°C (base preserved)
- Three target Curie zones MAE roughly halved

#### Surrogate model validation (NEMAD sim-to-real)
- Overall R²: −0.24 → +0.09 (crossed positive threshold)
- Overall MAE: 282°C → 239°C
- Hiperco50 ML prediction error: −77°C → −1°C
- Permalloy ML prediction stable at +3°C

#### GA behavioral validation
- 150°C scenario: Cr usage 4% → 10% (formula change propagated correctly)
- 500°C scenario: Co requirement 36% → 31% (synergy reduces Co need)
- All three scenarios: Tc accuracy < 1%
- Fitness improvement: +0.005 average

### Recommended Formulas (v3.0)

| Scenario | Target Tc | Formula (at%) | Pred Tc | Fitness |
|----------|-----------|---------------|---------|---------|
| Low-temp waste-heat | 150°C | Fe₂₀Ni₂₄Co₁₆Cr₁₀Si₁₉V₇Mn₃Mo₁ | 149.9°C | 0.8048 |
| Mid-temp waste-heat | 350°C | Fe₂₄Ni₂₇Co₁₉Si₂₀V₆Cr₃Mn₁ | 350.1°C | 0.8012 |
| High-temp waste-heat | 500°C | Fe₂₁Ni₂₅Co₃₁V₂₀Mo₂Cr₁ | 498.5°C | 0.7926 |

### Known Limitations (carried forward to future work)

1. **Sendust residual −115°C**: Si and Al are treated identically in dilution term, but their electronic effects differ. Future work: separate Si/Al treatment.

2. **Alnico5 residual −167°C**: Alnico has α'/α phase separation creating nanostructure that single-phase formula cannot capture. Considered fundamental limitation for solid-solution model.

3. **Invar +400°C**: Slater-Pauling dip at Fe-Ni 35:65 region not encoded. Future work: add magneto-volume effect term.

4. **Search bias toward 5+ element alloys**: Poisson(λ=4) training distribution biases GA away from 2–3 element solutions like pure Permalloy/Hiperco.

### Reproducibility

```bash
# Retrain surrogate with v3.0 formula
python scripts/train_surrogate.py --n-samples 8000 --epochs 300 --seed 42

# Run GA search (all three scenarios)
python scripts/run_search.py --scenario all --population-size 100000 --n-generations 150

# Validate formula against NEMAD (no retraining)
python scripts/validate_formula_v2.py

# Analyze formula bias on NEMAD
python scripts/analyze_formula_bias.py
```

All results deterministic at seed=42.

---

## v2.0 — Sparse Dirichlet + Tc Leakage Fix

**Released**: 2026-05-02  
**Tag**: v2.0  
**Commit**: 3d1dc38

### Summary

Two structural bugs caused catastrophic predictions (~10⁹ °C) on real binary/ternary alloys. Both are fixed in this release.

### Bug Fixes

**Bug 1 — Tc data leakage**: `PROP_NAMES` included `"Tc"` (pure-element Curie temperatures). Only Fe/Co/Ni have Tc > 0; the `max_element_Tc` feature directly encoded magnetic element identity, letting the model fit Tc trivially. Fixed by removing `"Tc"` from `PROP_NAMES` (40 → 36 feature dims).

**Bug 2 — Full-Dirichlet distribution shift**: With all 10 elements always active, `min_X` statistics were nearly constant across training samples (std ≈ 0, clipped to 1e-6). At inference on real binary/ternary alloys, normalized features reached z ~ 10⁸–10¹¹. Fixed by switching to sparse Dirichlet sampling (Poisson λ=4, 2–8 active elements per sample).

### Before / After

| Metric | v1.0 | v2.0 |
|--------|------|------|
| Permalloy prediction | ~10⁹ °C | 437°C (exp: 434°C) |
| NEMAD overall R² | −1.5 × 10¹³ | −0.24 |
| NEMAD MAE | ~8.6 × 10⁸ °C | 282°C |
| Permalloy max z-score | +6.3 × 10⁸σ | +1.70σ |

### Reproducibility

```bash
python scripts/train_surrogate.py --n-samples 8000 --epochs 300 --seed 42
python scripts/run_search.py --scenario all --population-size 100000 --n-generations 150
```
