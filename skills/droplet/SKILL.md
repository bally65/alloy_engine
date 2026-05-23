---
name: droplet
description: 液滴動力學分析工具。計算 Weber 數、Ohnesorge 數、液滴破碎模式（完整/拉伸/劇烈霧化），以及壓力噴嘴的 Sauter 平均直徑（SMD），評估清潔噴霧的霧化品質。
---

# Droplet — 液滴動力學分析

## Overview

清潔噴霧的液滴大小直接影響清潔效果：液滴太大穿透力強但覆蓋不均；液滴太小飄散損失大。
Weber 數與 Ohnesorge 數描述慣性力、黏性力、表面張力的相對強弱，決定液滴破碎行為。

**核心能力**：
- Weber 數 We = ρv²d/γ（慣性力 vs 表面張力）
- Ohnesorge 數 Oh = μ/√(ρdγ)（黏性力 vs 表面張力/慣性力）
- 破碎模式判斷：intact / stretching_breakup / catastrophic_breakup
- 壓力噴嘴 Sauter 平均直徑（SMD）估算

## Core Capabilities

### 1. Weber 數與破碎模式

```python
python scripts/droplet_analysis.py \
  --velocity 10 --diameter 0.2 --density 998 --tension 72.8
```

```python
from fluidsim_skills.droplet import weber_number, ohnesorge_number, droplet_regime

We = weber_number(velocity=10.0, diameter_m=0.0002, density=998.2,
                  surface_tension_Nm=0.0728)
Oh = ohnesorge_number(diameter_m=0.0002, density=998.2,
                      dynamic_viscosity=1.002e-3, surface_tension_Nm=0.0728)
regime = droplet_regime(We, Oh)
print(f"We={We:.1f}, Oh={Oh:.4f}, 模式={regime}")
```

### 2. 完整液滴分析報告

```python
from fluidsim_skills.droplet import analyse_droplet

result = analyse_droplet(velocity=10.0, diameter_mm=0.2)
print(f"破碎模式: {result.regime_description}")
print(f"臨界流速: {result.critical_velocity:.2f} m/s")
```

### 3. 噴嘴 SMD 估算

```python
python scripts/spray_smd.py --pressure 3.0 --orifice 2.0 --tension 30
```

```python
from fluidsim_skills.droplet import spray_droplet_size

smd = spray_droplet_size(pressure_bar=3.0, orifice_diameter_mm=2.0,
                         surface_tension_mN=30.0)
print(f"SMD: {smd:.1f} μm")
```

## Quick Reference

| 操作 | 指令 |
|------|------|
| 液滴分析 | `python scripts/droplet_analysis.py --velocity 10 --diameter 0.2` |
| SMD 估算 | `python scripts/spray_smd.py --pressure 3.0 --orifice 2.0` |
| We < 12 | 液滴完整，保持球形 |
| 12 ≤ We < 100 | 袋式破碎，形成細霧 |
| We ≥ 100 | 劇烈霧化，微細液滴 |
| 清潔噴嘴目標 SMD | 100–400 μm（翅片縫隙穿透） |
| Oh < 0.1 | 水性液體典型值（表面張力主導）|
