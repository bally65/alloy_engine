---
name: design_assist
description: HVAC 清潔系統 AI 輔助設計整合工具。接受自然語言描述（如「幫我設計日立 2HP 冷氣的清潔方案」），自動協調 $fluid、$pressure、$cleaning skill，輸出完整工程設計報告。
---

# Design Assist — AI 輔助設計整合層

## Overview

將自然語言需求轉換為完整 HVAC 清潔系統設計報告。
自動判斷需要呼叫哪些底層 skill，並整合計算結果輸出設計文件。

**設計流程**：
```
自然語言輸入
    ↓ 解析設備規格
$fluid → 確認管道流態
    ↓
$pressure → 計算可用壓力
    ↓
$cleaning → 噴嘴設計 + 清潔 SOP
    ↓
生成設計報告（文字 + 圖表）
```

## Core Capabilities

### 1. 自然語言轉工程規格

```python
python scripts/parse_requirement.py "日立 RAS-28NK，家用自來水，要清潔蒸發器"
```

輸出解析後的工程參數（設備尺寸、水源壓力範圍等）。

### 2. 完整設計報告生成

```python
python scripts/full_report.py \
  --equipment "日立 RAS-28NK" \
  --type split-indoor \
  --supply-pressure 3.0 \
  --output report.md
```

### 3. 多方案比較

```python
python scripts/compare_scenarios.py \
  --equipment "商用箱型機 5HP" \
  --pressure-range "2.0,4.0,6.0,8.0"
```

## Common Use Cases

### 快速生成家用冷氣清潔方案

```bash
python scripts/full_report.py \
  --equipment "一般家用分離式 1.5HP" \
  --type split-indoor \
  --width 800 --height 180 \
  --supply-pressure 3.0 \
  --output 清潔方案.md
```

### 比較不同水壓下的清潔效果

```bash
python scripts/compare_scenarios.py \
  --equipment "分離式 2HP" \
  --width 900 --height 200 \
  --pressure-range "2.0,3.0,4.0,6.0,8.0"
```

## Quick Reference

| 操作 | 指令 |
|------|------|
| 快速設計 | `python scripts/full_report.py --equipment NAME --supply-pressure P` |
| 多壓力比較 | `python scripts/compare_scenarios.py --pressure-range "2,4,6,8"` |
| 需求解析 | `python scripts/parse_requirement.py "描述文字"` |

## Resources

- `references/equipment-database.md` — 常見冷氣型號規格資料庫
- `references/design-workflow.md` — 設計流程與決策邏輯
- `references/report-format.md` — 設計報告格式規範
