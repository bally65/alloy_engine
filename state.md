# 專案狀態（state.md）

> 熱磁能量轉換材料與整機計算設計引擎（alloy_engine）的單一真實狀態文件——
> 設計成「即使對話記憶遺失，讀此檔即可接手」。最後更新：2026-06-15（main @ PR #24 後）。

---

## 1. 進度總結

從「熱磁合金材料篩選器」擴展為**成分 → AI 預測 → GA 搜尋 → 整機設計 → 真實資料校準 →
主動學習 → 實驗計畫**的完整框架。兩個內在磁性量（Tc、Br）已真實資料化、交叉驗證、
且實際用於預測。

| 領域 | 狀態 | 關鍵結果 |
|---|---|---|
| 整機 TMG 模型 | ✅ | 三階段（W=μ₀∮HdM / Q / η）；分層發電床；D4 頻率封頂 |
| 製冷對偶 | ✅ | 對標 CAS HMR（8.4 kW/kg、火用 59.6%）|
| ML 代理 + GPU GA | ✅ | 4-property、整機目標、化學軟約束 |
| 元素空間 | ✅ | 14 元素（Fe,Ni,Co,Cr,Mn,Cu,Mo,Si,Al,V + 稀土 Gd/La + 類金屬 P/Ge）|
| 複合材料 | ✅ | 高κ基底+高ΔM相，φ*≈0.3，增益 ×7–12 |
| **Tc 真實校準** | ✅ | NEMAD R²=**0.78**（合成 −0.17）；已烘焙進 `bundle_real_tc.pt` |
| **Br 真實校準** | ✅ | MP DFT GBR R²=**0.58**（合成 ≤0）；torch 版已烘焙進 bundle |
| Hc / σy | 🔶 維持合成 | 外在/製程主導，組成-only 本質受限（HC_SIGMA_FEASIBILITY）|
| 不確定度傳播 | ✅ | 文獻 ±12% Monte Carlo → 整機 P/V、η 帶誤差條 |
| 主動學習 / DoE | ✅(已驗) | recommend_experiments；**回顧基準顯示隨機勝出** → 定位為壓力測試，非省實驗 |
| 缺陷登錄 D1–D12 | ✅ | 全處理；Hc/σy 評估維持合成（非缺陷）|
| 對外輸出 | ✅ | 3 份簡報 + 論文初稿 + 150°C 案例 + 模型卡 + pyproject/Makefile |
| 品質 | ✅ | **303 測試通過**、CI 綠燈、漂移守衛、兩輪 code-review（近期+核心）|

---

## 2. 已確認的架構決策

1. **內在 vs 外在分界**：只對內在量（Tc、Br）做真實資料預測；外在量（Hc、σy）維持
   合成、僅作 GA 軟約束——不假裝可預測。**核心可信度原則。**
2. **真實資料不入版控**：NEMAD、MP 皆 git-ignored，執行時抓取+引用；checkpoint 亦
   git-ignored；只 commit「可復現結果（文字）」不存二進位。
3. **物性陣列以元素符號為鍵的字典建構**（按 ELEMENTS 對齊）：加元素只補鍵，缺鍵即
   KeyError——杜絕維度漂移。特徵 36 維，與元素數無關。
4. **真實模型整合 = baseline → 烘焙**：`replace_tc_head`/`replace_br_head` 換真實頭進
   `bundle_real_tc.pt`，下游用標準 `SurrogateBundle.load`（免旗標）。
   **load 由各頭 state_dict 自推 hidden**（支援異寬頭，如 Br=64/Tc=128）。
5. **裝置自動選擇**：CUDA → MPS（Apple Silicon）→ CPU，`ALLOY_DEVICE` 可覆寫。
6. **絕對值誠實折減**：發電側絕對 P/V 為理想化上界，對標原型後套 ~10×（D12）；絕對
   輸出帶 ±12% 誤差條。
7. **單一真實來源 + 漂移守衛**：reference_materials 的 ΔS_M/Tc 與 literature_mce 對齊，
   測試強制一致。
8. **誠實優先**：負面結果（合成 sim-to-real、AL 輸給隨機、絕對值上界）一律據實記錄。
9. **流程**：固定分支 `claude/thermomagnetic-generator-design-qvi4bw`，每批開 draft PR、
   CI 綠燈後合併（截至 PR #24）。

---

## 3. 建置狀態：無編譯錯誤
- `py_compile` 全 `alloy_engine/` + `scripts/`：**零錯誤**。
- 測試：**303 項全通過**（`python -m pytest tests/`）。CI（tests.yml）綠燈。
- `pip install -e .` 可用（pyproject.toml）。

### 已知限制（物理/資料本質，非錯誤）
- Hc/σy 為合成（外在主導，無乾淨公開資料）。
- 整機絕對 P/V 為上界（~10× 高）；相對結論可信。
- Br R²=0.58 中等（金屬磁化真實資料僅 266 筆）。
- **未經實體實驗驗證**（最大缺口）——須鑄樣量測（MEASUREMENT_PROTOCOL.md）。
- 執行期需 NEMAD CSV（公開可抓）+ MP key；checkpoint ephemeral，用
  `run_full_pipeline.sh` / CI 重生。`LinAlgWarning` 為良性。

---

## 4. 檔案地圖（恢復用）

**核心程式** `alloy_engine/`：
- `thermomagnetic/`：generator_design（整機）、magnetocaloric_refrigeration（製冷）、
  composite（複合）、properties（物性）、reference_materials、reference_devices（D12）、
  literature_mce（文獻+成本）、magnetization_correction（溫度修正）、recommend、uncertainty。
- `models/`：surrogate（4-MLP bundle）、hybrid（真實Tc包裝）、real_br（MP Br GBR）。
- `ga/`：gpu_ga（GA）、active_learning（DoE）。
- `data/`：elements（14元素）、synthetic（物理啟發合成）。

**關鍵腳本** `scripts/`：train_surrogate、train_surrogate_nemad_baseline、
build_mp_magnetization_dataset、train_br_mp_baseline、bake_real_tc、run_search、
run_full_pipeline.sh、recommend_material、recommend_experiments、
active_learning_benchmark、make_*_ppt/charts（簡報）。

**知識文件** `docs/`（索引見 `docs/README.md`）：KNOWN_DEFECTS、CAPABILITY_STATEMENT、
PIPELINE_REPORT、DATA_SOURCING_ASSESSMENT、LITERATURE_CALIBRATION、BR_CALIBRATION、
HC_SIGMA_FEASIBILITY、CALIBRATED_PREDICTION、SENSITIVITY_ANALYSIS、ACTIVE_LEARNING、
MEASUREMENT_PROTOCOL、PAPER_DRAFT/OUTLINE、設計案例 case_study/、SESSION_LOG。
**模型卡** `MODEL_CARD.md`。

**簡報/交付**：`docs/熱磁專案_白話入門.pptx`（新手白話 22 頁）、
`docs/熱磁發電機_研究簡報.pptx`（技術 30 頁）、
`docs/實驗驗證計畫_簡報.pptx` + `_詳細需求.docx`（實驗計畫）。

---

## 5. 下一步（皆需實體實驗或外部資源）
1. 鑄一個 GA 候選（如 150°C 案例的 Fe-Ni-Co），實測 Tc/Br 驗證模型（打破「未驗證」）。
2. 整機 TMG 原型，錨定發電側絕對 P/V、η。
3. 擴大 Br 真實資料再推 R²。

> 計算可做的範圍已大致走完；剩下本質上需實體量測。一鍵復現：`make pipeline` / `make test`。
