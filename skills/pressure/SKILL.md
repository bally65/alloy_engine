---
name: pressure
description: 管路壓力系統設計工具。用於計算管道壓力損失、閥門選型、噴嘴前可用壓力、管路配件局部損失。適用於冷氣清潔、工業管路、高壓水洗系統設計。依賴 $fluid skill 的流體性質計算。
---

# Pressure — 壓力系統計算

## Overview

基於 Darcy-Weisbach 方程式的管路壓力損失計算工具，涵蓋直管摩擦損失與管路配件局部損失。
提供從水源壓力推算噴嘴前實際可用壓力的完整計算流程。

**支援管材**：鋼管、銅管、PVC、不鏽鋼管（不同粗糙度）

## Core Capabilities

### 1. 直管壓力損失（Darcy-Weisbach）

```python
python scripts/pressure_drop.py --diameter 9.5 --length 5 --flowrate 10 --temp 20
```

```python
from fluidsim_skills.pressure import pressure_drop

result = pressure_drop(
    diameter=0.0095,      # 9.5mm 管道（3/8"）
    length=5.0,           # 5 公尺
    flowrate_lpm=10.0,    # 10 L/min
    temperature_C=20.0,
    roughness_m=1.5e-5,   # 鋼管
)
print(f"壓損: {result.total_loss_bar:.3f} bar")
print(f"摩擦係數: {result.friction_factor:.4f}")
print(f"流速: {result.velocity:.2f} m/s, Re={result.reynolds:.0f}")
```

### 2. 含管路配件的總壓損

```python
from fluidsim_skills.pressure import pressure_drop, FITTING_K_VALUES

# 管路含 2 個 90° 彎頭 + 1 個截止閥
K_total = (
    2 * FITTING_K_VALUES['90deg_elbow_standard'] +
    FITTING_K_VALUES['gate_valve_open']
)
result = pressure_drop(
    diameter=0.0095,
    length=3.0,
    flowrate_lpm=8.0,
    minor_loss_K=K_total,
)
```

### 3. 噴嘴前可用壓力

```python
python scripts/available_pressure.py --supply 3.5 --pipe-d 9.5 --length 5 --flowrate 8
```

```python
from fluidsim_skills.pressure import available_nozzle_pressure

nozzle_p = available_nozzle_pressure(
    supply_pressure_bar=3.5,   # 水源壓力
    pipe_diameter=0.0095,
    pipe_length=5.0,
    flowrate_lpm=8.0,
    fittings_K=2.5,            # 管路配件損失
)
print(f"噴嘴前壓力: {nozzle_p:.2f} bar")
```

## Common Use Cases

### 計算家用自來水清潔管路壓損

```python
from fluidsim_skills.pressure import pressure_drop, available_nozzle_pressure

# 家用水壓 2.5~3.5 bar，使用 3/8" 軟管 3 公尺
nozzle_p = available_nozzle_pressure(
    supply_pressure_bar=3.0,
    pipe_diameter=0.0095,   # 3/8" = 9.5mm
    pipe_length=3.0,
    flowrate_lpm=6.0,
    fittings_K=1.5,         # 1 彎頭 + 接頭
)
print(f"噴嘴可用壓力: {nozzle_p:.2f} bar")
# 通常結果 ~2.7 bar，足夠輕度清潔
```

## Quick Reference

| 操作 | 指令 |
|------|------|
| 管路壓損計算 | `python scripts/pressure_drop.py --diameter D --length L --flowrate Q` |
| 噴嘴前壓力 | `python scripts/available_pressure.py --supply P --pipe-d D --length L --flowrate Q` |
| 常見管徑換算 | 1/4"=6.35mm, 3/8"=9.5mm, 1/2"=12.7mm, 3/4"=19.05mm |
| 鋼管粗糙度 | 1.5×10⁻⁵ m |
| 銅管粗糙度 | 1.5×10⁻⁶ m |
| PVC 管粗糙度 | 1.5×10⁻⁶ m |

## Resources

- `references/darcy-weisbach.md` — 公式推導與摩擦係數計算
- `references/pipe-fittings.md` — 管路配件 K 值速查表
- `references/pipe-sizing.md` — 管徑選型建議（流速範圍）

## 參考文獻

| # | 文獻 |
|---|------|
| [1] | Weisbach, J. (1845). *Lehrbuch der Ingenieur- und Maschinen-Mechanik*. (Darcy-Weisbach 公式原始推導) |
| [2] | Darcy, H. (1857). "Recherches expérimentales relatives au mouvement de l'eau dans les tuyaux." *Mém. Acad. Sci.* |
| [3] | Moody, L.F. (1944). "Friction factors for pipe flow." *Trans. ASME*, 66(8), 671–684. |
| [4] | Colebrook, C.F. (1939). "Turbulent flow in pipes." *J. Inst. Civil Engineers*, 11(4), 133–156. |
| [5] | Idelchik, I.E. (2008). *Handbook of Hydraulic Resistance*, 4th ed. Begell House. (管件 K 值資料庫) |
