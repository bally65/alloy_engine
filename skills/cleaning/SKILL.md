---
name: cleaning
description: 冷氣與 HVAC 設備清潔系統設計工具。輸入冷氣型號、蒸發器尺寸、水源壓力，輸出噴嘴規格、操作壓力設定、清潔 SOP 與安全注意事項。依賴 $fluid 和 $pressure skill。
---

# Cleaning — 冷氣清潔系統設計

## Overview

針對分離式、窗型、商用冷氣的蒸發器/冷凝器翅片清潔設計工具。
從水源條件出發，計算最佳噴嘴規格、清潔操作參數，並生成完整 SOP。

**支援設備類型**：
- 分離式冷氣（室內機蒸發器）
- 窗型冷氣
- 商用箱型機
- 冷凝器（室外機）清潔

## Core Capabilities

### 1. 噴嘴流量與衝擊力計算

```python
python scripts/nozzle_calc.py --pressure 2.8 --orifice 2.0 --distance 150 --angle 25
```

```python
from fluidsim_skills.cleaning import nozzle_impact_force

result = nozzle_impact_force(
    pressure_bar=2.8,
    orifice_diameter_mm=2.0,
    distance_mm=150,
    spray_angle_deg=25,
)
print(f"流量: {result.flowrate_lpm:.2f} L/min")
print(f"衝擊力: {result.impact_force_N:.2f} N")
print(f"衝擊壓力: {result.impact_pressure_kpa:.1f} kPa")
print(f"覆蓋寬度: {result.coverage_width_mm:.0f} mm")
```

### 2. 完整清潔方案設計

```python
python scripts/design_cleaning.py --equipment "日立RAS-28NK" --width 750 --height 200 --supply 3.0
```

```python
from fluidsim_skills.cleaning import design_cleaning_system

report = design_cleaning_system(
    equipment_name="日立 RAS-28NK 3.2kW",
    evaporator_width_mm=750,
    evaporator_height_mm=200,
    supply_pressure_bar=3.0,
    pipe_diameter_mm=9.5,   # 3/8" 軟管
    pipe_length_m=3.0,
    target_distance_mm=150,
)

print(f"推薦噴嘴孔徑: {report.nozzle.orifice_diameter_mm} mm")
print(f"噴嘴前壓力: {report.nozzle_pressure_bar:.2f} bar")
print(f"估計清潔時間: {report.estimated_cleaning_time_min:.0f} 分鐘")
for step in report.procedure:
    print(step)
```

### 3. 噴嘴選型查詢

```python
python scripts/nozzle_selector.py --pressure 3.0 --flowrate-max 10 --application evaporator
```

## Common Use Cases

### 家用分離式冷氣清潔（自來水）

```python
from fluidsim_skills.cleaning import design_cleaning_system

# 台灣家用自來水約 2.5~3.5 bar
report = design_cleaning_system(
    equipment_name="一般家用分離式 1.5HP",
    evaporator_width_mm=800,
    evaporator_height_mm=180,
    supply_pressure_bar=3.0,
    pipe_diameter_mm=9.5,
    pipe_length_m=3.0,
)
# 輸出完整 SOP 與噴嘴規格
```

### 商用箱型機重度清潔（加壓泵）

```python
report = design_cleaning_system(
    equipment_name="商用箱型機 5HP",
    evaporator_width_mm=1200,
    evaporator_height_mm=400,
    supply_pressure_bar=8.0,   # 加壓泵
    pipe_diameter_mm=12.7,     # 1/2" 管
    pipe_length_m=5.0,
    target_distance_mm=200,
)
```

## Quick Reference

| 操作 | 指令 |
|------|------|
| 噴嘴計算 | `python scripts/nozzle_calc.py --pressure P --orifice D` |
| 完整方案 | `python scripts/design_cleaning.py --equipment NAME --width W --height H --supply P` |
| 家用建議噴嘴孔徑 | 1.5~2.0 mm |
| 翅片安全衝擊壓力 | < 50 kPa（鋁翅片），< 100 kPa（銅翅片） |
| 建議噴嘴距離 | 100~200 mm |
| 建議噴霧角度 | 15°~25°（蒸發器清潔） |

## Resources

- `references/nozzle-design.md` — 噴嘴水力計算與選型指南
- `references/evaporator-specs.md` — 常見冷氣蒸發器規格資料庫
- `references/cleaning-standards.md` — ASHRAE 與 CNS 清潔標準
- `references/safety-guidelines.md` — 作業安全規範
- `references/chemical-mixing.md` — 清潔劑濃度與使用建議
