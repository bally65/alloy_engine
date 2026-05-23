---
name: chem_cleaning
description: 冷氣翅片化學清潔設計工具。輸入污垢類型（灰塵/油污/水垢/生物膜）與翅片材質，使用 Noyes-Whitney 溶解動力學計算清潔效果，並分析表面張力、接觸角、剪切力，自動推薦清潔劑種類、濃度與接觸時間。搭配 $cleaning skill 輸出化學+物理整合清潔方案。
---

# Chem Cleaning — 化學清潔動力學設計

## Overview

基於 **Noyes-Whitney 溶解方程式**的冷氣翅片化學清潔設計工具。
計算清潔劑在翅片污垢上的溶解速率，並結合**表面張力**與**剪切力**分析，
推薦最有效的清潔劑、濃度與接觸時間。

**核心物理/化學模型**：
- Noyes-Whitney 方程式：溶解速率 `dC/dt = (D·A/h·V)·(Cs - C)`
- 表面張力（CMC 效應、Gibbs 吸附）
- 接觸角（Young 方程式）
- 翅片縫隙剪切應力（Couette 流近似）

## Core Capabilities

### 1. 溶解動力學計算

```python
python scripts/dissolution_calc.py \
  --contamination grease_light \
  --cleaner alkaline_mild \
  --conc 2.0 --time 10
```

```python
from fluidsim_skills.chemistry import noyes_whitney_dissolution

result = noyes_whitney_dissolution(
    contamination_key='grease_light',
    contact_time_min=10,
    cleaner_key='alkaline_mild',
    concentration_pct=2.0,
    temperature_C=25,
)
print(f"溶解分率: {result.dissolved_fraction*100:.1f}%")
print(f"有效清潔: {result.effective}")
```

### 2. 表面力學分析

```python
from fluidsim_skills.chemistry import surface_forces

forces = surface_forces(
    cleaner_key='surfactant_neutral',
    concentration_pct=1.5,
    shear_velocity=1.5,    # m/s，清潔水流速
    fin_spacing_mm=1.2,
)
print(f"表面張力: {forces.surface_tension_mN:.1f} mN/m")
print(f"接觸角: {forces.contact_angle_deg:.1f}°")
print(f"剪切應力: {forces.shear_stress_Pa:.1f} Pa")
```

### 3. 自動清潔劑推薦

```python
python scripts/recommend_cleaner.py \
  --contamination grease_heavy \
  --fin-material aluminum \
  --target 0.85
```

```python
from fluidsim_skills.chemistry import recommend_cleaner

report = recommend_cleaner(
    contamination_key='grease_heavy',
    fin_material='aluminum',
    target_effectiveness=0.85,
)
print(f"推薦: {report.recommended_cleaner}")
print(f"濃度: {report.concentration_pct:.1f}%，接觸 {report.contact_time_min:.0f} 分鐘")
```

### 4. 化學+物理整合報告

```python
python scripts/full_chem_report.py \
  --equipment "日立 RAS-28NK" \
  --contamination grease_light \
  --supply 3.0 \
  --width 750 --height 200 \
  --output 完整清潔方案.md
```

## 污垢類型對照表

| Key | 中文名稱 | 適用清潔劑 |
|-----|---------|----------|
| `dust_general` | 一般灰塵 | 中性界面活性劑、弱鹼 |
| `grease_light` | 輕度油污 | 弱鹼性清潔劑 |
| `grease_heavy` | 重度油污/廚房油垢 | 強鹼清潔劑 |
| `biofilm` | 生物膜/黴菌 | 消毒除菌劑 |
| `mineral_scale` | 水垢/礦物質沉積 | 弱酸性除垢劑 |

## 清潔劑類型對照表

| Key | 名稱 | pH | 鋁翅片安全 |
|-----|------|----|---------|
| `alkaline_mild` | 弱鹼性清潔劑 | 9.5 | ✓ |
| `alkaline_strong` | 強鹼清潔劑 | 12.5 | ✗ 會腐蝕 |
| `surfactant_neutral` | 中性界面活性劑 | 7.0 | ✓ |
| `acid_mild` | 弱酸性除垢劑 | 4.0 | ✓ |
| `disinfectant` | 消毒除菌劑 | 7.5 | ✓ |

## Quick Reference

| 操作 | 指令 |
|------|------|
| 溶解動力學計算 | `python scripts/dissolution_calc.py --contamination X --cleaner Y --conc C --time T` |
| 自動推薦清潔劑 | `python scripts/recommend_cleaner.py --contamination X --fin-material aluminum` |
| 完整整合報告 | `python scripts/full_chem_report.py --contamination X --supply P --width W --height H` |

## Resources

- `references/noyes-whitney.md` — 溶解方程式推導與參數說明
- `references/surfactant-theory.md` — 界面活性劑表面張力理論
- `references/contamination-types.md` — 各類污垢物理化學性質
- `references/cleaner-database.md` — 清潔劑成分與特性資料庫
- `references/material-compatibility.md` — 清潔劑與金屬材質相容性
