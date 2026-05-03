# Delta_M Threshold Sweep — Trade-off Table

**Scenario**: 中溫廢熱_350C (target Tc = 350°C)  
**Population**: 50,000 | **Generations**: 100  
**Element set**: Fe/Ni/Co/Cr/Mn/Cu/Mo/Si/Al/V

## Results

| Threshold | Top-1 Composition | Actual delta_M | Tc (°C) | Tc offset | Hc (A/m) | strength (MPa) | kappa (W/mK) | Cp (J/kgK) | ΔS_M (J/kgK) | f (Hz) | Fitness | Reached? |
|-----------|-------------------|---------------|---------|-----------|-----------|----------------|-------------|-----------|-------------|--------|---------|----------|
| 0.05 | Fe73.9-Co3.1-Cr13.4-Cu5.9-Si2.9 | 0.1772 T | 361.9 | +11.9 | 192 | 463 | 87.6 | 446.5 | 5.88 | 12.7 | 0.6981 | ✅ (above 0.05) |
| 0.10 | Fe76.6-Cr13.2-Cu7.6 | 0.1776 T | 360.1 | +10.1 | 209 | 466 | 91.3 | 445.0 | 5.72 | 13.4 | 0.6986 | ✅ (above 0.10) |
| 0.15 | Fe73.0-Ni3.9-Cr12.4-Cu3.5-Si3.5 | 0.1402 T | 346.6 | −3.4 | 193 | 450 | 86.3 | 445.0 | 4.65 | 12.5 | 0.6994 | ⚠️ below threshold |
| **0.20** | **Fe80.8-Cr13.9-Mn4.0** | **0.2012 T** | 365.4 | +15.4 | 235 | 470 | 82.7 | 451.0 | 6.71 | 11.9 | 0.6952 | ✅ v5.0 baseline |
| 0.25 | Fe82.0-Cr12.4-Mn4.0 | 0.2254 T | 376.1 | +26.1 | 245 | 463 | 83.5 | 450.0 | 6.94 | 12.1 | 0.5100 | ✅ |
| 0.30 | Fe83.1-Cr16.3 | 0.2318 T | 378.8 | +28.8 | 238 | 424 | 84.0 | 450.0 | 6.88 | 12.1 | 0.3605 | ✅ |
| 0.40 | Fe82.0-Cr12.2-Mn5.0 | 0.2270 T | 377.0 | +27.0 | 237 | 434 | 82.8 | 450.0 | 6.72 | 11.9 | 0.1995 | ❌ UNREACHABLE |

## Key Observations

1. **Physical ceiling**: delta_M saturates at ~**0.232 T** (achieved at thr=0.30). Beyond this, GA cannot improve further — thr=0.40 is physically unreachable.

2. **Fitness cliff**: fitness drops sharply above thr=0.20 (0.695 → 0.510 → 0.361 → 0.200), indicating a hard trade-off between delta_M and Tc accuracy / other objectives.

3. **Anomaly at thr=0.15**: GA converged to delta_M=0.140 T, **below** the threshold. This indicates the penalty at thr=0.15 was insufficient to force compliance while also satisfying other objectives — the optimization landscape has a local minimum below 0.15 T that other scores (Tc, eff) prefer.

4. **Composition evolution**: As threshold rises, Cu/Si/Ni disappear completely. Fe concentration rises from ~74% to ~83%. The solution converges to a near-binary Fe-Cr alloy, which maximizes Fe magnetic moment density at the cost of Tc precision.
