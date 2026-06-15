# 論文 / 研究生論文框架（Paper / Thesis Outline）

> 把這條研究線整理成可發表/可交的學術成果。每節對應 repo 內既有產物，
> 寫作時可直接引用對應檔案的數字與圖。

---

## 暫定標題

> 「從第一性原理到真實資料：一個熱磁發電/製冷材料與整機的計算設計與校準框架」
> *A first-principles-to-real-data computational framework for thermomagnetic
> energy-conversion materials and device design*

## 摘要（要點）

廢熱回收的熱磁發電（TMG）受限於材料與整機耦合。本工作建立從元素成分到整機效能
的計算框架，結合 ML 代理 + GPU 遺傳演算法，並以真實資料（NEMAD 居禮溫度、
Materials Project 磁化）與文獻磁熱數據校準。發現瓶頸依序為顯熱→磁滯→熱導率→
元素空間，提出複合材料解方，並以最低成本分析指向 La(Fe,Si)₁₃ / (Mn,Fe)₂(P,Si)。
所有絕對預測帶文獻 ±12% 誤差條與發電側 ~10× 現實折減，並附可執行的實驗驗證計畫。

## 章節結構（對應 repo）

| 節 | 內容 | 對應產物 |
|---|---|---|
| 1. 引言 | 廢熱、TMG、MCE 材料、研究缺口 | README、THERMOMAGNETIC_GENERATOR_DESIGN |
| 2.1 整機模型 | 三階段（磁功/熱輸入/效率/功率/電壓）| generator_design.py |
| 2.2 製冷對偶 | 正反向對偶、對標 HMR | magnetocaloric_refrigeration.py |
| 2.3 ML 代理 + GA | 4-property 代理、GPU 向量化 GA | surrogate.py、gpu_ga.py |
| 2.4 真實資料校準 | NEMAD Tc、MP 磁化溫度修正 | hybrid.py、magnetization_correction.py |
| 2.5 文獻校準 + UQ | ΔS_M/w 文獻、±12% 傳播 | literature_mce.py、uncertainty.py |
| 3.1 材料發現 | 元素擴張、稀土/P-Ge、GA 收斂 | RARE_EARTH_EXPANSION、D8 |
| 3.2 瓶頸分析 | 顯熱/磁滯/κ/元素空間 | KNOWN_DEFECTS、SENSITIVITY_ANALYSIS |
| 3.3 複合解方 | 高κ基底+高ΔM相、φ* | COMPOSITE_MATERIALS |
| 3.4 sim-to-real | 合成 −0.17 → 真實 0.78；Br bias | PIPELINE_REPORT、DATA_SOURCING_ASSESSMENT |
| 3.5 最低成本材料 | 效能/成本、新物種比較 | LITERATURE_CALIBRATION |
| 3.6 整機預估（帶誤差條）| P/V、η ± 12%、D12 折減 | CALIBRATED_PREDICTION |
| 4. 實驗驗證計畫 | 先導+決策門+規模化 | MEASUREMENT_PROTOCOL、實驗驗證計畫_* |
| 5. 限制 | 能力聲明、信心分級 | CAPABILITY_STATEMENT |
| 6. 結論 | 相對可信工具 + 待實測收斂絕對值 | — |

## 主要貢獻（claims）

1. 端到端「成分→整機」框架，正反向（發電↔製冷）對偶且單位一致。
2. 以**公開真實資料**把 Tc 從 sim-to-real R²=−0.17 救到 0.78。
3. **誠實的不確定度**：絕對輸出帶文獻 ±12% 誤差條與 D12 量化的現實折減。
4. **最低成本材料**結論（La-Fe-Si / Mn-Fe-P），含新物種（毒/貴/逆磁熱）排除理由。
5. 可執行、去風險的**實驗驗證計畫**（文獻優先、決策門閘控）。

## 可重現性

- 全部以 git 腳本可復現；CI（GitHub Actions）守護 280+ 測試。
- 真實資料執行時抓取（NEMAD 公開、MP 免費 key），不入版控。
- 一鍵管線 `run_full_pipeline.sh`（自動 CUDA/MPS/CPU）。

## 投稿/呈交建議

- 期刊取向：計算材料 / 能源材料 / 磁熱（如 *Acta Mater.*、*J. Phys. D*、
  *Energy* 系）。
- 研究生論文：以第 2 章為方法、第 3 章為結果、第 4–5 章為驗證與限制；
  附錄放缺陷登錄與復現指令。
- 圖：sim-to-real 對標、瓶頸鏈、複合 φ*、最低成本、帶誤差條的整機預估。
