---
name: fluid
description: 基礎流體力學計算工具。用於管道流量分析、雷諾數計算、流態判斷（層流/紊流）、流速剖面、連續方程式應用。是 pressure、hvac、cleaning 等 skill 的基礎計算層。
---

# Fluid — 流體力學核心計算

## Overview

提供工業流體系統設計所需的基礎流體力學計算，涵蓋管道流動分析、流態判斷與流量計算。所有計算基於 SI 單位制，壓力單位為 Pa，流量為 m³/s，長度為 m。

**核心能力**：
- 雷諾數計算與流態判斷
- 圓管流速分布（Hagen-Poiseuille / 紊流對數律）
- 流量與流速互換
- 流體性質查詢（密度、黏度）

## Core Capabilities

### 1. 雷諾數與流態判斷

```python
python scripts/reynolds.py --diameter 0.025 --velocity 2.5 --fluid water
```

```python
from fluidsim_skills.fluid import reynolds_number, flow_regime

Re = reynolds_number(diameter=0.025, velocity=2.5, kinematic_viscosity=1e-6)
regime = flow_regime(Re)
# regime: "laminar" | "transitional" | "turbulent"
print(f"Re = {Re:.0f}, 流態: {regime}")
```

### 2. 流量與流速換算

```python
from fluidsim_skills.fluid import velocity_to_flowrate, flowrate_to_velocity

# 流速 → 流量
Q = velocity_to_flowrate(velocity=2.5, diameter=0.025)  # m³/s
Q_lpm = Q * 1000 * 60  # 換算為 L/min

# 流量 → 流速
v = flowrate_to_velocity(flowrate_lpm=15.0, diameter=0.025)
```

### 3. 流體性質（水）

```python
from fluidsim_skills.fluid import water_properties

props = water_properties(temperature_C=25)
# props.density        → kg/m³
# props.dynamic_viscosity  → Pa·s
# props.kinematic_viscosity → m²/s
```

### 4. 完整管道流動分析

```python
python scripts/pipe_flow.py --diameter 0.025 --length 10 --flowrate 15 --fluid water --temp 25
```

輸出：
- 雷諾數與流態
- 平均流速
- 流速剖面圖（PNG）

## Common Use Cases

### 冷氣清潔用水管路流態確認

```python
from fluidsim_skills.fluid import reynolds_number, flow_regime, water_properties

# 清潔用 1/4" 水管，流量 8 L/min
diameter = 0.00635  # 6.35mm (1/4")
flowrate_m3s = 8 / 1000 / 60
area = 3.14159 * (diameter/2)**2
velocity = flowrate_m3s / area

props = water_properties(temperature_C=20)
Re = reynolds_number(diameter, velocity, props.kinematic_viscosity)
print(f"流速: {velocity:.2f} m/s, Re: {Re:.0f}, 流態: {flow_regime(Re)}")
```

## Quick Reference

| 操作 | 指令 |
|------|------|
| 雷諾數計算 | `python scripts/reynolds.py --diameter D --velocity V` |
| 管道流動分析 | `python scripts/pipe_flow.py --diameter D --flowrate Q` |
| 流態判斷臨界值 | Re < 2300 層流，2300–4000 過渡，> 4000 紊流 |
| 水在 20°C 運動黏度 | 1.004 × 10⁻⁶ m²/s |
| 水在 20°C 密度 | 998.2 kg/m³ |

## Resources

- `references/fluid-properties.md` — 常見流體物理性質表
- `references/flow-regimes.md` — 流態判斷與紊流模型說明
- `references/pipe-flow-theory.md` — Hagen-Poiseuille 與紊流管流理論
