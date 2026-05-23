---
name: thermal
description: 翅片熱效率計算工具。計算冷氣蒸發器翅片效率 η、Dittus-Boelter 對流換熱係數，並整合 alloy_engine κ（熱傳導率）預測結果評估不同合金翅片的熱性能。
---

# Thermal — 翅片熱效率計算

## Overview

翅片效率 η 決定翅片面積的有效利用率。η 越高，相同翅片面積提供越好的熱交換性能。
本模組提供標準矩形直翅片效率計算，並可直接接受 alloy_engine 輸出的 κ 值進行評估。

**核心能力**：
- 矩形直翅片效率 η = tanh(mL)/(mL)，m = √(2h/k·t)
- Dittus-Boelter 強制對流換熱係數（管內）
- alloy_engine κ 整合介面：直接輸入合金熱傳導率→翅片效率報告

## Core Capabilities

### 1. 翅片效率計算

```python
from fluidsim_skills.thermal import fin_efficiency

# 鋁翅片：高 15 mm，厚 0.1 mm，κ=205 W/m·K，h=30 W/m²·K
eta = fin_efficiency(
    fin_height_m=0.015, fin_thickness_m=0.0001,
    thermal_conductivity=205.0, h_conv=30.0
)
print(f"翅片效率: {eta:.1%}")
```

### 2. alloy_engine κ 整合

```python
python scripts/fin_efficiency.py \
  --height 15 --thickness 0.1 --kappa 220 --h-conv 30
```

```python
from fluidsim_skills.thermal import fin_efficiency_from_kappa

# 直接接受 alloy_engine 預測的 κ 值
report = fin_efficiency_from_kappa(
    fin_height_mm=15.0, fin_thickness_mm=0.1,
    kappa_W_mK=220.0, h_conv=30.0
)
print(f"翅片效率: {report.fin_efficiency:.1%}")
print(f"vs 標準鋁: {report.heat_transfer_improvement}")
```

### 3. Dittus-Boelter 對流係數

```python
python scripts/fouling_htc.py --velocity 1.5 --diameter 9.5 --temp 25
```

```python
from fluidsim_skills.thermal import dittus_boelter_h

h = dittus_boelter_h(velocity=1.5, diameter=0.0095, temperature_C=25)
print(f"對流係數: {h:.1f} W/m²·K")
```

## Quick Reference

| 操作 | 指令 |
|------|------|
| 翅片效率（輸入 κ）| `python scripts/fin_efficiency.py --height 15 --thickness 0.1 --kappa 205` |
| 對流係數 | `python scripts/fouling_htc.py --velocity 1.5 --diameter 9.5 --temp 25` |
| 典型鋁翅片 κ | 200–215 W/m·K |
| 典型銅翅片 κ | 385–400 W/m·K |
| 典型對流係數 h | 25–50 W/m²·K（空氣側自然對流） |
| η > 0.95 | 翅片設計良好，熱阻主要來自對流側 |
| η < 0.7 | 建議增加翅片厚度或改用高 κ 合金 |

## alloy_engine 整合說明

alloy_engine 輸出的熱傳導率 κ（單位 W/m·K）可直接傳入 `fin_efficiency_from_kappa()`：

```python
# alloy_engine 預測結果
predicted_kappa = alloy_engine.predict_kappa(composition)

# 評估此合金作為翅片材料的性能
report = fin_efficiency_from_kappa(
    fin_height_mm=15, fin_thickness_mm=0.1,
    kappa_W_mK=predicted_kappa
)
```
