# 工作歷程記錄（Session Log）

> 本檔備份這段「熱磁發電機」研究的對話與工作歷程，依時間順序記錄每一步的
> 提問動機、決策、產出與量化結果。知識索引見 [`README.md`](README.md)。
> （以 git commit 為事實基準重建；非逐字對話。）

---

## 緣起

使用者提出以「純數學與熱力學底層邏輯」推算並設計熱磁發電機（TMG）的架構，
拆解為熱能輸入、磁矩變化、電磁功輸出三階段。本引擎原為「熱磁合金材料篩選」，
工作即把它從**材料層**延伸到**整機層**，再一路追到**真實資料**。

## 時間線（PR 對照）

| # | 提問/動機 | 產出 | 結果 | PR |
|---|---|---|---|---|
| 1 | 從數學推導設計 TMG 整機 | `generator_design.py` 整機三階段模型 | 顯熱主導效率（η~0.02%）；回熱是主槓桿 | #2 |
| 2 | 參考磁熱製冷「反向運作」 | `magnetocaloric_refrigeration.py` 對偶 | 對標 CAS HMR 8.4kW/kg；磁滯是頭號殺手 | #2 |
| 3 | 規劃設計 + 評估 + 模擬 | `simulate_tmg_design.py`、分層發電床、設計藍圖 | 架構優化 ×71 效率、×31 電壓 | #2 |
| 4 | 換高 ΔM 材料 + GA 接整機目標 | `reference_materials.py`、`device_score.py` | **κ 是隱形殺手**，非只看 ΔM | #2→#3 |
| 5 | 收斂：複合材料 | `composite.py` 高 κ 基底 + 高 ΔM 相 | 功率密度 ×5–×22（後 D4 修正為 ×2.4–×10）| #3 |
| 6 | 複合接回 GA | `device_score` 複合最佳化 + `--device-matrix` | 瓶頸轉移到元素空間 | #4 |
| 7 | 擴張元素空間到稀土 | 加 Gd/La（10→12）、近室溫情境 | GA 自主收斂到 Gd 基室溫材料 | #4 |
| 8 | 評估缺陷 | — | 12 項缺陷，根因=以合成資料訓練 | — |
| 9 | 修可處理缺陷（A+B）| 修 NEMAD 腳本（10→12）、保留稀土條目 | 消除沉默迴歸缺陷 | #5 |
| 10 | 研究可處理方案 | CI workflow + `KNOWN_DEFECTS.md` | D7（CI）落地，攔截迴歸 | #6 |
| 11 | 物理保真度 | D4 頻率封頂、D5 一階相變銳度 | 複合增益回到物理量級 | #7 |
| 12 | 沒資料 → 調研 + GHA 方案 | `DATA_SOURCING_ASSESSMENT.md` | **NEMAD 公開可抓**；實測合成 R²=−0.17 | #8 |
| 13 | 用真實 Tc 訓練證明可行 | 跑 `train_surrogate_nemad_baseline` | 真實 **R²=0.88**（vs 合成 −0.17）| #8 |
| 14 | 用 MP key 解 D3 | `mp_magnetization_eval.py` | MP 已通；Br bias **−0.50T** | #8 |
| 15 | 真實 Tc 接進 GA + 備份 | `hybrid.py`、`--hybrid-tc`、知識/歷程備份 | GA 用真實 Tc 搜尋（Tc 命中 153–157°C）| #8 |

## 關鍵決策與理由

- **整機 vs 材料層**：原引擎只算材料；整機模型才能回答「能組出怎樣的發電機」。
- **正反向對偶**：發電與製冷共用材料/磁路，製冷的成熟文獻可當校準錨。
- **不天真拿 MP 校 Br**：MP 是 0K 飽和、我們的 Br 是工作溫度，直接校會把
  delta_M 推錯方向 → 列為謹慎後續。
- **資料不入版控**：NEMAD 無 license、MP key 為機密 → 皆 git-ignored，
  只「執行時抓取＋引用」。

## 安全備註

- Materials Project API key 曾以明文出現在對話中 → 已只存 git-ignored
  `external/.mp_key`，commit 前以 `git grep` 確認未洩漏；**建議使用者 rotate
  該 key**。

## 現況

七個 PR 全數合併進 main（截至 #7）；#8 含資料調研、真實 Tc 接入與本備份。
測試 217 項通過，CI 於 GitHub runner 實證綠燈。
