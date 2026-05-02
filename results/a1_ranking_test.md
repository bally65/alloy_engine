# A1-2: Hc / Br / σy Indirect Validation — Ranking Test

**Date:** 2026-05-02  
**Method:** Spearman rank correlation against literature values for 10 famous alloys (9 soft + 1 hard magnetic)  
**Why ranking, not R²:** NEMAD local repo contains only Tc/Neel temperature — no experimental Hc/Br/σy records.

**Literature sources:** Bozorth (1951), Cullity & Graham (2009), Carpenter Technology datasheets, Magnetics Inc. datasheets, NEMA datasheet, IEEE Magnetics Society reference data.

---

## 1. Full Prediction Table

### Hc (Coercivity, A/m)

| Alloy | Type | Lit Hc (A/m) | Pred Hc (A/m) | Ratio pred/lit |
|-------|------|-------------|--------------|----------------|
| Supermalloy | soft | 0.16 | 199 | 1244× |
| Mu-Metal | soft | 0.20 | 207 | 1037× |
| Permalloy | soft | 0.40 | 196 | 489× |
| Sendust | soft | 5 | 252 | 50× |
| Silicon Steel | soft | 40 | 298 | 7× |
| Pure Ni | soft | 60 | 295 | 5× |
| Pure Fe | soft | 80 | 299 | 4× |
| Hiperco50 | soft | 80 | 173 | 2× |
| Permendur | soft | 160 | 183 | 1.1× |
| **Alnico5** | **hard** | **51,000** | **143** | **0.003×** |

### Br (Remanence / saturation, T)

| Alloy | Type | Lit Br (T) | Pred Br (T) | Abs error |
|-------|------|-----------|------------|-----------|
| Mu-Metal | soft | 0.60 | 0.31 | −0.29 |
| Pure Ni | soft | 0.60 | 0.24 | −0.37 |
| Supermalloy | soft | 0.70 | 0.34 | −0.36 |
| Permalloy | soft | 0.70 | 0.37 | −0.33 |
| Sendust | soft | 1.00 | 0.77 | −0.23 |
| Alnico5 | hard | 1.25 | 0.66 | −0.59 |
| Pure Fe | soft | 1.40 | 0.88 | −0.52 |
| Silicon Steel | soft | 2.00 | 0.86 | −1.14 |
| Permendur | soft | 2.40 | 0.82 | −1.58 |
| Hiperco50 | soft | 2.40 | 0.81 | −1.59 |

### σy (Yield Strength, MPa — annealed state)

| Alloy | Lit σy (MPa) | Pred σy (MPa) | Abs error |
|-------|-------------|--------------|-----------|
| Pure Fe | 130 | 344 | +214 |
| Pure Ni | 140 | 249 | +109 |
| Permalloy | 220 | 270 | +50 |
| Mu-Metal | 240 | 299 | +59 |
| Supermalloy | 290 | 320 | +30 |
| Silicon Steel | 310 | 365 | +55 |
| Alnico5 | 380 | 332 | −48 |
| Sendust | 350 | 407 | +57 |
| Hiperco50 | 420 | 306 | −114 |
| Permendur | 470 | 320 | −150 |

---

## 2. Spearman Rank Correlations

| Property | Full r (n=10) | Full p | Soft-only r (n=9) | Soft-only p | Pass? |
|----------|--------------|--------|-------------------|------------|-------|
| **Hc** | **−0.310** | 0.383 | **−0.050** | 0.898 | ❌ |
| **Br** | **+0.869** | 0.001 | **+0.836** | 0.005 | ✅ |
| **σy** | **+0.261** | 0.467 | N/A | N/A | ❌ (weak) |

---

## 3. Hard vs Soft Magnetic Separation Test

| Metric | Value | Expected | Pass? |
|--------|-------|----------|-------|
| Soft-mag mean pred Hc | 233 A/m | — | — |
| Alnico5 pred Hc | 143 A/m | >> 233 A/m | ❌ |
| Hard/soft Hc ratio | **0.6×** | 100–1000× | ❌ |
| Alnico5 rank by pred Hc | **10/10 (lowest)** | 1/10 (highest) | ❌ (inverted) |
| Alnico5 rank by lit Hc | 1/10 (highest) | — | — |

**The model predicts Alnico5 as the softest material — the exact opposite of reality.** This is physically expected: our synthetic Hc formula is based on Fe-Ni balance and microstructural softness assumptions; it has no concept of magneto-crystalline anisotropy or exchange-coupled α'/α microstructure that gives Alnico its hardness.

---

## 4. MC Dropout Uncertainty (Hc)

