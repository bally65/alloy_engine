---
name: airflow
description: 空氣側翅片壓降與積垢風量衰退計算工具。計算乾淨與積垢翅片的空氣側壓降，量化積垢導致的風量衰退和風機功率增加，補全積垢熱阻之外的另一條效率損失路徑。
---

# Airflow — 空氣側壓降與風量衰退

## Overview

冷氣效能下降有兩條獨立路徑：
1. **熱傳路徑**（`$fouling`）：積垢增加熱阻 → 換熱效率下降
2. **氣流路徑**（本模組）：積垢縮小翅片間隙 → 風阻增加 → 風量下降 → 冷效下降

層流通道中 ΔP ∝ 1/gap³，即使積垢層只有數十 μm，也會顯著提高壓降。

**核心能力**：
- 翅片通道空氣側壓降（矩形通道 Hagen-Poiseuille + 入出口修正）
- 積垢層厚度估算（δ = Rf × k_deposit）
- 積垢後風量衰退與風機功率增加預測

## Core Capabilities

### 1. 乾淨翅片壓降

```python
from fluidsim_skills.airflow import fin_channel_pressure_drop

dp, v_max, Re = fin_channel_pressure_drop(
    face_velocity_ms=1.5,   # 面風速 m/s
    fin_pitch_mm=1.8,        # 翅片間距 mm
    fin_height_mm=25.0,      # 翅片深度（氣流方向）mm
    fin_thickness_mm=0.1,    # 翅片厚度 mm
)
print(f"壓降: {dp:.2f} Pa，Re={Re:.0f}")
```

### 2. 完整積垢風量衰退分析

```bash
python scripts/airflow_analysis.py \
  --velocity 1.5 --pitch 1.8 --height 25 --thickness 0.1 \
  --Rf 1.4e-4 --deposit dust
```

```python
from fluidsim_skills.airflow import analyse_airflow
from fluidsim_skills.fouling import kern_seaton_fouling, FOULING_RESISTANCE_DB

db = FOULING_RESISTANCE_DB['ac_indoor_unit']
Rf = kern_seaton_fouling(2000, db['Rf_star'], db['Kf'])

result = analyse_airflow(
    face_velocity_ms=1.5, fin_pitch_mm=1.8,
    fin_height_mm=25.0, fin_thickness_mm=0.1,
    Rf_current=Rf, deposit_type='dust',
)
print(f"壓降增幅: {result.pressure_increase_pct:.1f}%")
print(f"風量衰退: {result.airflow_reduction_pct:.1f}%")
print(result.recommendation)
```

### 3. 積垢層厚度估算

```python
from fluidsim_skills.airflow import fouling_layer_thickness

delta = fouling_layer_thickness(Rf=1.4e-4, deposit_type='dust')
print(f"積垢層厚度（每側）: {delta:.1f} μm")
```

## Quick Reference

| 操作 | 指令 |
|------|------|
| 壓降分析 | `python scripts/airflow_analysis.py --velocity 1.5 --pitch 1.8 --height 25` |
| 清潔效益比較 | `python scripts/cleaning_benefit.py --velocity 1.5 --pitch 1.8 --elapsed 2000` |
| 典型面風速 | 家用分離式 1.0–2.0 m/s，商用箱型機 2.0–3.5 m/s |
| 典型翅片間距 | 居家 1.5–2.5 mm，商用 2.5–4.5 mm |
| 積垢敏感度 | 層流通道：ΔP ∝ 1/gap³，間距縮 10% → 壓降增 37% |
| 整合 fouling 模組 | `Rf = kern_seaton_fouling(t, Rf_star, Kf)` → 傳入 `analyse_airflow()` |
