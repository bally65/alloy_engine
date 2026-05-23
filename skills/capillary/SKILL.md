---
name: capillary
description: 毛細滲透計算工具。分析清潔液在冷氣翅片縫隙（1.2–2.5 mm）的毛細壓力、Lucas-Washburn 滲透深度與滲透時間，評估清潔液自發滲入翅片的能力。
---

# Capillary — 毛細滲透計算

## Overview

翅片間距僅 1.2–2.5 mm，清潔液能否自發滲入是清潔效果的關鍵物理機制。
本模組基於 Laplace-Young 方程與 Lucas-Washburn 動力學，量化毛細壓力與滲透速度。

**核心能力**：
- Laplace-Young 毛細壓力計算（Pc = 2γ·cos(θ)/r）
- Lucas-Washburn 橫向滲透深度（x(t) = √(r·γ·cos(θ)/(2μ)·t)）
- 翅片縫隙完整滲透分析報告（含與純水對比）

## Core Capabilities

### 1. 毛細壓力計算

```python
from fluidsim_skills.capillary import capillary_pressure

# 30 mN/m 清潔液，接觸角 25°，翅片間距 2.0 mm（半徑 1.0 mm）
Pc = capillary_pressure(surface_tension_mN=30.0, contact_angle_deg=25.0,
                        channel_half_width_mm=1.0)
print(f"毛細壓力: {Pc:.1f} Pa")
```

### 2. Lucas-Washburn 滲透深度

```python
from fluidsim_skills.capillary import lucas_washburn_penetration

x = lucas_washburn_penetration(
    surface_tension_mN=30.0, contact_angle_deg=25.0,
    channel_half_width_mm=1.0, dynamic_viscosity=1.0e-3, time_s=30.0
)
print(f"30 秒後滲透深度: {x:.1f} mm")
```

### 3. 翅片完整分析報告

```python
python scripts/fin_penetration.py \
  --spacing 2.0 --height 15 --tension 30 --angle 25 --viscosity 0.001
```

```python
from fluidsim_skills.capillary import analyse_fin_penetration

report = analyse_fin_penetration(
    fin_spacing_mm=2.0, fin_height_mm=15.0,
    surface_tension_mN=30.0, contact_angle_deg=25.0,
    dynamic_viscosity=1.0e-3, cleaner_name='弱鹼清潔液'
)
print(report.recommendation)
print(f"滲透至底部需 {report.time_to_full_penetration_s:.1f} 秒")
print(f"對比純水：{report.vs_water}")
```

## Quick Reference

| 操作 | 指令 |
|------|------|
| 毛細壓力 | `python scripts/capillary_pressure.py --tension 30 --angle 25 --spacing 1.0` |
| 翅片滲透報告 | `python scripts/fin_penetration.py --spacing 2.0 --height 15 --tension 30` |
| θ < 90° | 毛細力促進滲入（親水面） |
| θ > 90° | 毛細力阻礙滲入（疏水面） |
| 典型鋁翅片接觸角 | 40–70°（清潔液）、60–80°（純水） |
| Lucas-Washburn 適用條件 | 水平方向滲透（重力忽略）|

## 參考文獻

| # | 文獻 |
|---|------|
| [1] | Young, T. (1805). "An essay on the cohesion of fluids." *Phil. Trans. R. Soc. London*, 95, 65–87. (Young-Laplace 方程) |
| [2] | Laplace, P.S. (1805). *Traité de Mécanique Céleste*, Supplement. |
| [3] | Lucas, R. (1918). "Ueber das Zeitgesetz des kapillaren Aufstiegs von Flüssigkeiten." *Kolloid-Zeitschrift*, 23(1), 15–22. |
| [4] | Washburn, E.W. (1921). "The dynamics of capillary flow." *Physical Review*, 17(3), 273–283. |
| [5] | Adamson, A.W. & Gast, A.P. (1997). *Physical Chemistry of Surfaces*, 6th ed. Wiley. Chapter 10. |
