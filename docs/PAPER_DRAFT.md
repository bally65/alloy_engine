# 從第一性原理到真實資料：熱磁能量轉換材料與整機的計算設計與校準框架

*A first-principles-to-real-data computational framework for thermomagnetic
energy-conversion materials and device design*

> 論文初稿（draft）。數字均引自本 repo 的可復現產物；圖見 `docs/figures/`。

---

## Abstract

廢熱回收的熱磁發電（TMG）效能受材料與整機強耦合所限，傳統「只篩材料」無法回答
「能組出怎樣的發電機」。本工作建立一個從元素成分到整機效能的計算框架：以輕量 ML
代理預測四項材料性質（Tc、Hc、Br、σy），GPU 向量化遺傳演算法（GA）在整機目標下搜尋
成分，並以**真實資料**（NEMAD 15,577 筆居禮溫度、Materials Project DFT 磁化）與
**文獻磁熱數據**校準。我們發現整機瓶頸依序為顯熱→磁滯→熱導率 κ→元素空間→真實資料，
並提出複合材料（高 κ 基底 + 高 ΔM 相）為出路。把 Tc 代理以真實 NEMAD 資料訓練，使
sim-to-real R² 由 −0.17 升至 0.78；磁化經溫度修正後系統偏差由 −0.50 T 降至 −0.12 T。
所有絕對預測帶文獻 ±12% 誤差條與發電側 ~10× 現實折減。最低成本分析指向
La(Fe,Si)₁₃ 與無稀土 (Mn,Fe)₂(P,Si)。附可執行、決策門閘控的實驗驗證計畫。

## 1. Introduction

熱磁循環利用鐵磁體在居禮溫度附近磁化隨溫度劇變，將熱能轉為電磁功
（W = μ₀∮H dM）。低品位廢熱（100–300°C）量大但難利用，TMG 是潛在路徑，然其效率
受顯熱主導、磁滯損耗、與材料熱導率限制循環頻率等多重耦合所困。既有研究多聚焦單一
材料的磁熱效應，缺乏「材料↔整機」一體化的設計與校準框架，且多數預測停在點估計、
未對標真實量測。本工作填補此缺口。

## 2. Methods

**2.1 整機模型**（`generator_design.py`）。三階段：磁功密度 W = μ₀·ΔM·B·util；
熱輸入 q_in = ρCpΔT(1−ε) + ρT·ΔS_M（顯熱可回熱、磁熵潛熱不可）；效率 η = W/q_in，
循環頻率 f = α/(2L²)（D4 工程封頂 f_eff = f/(1+f/f_max)）。正反向對偶得磁熱製冷模型
（`magnetocaloric_refrigeration.py`），對標 CAS 全固態 HMR（8.4 kW/kg、火用 59.6%）。

**2.2 ML 代理 + GA**（`surrogate.py`、`gpu_ga.py`）。四個 MLP（36 維 Oliynyk 特徵，
與元素數無關）；GA 族群可達數萬，整機目標 w_device 直接最佳化「功率密度×效率」，
化學可合成性軟約束（脆相、析出、稀土氧化/脆裂、類金屬脆性）。

**2.3 真實資料與文獻校準**。Tc 以 NEMAD 真實居禮溫度訓練（`hybrid.py` 接 GA、
`bake_real_tc.py` 烘焙統一 bundle）；磁化以 MP DFT + 平均場溫度修正
（`magnetization_correction.py`）；ΔS_M 與一階銳度 w 以文獻校準
（`literature_mce.py`）；不確定度以 Monte Carlo 傳過整機（`uncertainty.py`）。

## 3. Results

**3.1 瓶頸鏈（圖 4）**。整機分析顯示顯熱主導效率（η~0.02%），回熱是主槓桿；
磁滯是發電與製冷兩向頭號殺手；熱導率 κ 透過循環頻率成為「隱形天花板」——最好的
一階磁熱材料 κ 極低。瓶頸隨之轉移到元素空間與真實資料。

**3.2 複合材料解方**。高 κ 基底（Cu/Al/α-Fe）+ 高 ΔM 相，以 Wiener 界估有效 κ，
存在最佳基底分率 φ*≈0.3，功率密度提升 ×7–12（敏感度分析：定性穩健，
connectivity 影響 ~43% 但不翻盤）。

**3.3 Sim-to-real（圖 1）**。12 元素合成代理在真實 NEMAD 上 R²=−0.17（比猜平均還差）；
以真實 Tc 訓練 baseline R²=0.78、MAE 91°C（P/Ge 擴張後 1,380 化合物）。磁化溫度修正
後 Br 偏差 −0.50→−0.12 T，證實多源於 0K-vs-室溫而非系統性低估。

**3.4 最低成本材料（圖 2）**。文獻 ΔS_M ÷ 元素價格代理：La(Fe,Si)₁₃H（14.2）與
(Mn,Fe)₂(P,Si)（9.3，無稀土）的效能/成本比 Gd/Gd₅Si₂Ge₂ 高 ~100–200×；MnAs 便宜但
含砷劇毒、FeRh 因 Rh 達 ~$9723/kg、Heusler 有逆磁熱+磁滯——皆排除。

**3.5 帶誤差條的整機預估（圖 3）**。La-Fe-Si 1110±134、Mn-Fe-P 609±72、
Gd 1847±220 kW/m³（理想，±12% 文獻散布）。反直覺但正確：Gd 因高 κ/低 Cp 之 P/V 高於
La-Fe-Si，即為複合材料存在的理由。

**3.6 設計案例（150°C）**。GA 搜出 Fe-Ni-Co 多元合金（Tc 139.5°C、κ 118.6）；
整機 P/V ~200 kW/m³（現實折減後）、f 28.5 Hz。詳見 `case_study/CASE_STUDY_150C.md`。

## 4. Discussion & Limitations

模型為**可信的相對設計與篩選工具**：材料排序、瓶頸結論、複合決策皆穩健且被 GA 自主
行為佐證。**絕對**輸出帶明確誤差條與現實折減——尤其發電側絕對功率密度為理想化上界
（比真實原型高 ~10×），唯有實體 M-H/DSC/SEM 量測能最終收斂（見能力聲明與實驗計畫）。

## 5. Conclusion

本框架把熱磁能量轉換從「單材料磁熱效應」推進到「材料↔整機一體化、真實資料校準、
帶不確定度」的設計工具，並以最低成本分析給出可落地的材料選擇與可執行的驗證路徑。

## References（代表）

Brück (arXiv:1006.3415); Pecharsky & Gschneidner, PRL 78, 4494 (1997);
Dan'kov et al., PRB 57, 3478 (1998); Fujita et al., PRB 67, 104416 (2003);
Tegus et al., Nature 415, 150 (2002); NEMAD (Nature Comms 2025); Kishore & Priya
(OSTI 1538781); Nat. Commun. 14 (2023, PMC10412618). 完整見 `LITERATURE_CALIBRATION.md`。

## Reproducibility

全部以 git 腳本可復現；CI 守護 290+ 測試。一鍵管線 `run_full_pipeline.sh`（自動
CUDA/MPS/CPU）；圖 `make_figure_pack.py`；案例 `run_search.py`。
