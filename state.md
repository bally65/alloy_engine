# 專案狀態（state.md）

> 熱磁能量轉換材料與整機計算設計引擎（alloy_engine）的當前狀態總結。
> 最後更新：2026-06-15（main @ PR #20 合併後）。

---

## 1. 進度總結

### 整體
從「熱磁合金材料篩選器」擴展為**成分 → 整機 → 真實資料校準**的完整框架，並把兩個
內在磁性量（Tc、Br）從合成升級為真實資料訓練、交叉驗證、可預測且實際用於預測。

### 已完成（皆在 main、有測試與 CI 守護）
| 領域 | 狀態 | 關鍵結果 |
|---|---|---|
| 整機 TMG 模型 | ✅ | 三階段（磁功/熱輸入/效率/功率/電壓）；分層發電床 |
| 製冷對偶 | ✅ | 對標 CAS HMR（8.4 kW/kg、火用 59.6%）|
| ML 代理 + GPU GA | ✅ | 4-property、整機目標、化學軟約束 |
| 元素空間 | ✅ | 14 元素（含稀土 Gd/La + 類金屬 P/Ge）|
| 複合材料 | ✅ | 高κ基底+高ΔM相，φ*≈0.3，增益 ×7–12 |
| **Tc 真實校準** | ✅ | NEMAD 真實訓練 **R²=0.78**（合成 −0.17）；已烘焙進 bundle |
| **Br 真實校準** | ✅ | MP DFT 訓練 **R²=0.58 / held-out 0.70**（合成 ≤0）；已烘焙進 bundle |
| Hc / σy | 🔶 維持合成 | 外在/製程主導，組成-only 本質受限（已評估，見 HC_SIGMA_FEASIBILITY）|
| 不確定度傳播 | ✅ | 文獻 ±12% Monte Carlo → 整機 P/V、η 帶誤差條 |
| 缺陷登錄 D1–D12 | ✅ | 全處理（D1/D2/D3/D4/D5/D7/D8/D9/D11/D12 修復；D6 量化；Hc/σy 評估）|
| 對外輸出 | ✅ | 150°C 設計案例、論文初稿、出版圖表包、模型卡、pyproject/Makefile |
| 品質 | ✅ | **296 測試通過**、GitHub Actions CI、漂移守衛、兩輪 code-review 審查 |

### 缺陷狀態快照
D1✅ D2✅ D3✅ D4✅ D5✅ D6✅(量化) D7✅ D8✅ D9✅ D11✅ D12✅；
Hc/σy 經評估維持合成（物理本質受限，非缺陷）。

---

## 2. 已確認的架構決策

1. **內在 vs 外在性質分界**：只對「內在」量（Tc、磁化/Br）做真實資料預測；「外在/製程
   主導」量（Hc、σy）維持合成、僅作 GA 軟約束——不假裝可預測。這是核心可信度原則。
2. **真實資料不入版控**：NEMAD（Tc）、MP（磁化）皆 git-ignored，執行時抓取 + 引用。
   checkpoint（.pt/.pkl）git-ignored；只 commit「可復現結果（文字）」，不存二進位。
3. **物性陣列以元素符號為鍵的字典建構**（按 ELEMENTS 對齊）：加元素只需補鍵，缺鍵
   即 KeyError——根除「忘了同步位置陣列」的靜默維度漂移（特徵維度 36，與元素數無關）。
4. **真實模型整合 = baseline → 烘焙進統一 bundle**：`replace_tc_head` / `replace_br_head`
   把真實 Tc、Br 頭換進 `bundle_real_tc.pt`，下游用標準 `SurrogateBundle.load`（免旗標）。
5. **裝置自動選擇**：CUDA → MPS（Apple Silicon）→ CPU，`ALLOY_DEVICE` 可覆寫。
6. **絕對值誠實折減**：發電側絕對功率密度為理想化上界，對標真實原型後套 ~10×（D12）；
   所有絕對輸出帶文獻 ±12% 誤差條。
7. **單一真實來源 + 漂移守衛**：`reference_materials` 的 ΔS_M/Tc 與 `literature_mce`
   對齊，並有測試強制一致（防漂移）。
8. **開發流程**：固定分支 `claude/thermomagnetic-generator-design-qvi4bw`，每批工作
   開 draft PR、CI 綠燈後合併。

---

## 3. 編譯 / 建置狀態

**目前無任何編譯錯誤。**

- `py_compile` 掃描全部 `alloy_engine/` 與 `scripts/` 的 .py 檔：**全數通過，零錯誤**。
- 測試套件：**296 項全數通過**（`python -m pytest tests/`）。
- CI（GitHub Actions `tests.yml`）：在每次 push/PR 跑全套件 + 16 支腳本 py_compile，
  截至 main @ PR #20 為**綠燈**。
- 套件可安裝：`pip install -e .`（pyproject.toml 有效）。

> 註：使用者詢問的「當前編譯錯誤」目前為**無**。下方列出的是真實的**已知限制/開放項**
> （非編譯錯誤），以資誠實交代。

### 已知限制（非錯誤，物理/資料本質）
- **Hc、σy 為合成**：外在/製程主導，組成-only 預測上限低、無乾淨公開組成級資料集。
- **整機絕對功率密度為理想化上界**（~10× 高於真實原型）；相對結論可信，絕對待實測。
- **Br R²=0.58 為中等**：金屬磁化真實資料稀疏（266 化合物）；可再擴 chemsys。
- **未經實體實驗驗證**：從未「模型預測 → 獨立實測證實」；下一步須實體量測
  （協定見 `docs/MEASUREMENT_PROTOCOL.md`）。
- **執行期相依**：真實資料管線需 NEMAD CSV（公開可抓）與 MP API key；checkpoint 為
  ephemeral，需用 `run_full_pipeline.sh` / CI 重生。

### 環境相依（非錯誤，但執行某些腳本所需）
- MP 相關腳本（`mp_magnetization_eval.py`、`build_mp_magnetization_dataset.py`、
  `train_br_mp_baseline.py`）需 `external/.mp_key`（git-ignored）。
- NEMAD 相關（`nemad_eval.py`、`train_surrogate_nemad_baseline.py`）需
  `external/NEMAD/Dataset/FM_with_curie.csv`。
- `LinAlgWarning`（sklearn Ridge ill-conditioned）為良性警告，非錯誤。

---

## 4. 下一步（皆需實體實驗或外部資源）
1. 鑄一個 GA 候選樣品，實測 Tc/Br 驗證模型預測（打破「未經驗證」）。
2. 整機 TMG 原型，錨定發電側絕對 P/V、η（收斂 D12 的 ~10×）。
3. 擴大 Br 真實資料（四元系統 / 放寬 e_above_hull）再推 R²。

文件索引見 `docs/README.md`；模型卡見 `MODEL_CARD.md`；能力與限制見
`docs/CAPABILITY_STATEMENT.md`。
