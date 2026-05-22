# HVAC Fluid Skills — Agent 使用指南

這個 `skills/` 目錄提供流體力學與 HVAC 清潔系統設計能力。
每個 skill 是獨立模組，可單獨使用或組合使用。

## 可用 Skills

| Skill | 觸發情境 | SKILL.md |
|-------|---------|----------|
| `$fluid` | 計算流速、雷諾數、流態、流體性質 | `fluid/SKILL.md` |
| `$pressure` | 管路壓損、噴嘴前可用壓力、閥門選型 | `pressure/SKILL.md` |
| `$cleaning` | 冷氣蒸發器/冷凝器清潔方案設計 | `cleaning/SKILL.md` |
| `$design_assist` | 自然語言 → 完整 HVAC 清潔設計報告 | `design_assist/SKILL.md` |
| `$chem_cleaning` | 污垢溶解動力學、表面張力/剪切力、清潔劑推薦 | `chem_cleaning/SKILL.md` |

## 共用計算模組

所有 skills 共用 `fluidsim_skills/` Python 套件：

```
fluidsim_skills/
  fluid.py     ← 水的物理性質、雷諾數、流態判斷
  pressure.py  ← Darcy-Weisbach 壓損、閥門 K 值
  cleaning.py  ← 噴嘴計算、清潔系統設計
```

## 快速使用

### 場景一：只需要壓力計算

```bash
python skills/pressure/scripts/pressure_drop.py \
  --diameter 9.5 --length 5 --flowrate 10
```

### 場景二：設計完整清潔方案

```bash
python skills/cleaning/scripts/design_cleaning.py \
  --equipment "日立 RAS-28NK" \
  --width 750 --height 200 \
  --supply 3.0
```

### 場景三：生成設計報告

```bash
python skills/design_assist/scripts/full_report.py \
  --equipment "日立 RAS-28NK" \
  --type split-2hp \
  --supply-pressure 3.0 \
  --output report.md
```

## Skill 依賴關係

```
design_assist
    ├── cleaning
    │     ├── pressure
    │     │     └── fluid
    │     └── fluid
    └── fluid
```

## 開發規範

- 所有計算使用 SI 單位，對外介面以常用單位（mm、bar、L/min）換算
- 每個 script 都可獨立執行（`python scripts/xxx.py --help`）
- 新增 skill 請在此 CLAUDE.md 更新 skill 列表
