---
name: design_assist
description: HVAC 清潔系統全域決策報告。整合流體力學、化學溶解動力學、毛細滲透、翅片熱效率、液滴動力學、積垢預測，一次輸出八節完整工程報告。
---

# Design Assist — 全模組整合決策報告

## Overview

將設備規格與環境條件轉換為完整 HVAC 清潔決策報告。
整合六大物理模組，一次輸出：液壓設計、清潔劑推薦、毛細滲透評估、翅片效率、噴霧品質、積垢預測。

**整合流程**：
```
設備輸入
    ├── $fluid / $pressure / $cleaning → 液壓設計 + 清潔 SOP
    ├── $chem_cleaning                 → 清潔劑推薦 + 溶解效率
    ├── $capillary                     → 毛細滲透分析
    ├── $thermal                       → 翅片效率 η
    ├── $droplet                       → 噴霧 SMD + 破碎模式
    └── $fouling                       → 積垢狀態 + 清潔週期
              ↓
    八節 Markdown 決策報告
```

## Core Capabilities

### 1. 全域決策報告（推薦入口）

```bash
python scripts/comprehensive_report.py \
  --equipment "日立 RAS-28NK" --type split-2hp \
  --contamination grease_light --supply 3.0 \
  --elapsed-hours 2000 --output report.md
```

輸出八節報告：摘要、設備規格、液壓設計、化學清潔、毛細滲透、翅片效率、液滴品質、積垢分析。

### 2. 液壓設計報告（舊版）

```bash
python scripts/full_report.py \
  --equipment "日立 RAS-28NK" --type split-2hp \
  --supply-pressure 3.0 --output hydraulic.md
```

### 3. 參數說明

| 參數 | 預設 | 說明 |
|------|------|------|
| `--contamination` | grease_light | dust_general / grease_light / grease_heavy / biofilm / mineral_scale |
| `--environment` | ac_indoor_unit | ac_indoor_unit / ac_outdoor_unit / coastal_air / industrial_air / kitchen_exhaust |
| `--elapsed-hours` | 1000 | 上次清潔後已運行時數 |
| `--fin-height` | 15.0 | 翅片高度 mm |
| `--kappa` | 自動（Al=237/Cu=385）| 可輸入 alloy_engine 預測的 κ 值 |

## Quick Reference

| 操作 | 指令 |
|------|------|
| 全域報告 | `python scripts/comprehensive_report.py --equipment NAME --supply P` |
| 液壓報告 | `python scripts/full_report.py --equipment NAME --supply-pressure P` |
| 污垢類型 | dust_general, grease_light, grease_heavy, biofilm, mineral_scale |

## alloy_engine κ 整合

翅片材料由 alloy_engine 預測的 κ 可透過 `--kappa` 直接傳入：

```bash
# 先用 thermal/scripts/alloy_kappa_bridge.py 計算合金 κ
python skills/thermal/scripts/alloy_kappa_bridge.py --Fe 0.7 --Ni 0.2 --Al 0.1
# → κ = 134.2 W/m·K

# 再帶入全域報告
python scripts/comprehensive_report.py \
  --equipment "合金翅片蒸發器" --supply 3.0 --kappa 134.2
```
