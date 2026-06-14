# 知識總覽（Knowledge Index）— 熱磁發電機材料與整機設計

> 本檔是整個「熱磁發電機（TMG）材料 → 整機」研究的知識備份與索引。把分散的
> 設計文件、缺陷登錄、資料調研串成一條線，方便日後回溯。
> 對話/工作歷程見 [`SESSION_LOG.md`](SESSION_LOG.md)。

---

## 研究主線（一句話）

從 TMG 的數學/熱力學推導出發，建出**整機效能模型**，發現瓶頸依序是
**顯熱 → 磁滯 → 熱導率 κ → 元素空間 → 真實資料**，並逐一處理；最終把
**真實 NEMAD 居禮溫度**接進 GA 搜尋。

## 文件地圖

| 文件 | 內容 | 關鍵結論 |
|---|---|---|
| [THERMOMAGNETIC_GENERATOR_DESIGN](THERMOMAGNETIC_GENERATOR_DESIGN.md) | 整機三階段數學模型（磁功/熱輸入/效率/功率/電壓）| 顯熱主導效率；回熱是主槓桿 |
| [MAGNETOCALORIC_DUALITY](MAGNETOCALORIC_DUALITY.md) | 發電↔製冷對偶；對標 CAS HMR | 磁滯是兩向頭號殺手 |
| [TMG_DESIGN_PLAN](TMG_DESIGN_PLAN.md) | 四層架構藍圖 + 模擬評估 | 架構優化 ×71 效率、×31 電壓 |
| [MATERIALS_AND_DEVICE_GA](MATERIALS_AND_DEVICE_GA.md) | 換材料 what-if + GA 接整機目標 | κ 是隱形殺手，非只看 ΔM |
| [COMPOSITE_MATERIALS](COMPOSITE_MATERIALS.md) | 高 κ 基底 + 高 ΔM 相複合 | 複合提升功率密度 ×2.4–×10 |
| [GA_COMPOSITE_SEARCH](GA_COMPOSITE_SEARCH.md) | 複合有效物性接回 GA | 瓶頸轉移到元素空間 |
| [RARE_EARTH_EXPANSION](RARE_EARTH_EXPANSION.md) | 加 Gd/La（10→12 元素）| GA 自主收斂到 Gd 基室溫材料 |
| [KNOWN_DEFECTS](KNOWN_DEFECTS.md) | 12 項缺陷登錄 + 可處理性分級 | D1–D7 已修；D8–D12 路線圖 |
| [DATA_SOURCING_ASSESSMENT](DATA_SOURCING_ASSESSMENT.md) | 真實資料調研 + GHA 方案 | NEMAD 公開可抓；MP 已通 |

## 關鍵量化結果

| 主題 | 數字 |
|---|---|
| 架構優化（低溫情境）| η 0.022%→1.56%（×71）、P/V 0.73→4.1 MW/m³、V 0.14→4.37V |
| 複合材料（Mn-Fe-P+Cu）| 功率密度 ×10（D4 封頂後物理量級）|
| 製冷對標（CAS HMR）| 8.4 kW/kg、火用效率 59.6%（吻合文獻 8.3/54.2%）|
| **Tc sim-to-real** | 合成 R²=**−0.17** → 真實 NEMAD 訓練 R²=**0.88**（MAE 274→81°C）|
| Br vs MP DFT | bias **−0.50T**（合成系統性低估 → delta_M 偏保守）|

## 核心程式

```
alloy_engine/thermomagnetic/
  generator_design.py        # 整機設計（含 D4 頻率封頂、分層發電床）
  magnetocaloric_refrigeration.py  # 反向製冷對偶
  composite.py               # 複合材料有效物性 + 最佳基底分率
  device_score.py            # GA 整機級目標（torch 向量化，含複合）
  properties.py              # 材料物性（含 D5 一階相變銳度）
  reference_materials.py     # 基準 MCM 文獻值（Gd/La-Fe-Si/Mn-Fe-P）
alloy_engine/models/
  surrogate.py               # 合成 4-property 代理
  hybrid.py                  # 真實 Tc + 合成 Hc/Br/σy 混合（接 GA）
```

## 復現指令

```bash
# 1. 合成代理（含 Gd/La 稀土）
python scripts/train_surrogate.py --n-samples 6000 --epochs 100

# 2. 真實 NEMAD Tc 基準（需 external/NEMAD/Dataset/FM_with_curie.csv）
python scripts/train_surrogate_nemad_baseline.py        # → R²≈0.88

# 3. sim-to-real 對標
python scripts/nemad_eval.py                            # 合成 vs 真實 Tc
python scripts/mp_magnetization_eval.py                 # 合成 Br vs MP（需 MP key）

# 4. GA 用真實 Tc + 整機/複合目標搜尋
python scripts/run_search.py --scenario 低溫廢熱_150C --mode thermomagnetic \
    --hybrid-tc alloy_engine/models/checkpoints/surrogate_nemad_baseline.pt \
    --w-device 1.0 --device-matrix Cu

# 5. 設計模擬與 what-if
python scripts/simulate_tmg_design.py
python scripts/evaluate_reference_materials.py
python scripts/evaluate_composite_materials.py
```

## 資料來源（git-ignored，不入版控）

- **NEMAD Tc**：[`sumanitani/NEMAD-MagneticML`](https://github.com/sumanitani/NEMAD-MagneticML)
  `Dataset/FM_with_curie.csv`（公開可抓，引用 Nature Comms 2025）→ `external/`
- **Materials Project 磁化**：mp-api / raw HTTPS，需免費 API key → `external/.mp_key`

## 現況與下一步

- ✅ 已完成：整機模型、製冷對偶、複合材料、稀土擴張、CI、D4/D5 物理修正、
  真實 Tc 接入 GA。
- 🔶 進行中：真實 Br 校準（需區分 0K 飽和 vs 工作溫度磁化）。
- ⛔→🔶 已連通：NEMAD（Tc）、MP（磁化）皆可取用，剩整合與校準。
