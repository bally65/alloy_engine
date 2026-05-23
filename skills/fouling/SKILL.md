---
name: fouling
description: 積垢動力學與清潔週期計算工具。基於 Kern-Seaton 積垢模型預測冷氣蒸發器熱傳效率隨時間的衰退，計算建議清潔週期，並提供 TEMA 標準積垢熱阻資料庫。
---

# Fouling — 積垢動力學與清潔週期

## Overview

冷氣蒸發器積垢會逐漸降低熱傳效率，增加耗電量並縮短壽命。
Kern-Seaton 模型描述積垢熱阻隨運行時間的漸近增長，可定量預測清潔週期。

**核心能力**：
- Kern-Seaton 積垢模型：Rf(t) = Rf*(1 − e^{−Kf·t})
- 熱傳效率損失計算
- 建議清潔週期計算（設定效率損失門檻）
- TEMA 標準積垢熱阻資料庫（6 種典型環境）

## Core Capabilities

### 1. 積垢熱阻計算

```python
from fluidsim_skills.fouling import kern_seaton_fouling

# 冷氣室內機，運行 2000 小時
Rf = kern_seaton_fouling(time_h=2000, asymptotic_resistance=1.76e-4,
                          fouling_rate_constant=8.0e-4)
print(f"積垢熱阻: {Rf:.2e} m²·K/W")
```

### 2. 完整積垢分析報告

```python
python scripts/fouling_growth.py \
  --time 2000 --environment ac_indoor_unit --U-clean 50
```

```python
from fluidsim_skills.fouling import analyse_fouling

report = analyse_fouling(elapsed_hours=2000, environment='ac_indoor_unit')
print(f"效率損失: {report.efficiency_penalty_pct:.1f}%")
print(f"建議: {report.recommendation}")
```

### 3. 清潔週期計算

```python
python scripts/cleaning_schedule.py \
  --environment ac_indoor_unit --U-clean 50 --target-loss 10
```

```python
from fluidsim_skills.fouling import cleaning_interval, FOULING_RESISTANCE_DB

db = FOULING_RESISTANCE_DB['ac_indoor_unit']
t = cleaning_interval(U_clean=50, asymptotic_Rf=db['Rf_star'],
                      fouling_rate_constant=db['Kf'], target_efficiency_loss_pct=10)
print(f"建議每 {t:.0f} 小時（約 {t/8760:.1f} 年）清潔一次")
```

## Quick Reference

| 操作 | 指令 |
|------|------|
| 積垢分析報告 | `python scripts/fouling_growth.py --time 2000 --environment ac_indoor_unit` |
| 清潔週期計算 | `python scripts/cleaning_schedule.py --environment ac_indoor_unit` |
| 環境類型 | ac_indoor_unit, ac_outdoor_unit, city_water, coastal_air, industrial_air, kitchen_exhaust |
| 效率損失門檻 | 建議 10%（超過開始感受到冷效下降） |
| 典型家用冷氣清潔週期 | 每 1–2 年（室內機）|
| 廚房環境 | 積垢快 3 倍，建議每半年清潔 |

## TEMA 積垢熱阻資料庫

| 環境 | Rf* (m²·K/W) | Kf (1/h) |
|------|-------------|----------|
| ac_indoor_unit | 1.76×10⁻⁴ | 8.0×10⁻⁴ |
| ac_outdoor_unit | 3.52×10⁻⁴ | 5.0×10⁻⁴ |
| city_water | 1.76×10⁻⁴ | 2.0×10⁻³ |
| coastal_air | 5.28×10⁻⁴ | 6.0×10⁻⁴ |
| industrial_air | 8.80×10⁻⁴ | 4.0×10⁻⁴ |
| kitchen_exhaust | 1.76×10⁻³ | 3.0×10⁻³ |
