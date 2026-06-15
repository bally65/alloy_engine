# 實測協定與驗證計畫（Measurement Protocol）

> 本檔列出**唯有實體量測才能完成**的收尾項目（算力做不到的部分），給出可執行的
> 量測目標、樣品與協定，並提供「實驗前」可用的**文獻替代**作為過渡。對應缺陷
> D6（複合微結構/M-H 假設參數）與整機/材料預測的最終驗證。

---

## 0. 為什麼這些非算力可解

模型已把能用第一性原理 + 真實資料庫（NEMAD Tc、MP 0K 磁化）處理的都處理了。
剩下三類量本質上是**材料的真實微結構與工作溫度下的磁/熱行為**，公開資料庫不含、
或需特定樣品才測得到：

| 項目 | 為何需實測 | 目前模型用什麼代替 |
|---|---|---|
| 複合 connectivity（D6）| 取決於實際燒結/黏結微結構 | 假設 0.7（Wiener 界內） |
| 工作溫度 M-H 迴線 / ΔM | MP 為 0K DFT；工作溫度迴線需 VSM 量測 | 平均場 m(T/Tc) 溫度修正（已建） |
| 磁滯損耗 / 一階銳度 w | 取決於樣品缺陷、晶界、應力 | 假設值；D5 logistic w 待校 |
| 回熱 ε、利用率 util | 取決於熱交換器與流場 | 假設 ε、util=0.30 |

---

## 1. 量測目標（最小可驗證集，MVP）

挑 3 個落在不同物理區的代表材料，覆蓋二階/一階、有/無稀土：

| # | 材料 | 目的 | 預期 Tc | 模型現值對照 |
|---|---|---|---|---|
| M1 | 純 Gd | 二階基準、錨定 ΔM(T) 與溫度修正 | ~293 K | reference_materials「Gd」|
| M2 | La(Fe,Si)₁₃（可氫化）| 一階、驗證 D5 銳度 w 與 D8 氫化上修 | ~200→340 K（氫化後）| `hydrogenation_tc_shift_K` |
| M3 | (Mn,Fe)₂(P,Si) | 無稀土一階、ΔS 最大、低 κ | ~280 K | D8 (Mn,Fe)₂(P,Si) 物理 |

> 若要驗證 **GA 自主推薦** 的配方，從 `run_search.py --hybrid-tc` 的 Top-N CSV
> 取 1–2 個 Fe 基候選一併鑄造，直接檢驗「模型→真實」的端到端可信度。

## 2. 量測協定（每材料）

1. **製樣**：電弧熔煉/感應熔煉 → 退火均質化（一階相需正確相形成）。
   - La-Fe-Si 1:13 需長時退火；氫化於 H₂ 氣氛 1–10 bar、~150–300°C。
2. **成分/相**：EDS 確認成分、XRD 確認相（1:13 / 六方 Fe₂P 型）。
3. **微結構（解 D6）**：SEM 量測複合相連通度 connectivity、相分率 φ；
   → 回填 `composite.py` 的 connectivity（取代假設的 0.7）。
4. **磁性（解溫度修正/ΔM）**：VSM 量 M-H 迴線於 T_cold、T_hot（涵蓋 Tc）；
   → 取得工作溫度下的 ΔJ（取代平均場 m(T/Tc) 推估）、磁滯面積（磁滯損耗）。
5. **熱性（解 κ/Cp）**：雷射閃光法量 α → κ；DSC 量 Cp 與 ΔS_M（相變峰）。
6. **一階銳度（解 D5 w）**：由 M(T) 在 Tc 附近的斜率擬合 logistic 寬度 w
   → 回填 `magnetic_thermodynamic_score(transition_width_K=w)`。

## 3. 回填模型的對應點（量到什麼、改哪裡）

| 量測值 | 回填位置 |
|---|---|
| 工作溫度 ΔJ | 取代 `properties.magnetic_thermodynamic_score` 的平均場估計 |
| logistic 寬度 w | `magnetic_thermodynamic_score(transition_width_K=w)`（D5）|
| 複合 connectivity、φ | `composite.composite_properties` 的 connectivity 參數（D6）|
| κ、Cp、ΔS_M | `thermomagnetic/reference_materials.py` 對應材料 / 直接餵 `design_tmg` |
| 磁滯損耗 | `magnetocaloric_refrigeration` 的 hysteresis 懲罰、整機效率折減 |
| 整機 W/η/P（若做原型）| `reference_devices.py` 新增一筆「本工作」錨點（解發電側絕對校準）|

## 4. 實驗前的文獻替代（過渡橋接）

在拿到自測資料前，用已發表 M-H / ΔS_M 數據近似校準：

- **Gd / Gd₅(Si,Ge) / La-Fe-Si / Mn-Fe-P 的 M(T)、ΔS_M**：Tishin & Spichkin 2003；
  Gschneidner & Pecharsky 2000；Brück 系列。→ 填 `reference_materials.py`。
- **LLM 自動生成磁熱資料庫（AIP Advances 2024）**：ΔS_M / ΔT_ad 批量值，
  可作 D5 銳度 w 與 ΔM 的群體校準（不需自製樣）。
- **發電側原型**：已收錄 5 筆（`reference_devices.py`）；Waske et al. Nature Energy
  2019 的數值若取得可補上，進一步收斂 D12 的絕對功率校準。

## 5. 成本/可行性分級

| 量測 | 設備 | 可行性 |
|---|---|---|
| 成分/相（EDS/XRD）| 常見 | 高 |
| M-H 迴線（VSM/PPMS）| 中階磁量測 | 中（多數材料所需）|
| κ（雷射閃光）、Cp/ΔS_M（DSC）| 熱分析 | 中 |
| 整機 TMG 原型 W/η/P | 自製裝置 | 低（工程量大，可後置）|

→ **建議順序**：先 M-H + DSC 拿 ΔJ/ΔS_M/w（解最關鍵的 ΔM 與 D5），再 SEM 解 D6，
整機原型最後做。文獻替代可立即先把 `reference_materials.py` 校到已發表值。
