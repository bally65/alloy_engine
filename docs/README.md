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
| [PIPELINE_REPORT](PIPELINE_REPORT.md) | 生產級全管線正式數字 | 真實 Tc R²=0.78（P/Ge 擴張後）|
| [MEASUREMENT_PROTOCOL](MEASUREMENT_PROTOCOL.md) | 實測協定（D6/驗證）+ 文獻替代 | 唯實測可解的收尾 |
| [SENSITIVITY_ANALYSIS](SENSITIVITY_ANALYSIS.md) | 假設參數敏感度（D6）| connectivity 43%、回熱相消；定性穩健 |
| [LITERATURE_CALIBRATION](LITERATURE_CALIBRATION.md) | 文獻校準 + 最低成本材料（無儀器）| La-Fe-Si/Mn-Fe-P 效能/成本 ×100–200 於 Gd |
| [CALIBRATED_PREDICTION](CALIBRATED_PREDICTION.md) | 校準後整機預估（帶 ±12% 誤差條）| 點估計 → 可辯護的區間估計 |
| [CAPABILITY_STATEMENT](CAPABILITY_STATEMENT.md) | 能力聲明：能/不能預測什麼 | 相對可信、絕對帶折減 |
| [PAPER_OUTLINE](PAPER_OUTLINE.md) | 論文/論文框架 + 貢獻 | 可發表/可交的學術成果 |

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
# 0. 一鍵生產級全管線（自動選 CUDA/MPS/CPU；Mac M5 用 MPS）→ docs/PIPELINE_REPORT.md
bash scripts/run_full_pipeline.sh

# 1. 合成代理（14 元素：含 Gd/La 稀土 + P/Ge 類金屬）
python scripts/train_surrogate.py --n-samples 6000 --epochs 100

# 2. 真實 NEMAD Tc 基準（需 external/NEMAD/Dataset/FM_with_curie.csv）
python scripts/train_surrogate_nemad_baseline.py        # → R²≈0.88

# 3. sim-to-real 對標
python scripts/nemad_eval.py                            # 合成 vs 真實 Tc
python scripts/mp_magnetization_eval.py                 # 合成 Br vs MP（需 MP key）

# 4a. 把真實 Tc 烘焙進主代理 → 單一統一 bundle（D2，免 --hybrid-tc）
python scripts/bake_real_tc.py   # → checkpoints/bundle_real_tc.pt

# 4b. GA 用真實 Tc + 整機/複合目標搜尋（兩種等價路徑）
python scripts/run_search.py --scenario 低溫廢熱_150C --mode thermomagnetic \
    --checkpoint alloy_engine/models/checkpoints/bundle_real_tc.pt \
    --w-device 1.0 --device-matrix Cu
#   或保留兩檔、推論期混合：
#   ... --hybrid-tc alloy_engine/models/checkpoints/surrogate_nemad_baseline.pt

# 5. 設計模擬與 what-if
python scripts/simulate_tmg_design.py
python scripts/evaluate_reference_materials.py
python scripts/evaluate_composite_materials.py
python scripts/evaluate_reference_devices.py   # 發電側對標真實 TMG 原型（D12）
```

## 資料來源（git-ignored，不入版控）

- **NEMAD Tc**：[`sumanitani/NEMAD-MagneticML`](https://github.com/sumanitani/NEMAD-MagneticML)
  `Dataset/FM_with_curie.csv`（公開可抓，引用 Nature Comms 2025）→ `external/`
- **Materials Project 磁化**：mp-api / raw HTTPS，需免費 API key → `external/.mp_key`

## 現況與下一步

- ✅ 已完成：整機模型、製冷對偶、複合材料、稀土擴張、CI、D4/D5 物理修正、
  D9 稀土可製造性、真實 Tc 接入 GA 並烘焙進統一 bundle（D2）、D3 磁化溫度修正、
  D12 發電側原型對標、GHA sim-to-real 基準、知識/歷程備份。
  D8 P/Ge 元素擴張（12→14，解鎖 +366 筆真實 NEMAD 化合物 + 氫化 Tc 模型）。
- 🔶 進行中：真實 Br 完整入管線（謹慎，需 0K 飽和→工作溫度）；
  D11（生產級代理重跑）、D6（複合微結構參數校準）。
- ⛔→🔶 已連通：NEMAD（Tc）、MP（磁化）皆可取用並已用於對標/烘焙。