| Alloy | Hc_mean (A/m) | Hc_std | Lit Hc | Abs err | std/err | Assessment |
|-------|--------------|--------|--------|---------|---------|------------|
| Supermalloy | 201 | 9.2 | 0.16 | 201 | 0.046 | Over-confident |
| Mu-Metal | 205 | 7.6 | 0.20 | 204 | 0.037 | Over-confident |
| Permalloy | 196 | 8.5 | 0.40 | 196 | 0.044 | Over-confident |
| Sendust | 252 | 12.2 | 5.0 | 247 | 0.049 | Over-confident |
| Silicon Steel | 298 | 18.4 | 40 | 258 | 0.071 | Over-confident |
| Pure Ni | 299 | 18.6 | 60 | 239 | 0.078 | Over-confident |
| Pure Fe | 294 | 20.9 | 80 | 214 | 0.098 | Over-confident |
| Hiperco50 | 175 | 12.5 | 80 | 95 | 0.132 | — |
| Permendur | 183 | 12.1 | 160 | 23 | 0.536 | Reasonable |
| Alnico5 | 144 | 6.9 | 51,000 | 50,856 | 0.000 | Maximally over-confident |

All alloys are over-confident: std/|error| << 1 for every sample. This is the same systematic under-calibration identified in A3-4.

---

## 5. Interpretation

### Br: **Strong result (r = +0.836, p = 0.005)**

The Br ordering is physically correct:
- Low-Fe Ni-based alloys (Permalloy, Mu-Metal, Supermalloy, Pure Ni) correctly predicted as low-Br
- Fe-rich (Pure Fe, Si-Steel) correctly ranked above mid-range
- The systematic under-prediction (~0.3–1.6 T below literature) reflects that our synthetic formula uses `Br = mag_moment × 0.4 × noise` — the `0.4` saturation coefficient needs calibration, but the *ordering* is captured by the magnetic moment calculation.

### Hc: **Failed (soft-only r = −0.050, essentially zero)**

Root cause: the synthetic Hc formula (`base_hc = 50 + 250|Fe−Ni| - 30·Si + 100·(Cu+Mo)`) treats coercivity purely as a microstructural softness proxy based on Fe-Ni balance. This captures almost nothing of what physically determines Hc:

- **Not captured:** magneto-crystalline anisotropy (K₁), domain wall pinning density, grain size, texture, magnetostriction
- **Consequence:** all 10 predictions cluster in the range 143–299 A/m, while literature spans 0.16–51,000 A/m (6 orders of magnitude)
- Permendur (lit 160 A/m) is predicted closest to literature only by coincidence

### σy: **Weak (r = +0.261, not significant)**

The solid-solution strengthening formula captures the right direction for some elements (Cr, Mo, Si, Al, V all increase σy) but:
- Pure Fe and Ni are systematically over-predicted (model has no concept of single-element annealed state)
- Heat treatment state is unspecified in our model; literature values are for annealed condition

---

## 6. Known Limitations

1. **n = 10** — Spearman correlation with n=10 has high variance; results should be considered indicative only.
2. **σy literature values are annealed state** — our model has no heat treatment parameter; predictions may reflect a generic solid-solution estimate, not annealed microstructure.
3. **Br literature values ≈ saturation magnetization (Ms)** — for soft magnetics, Br ≈ Ms is a reasonable approximation, but the exact equivalence depends on squareness ratio.
4. **Alnico5 is fundamentally outside model scope** — α'/α phase-separated permanent magnet; single-phase composition-only model cannot predict its coercivity.
5. **Hc is a microstructure-dependent property** — composition-only models are inherently limited for Hc prediction. A physically valid Hc model requires grain size, texture, and processing history inputs.

---

## 7. Summary Verdict

| Property | Ranking ability | Absolute accuracy | Suitable for use? |
|----------|----------------|-------------------|-------------------|
| Tc | Moderate (NEMAD R²=+0.09) | ±240°C MAE | Yes, with caveats |
| **Br** | **Strong (r=+0.836)** | Systematic −0.3 to −1.6 T | **Yes for relative ranking** |
| Hc | Absent (r=−0.050) | Orders of magnitude off | **No — composition-only insufficient** |
| σy | Weak (r=+0.261) | ±50–200 MPa | Relative guidance only |

**Recommendation:** Br predictions can be used for relative ranking with confidence. Hc predictions should be treated as a qualitative low-Hc optimization signal only — the ordering is unreliable and absolute values are meaningless for soft magnetic alloy screening. σy is marginally useful for screening out very-low-strength compositions.
