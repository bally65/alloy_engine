# 真實資料調研與比較評估（Data Sourcing Assessment）

> 任務：手上沒有資料 → 調研網路上有哪些好資料可拿來與本引擎的「合成資料」
> 比較，並評估 GitHub Actions（GHA）上可輔助的自動化方案。本文為「先評估」
> 的成果，含**已實測的 sim-to-real 落差數字**。

---

## 0. 重大發現：資料其實「拿得到」

本引擎腳本期望的 NEMAD `FM_with_curie.csv` **就在公開 GitHub repo
[`sumanitani/NEMAD-MagneticML`](https://github.com/sumanitani/NEMAD-MagneticML)**，
且本環境的 GitHub raw 可連線。已實測下載成功：

- **15,577 筆鐵磁化合物**、8.3 MB、欄位 `Normalized_Composition, Mean_TC_K,
  H…全週期表（含 La/Ce/Pr/Nd/Gd 稀土）`，**與我們腳本期望完全吻合**。
- ⚠️ repo **無 LICENSE 檔**（授權未標明）→ 不可 redistribute / commit 進本
  repo；採「執行時抓取」+ 引用 NEMAD（Nature Comms 2025）。資料已放
  `external/`（git-ignored，不會進版控）。

→ **這把缺陷 D1（真實 Tc）從「⛔ 被阻擋」改判為「✅ 現在就能做」。**

---

## 1. 已實測：合成 vs 真實的落差（最有力的評估）

把本引擎 12 元素合成代理拿去對標 NEMAD 真實 Tc（`scripts/nemad_eval.py`，
稀土感知清理後 n=1,014 筆）：

| 子集 | R² | MAE |
|---|---|---|
| 整體 (n=1014) | **−0.17** | **274°C** |
| 100–200°C 目標帶 | −115.8 | 279°C |
| 300–400°C 目標帶 | −171.5 | 315°C |
| 500–700°C 目標帶 | −34.1 | 218°C |

**R² 為負 → 合成代理在真實資料上比「直接猜平均」還差**。這是 D1 的硬證據。

名材抽查（pred vs NEMAD 真值）：Fe-Co 系尚可（Hiperco50 err −19°C、
Permalloy +30°C），但稀土/特殊系崩潰——**La-Fe-Si 預測 +463°C，NEMAD 真值
−57°C，誤差 +520°C**；Invar Fe65Ni35 +420°C。這同時是 **D2（稀土外推不可信）
的硬證據**，且證明 NEMAD 內就有正確的 La-Fe-Si Tc（≈216K）可用來修正。

---

## 2. 可用資料目錄（與本引擎的關係）

| 資料源 | 內容 | 可得性 | 解哪個缺陷 |
|---|---|---|---|
| **NEMAD `FM_with_curie.csv`** | 15,577 FM 化合物 + Curie 溫度（含稀土）| ✅ 已驗證可抓 | **D1**（真實 Tc）|
| NEMAD 全庫（[nemad.org](https://www.nemad.org)，67k 筆，含 Néel）| FM+AFM、相變溫度、結構 | 網站/論文 | D1 擴充 |
| 精選 2,504 筆 Curie 資料集（arXiv 2509.17464）| 高信心清理過 | GitHub 公開 | D1 對照 |
| **Materials Project**（`total_magnetization`, `ordering`）| DFT 磁化/磁序 | ⚠️ 需免費 API key | **D3**（真實 Br/delta_M）|
| LLM 自動生成磁熱資料庫（AIP Advances 2024）| ΔS_M / ΔT_ad | 論文附件 | D5 銳度校準、D12 |

**唯一真正卡點**：D3 的真實磁化要 Materials Project，需**你註冊一個免費 MP
帳號拿 API key**（資料本身免費，但 API 要 key）。

---

## 3. 比較運作（我們已備好的管線）

PR #5 已把兩支腳本修成支援 12 元素 + 保留稀土：
- `scripts/nemad_eval.py`：合成代理 vs 真實 Tc 的 sim-to-real 對標（上節數字即此產出）。
- `scripts/train_surrogate_nemad_baseline.py`：用真實 Tc 直接訓練基準模型，
  量出「真實資料能達到的 R²」，作為是否全面切換真實資料的依據。

只要 CSV 在 `external/NEMAD/Dataset/`（已驗證可自動抓），兩者立即可跑。

---

## 4. GHA 輔助方案（可自動化的調研/比較）

| 方案 | 做法 | 價值 |
|---|---|---|
| **A. 排程資料對標** | cron workflow：`actions/cache` 快取 NEMAD CSV → 跑 `nemad_eval.py` → sim-to-real R²/MAE 圖存 artifact | 自動追蹤真實落差，**不需 commit 資料**（繞過授權）|
| **B. 連續基準** | [`benchmark-action/github-action-benchmark`](https://github.com/benchmark-action/github-action-benchmark)：追蹤 surrogate 真實 R²/MAE 隨 commit 變化，回歸超閾值即標記 | 防止模型退步 |
| **C. 資料完整性** | `upload-artifact` 內建 SHA256 digest + pandas 欄位/範圍驗證 step | 確保抓到的資料正確 |
| **D. MP 機密** | 若你提供 MP API key → 存 GitHub Secret，GHA 安全拉磁化資料 | 解 D3 自動化 |

**最高槓桿、現在就能做（不需你任何資料/key）**：方案 A——讓 GHA 每次/每週
自動抓公開 NEMAD + 跑對標，把「合成 vs 真實」的落差變成持續可見的指標。

---

## 5. 建議與你需要決定的事

1. **可立即做（我這邊就能）**：把方案 A 寫成 GHA workflow（排程抓 NEMAD +
   跑 `nemad_eval` + 存 artifact）；以及用真實 Tc 跑
   `train_surrogate_nemad_baseline` 量出真實基準 R²。
2. **需要你**：一個**免費 Materials Project API key**（解 D3 真實磁化/delta_M）。
3. **授權**：NEMAD repo 無 license → 我們只「執行時抓取＋引用」，不 commit 資料。
   若要正式採用，建議你到 nemad.org / Nature Comms 論文確認資料條款。

---

## Sources

- NEMAD-MagneticML GitHub（含 `FM_with_curie.csv`）：https://github.com/sumanitani/NEMAD-MagneticML
- NEMAD 論文（Nature Communications 2025）：https://www.nature.com/articles/s41467-025-64458-z ／ arXiv:2409.15675 https://arxiv.org/html/2409.15675
- 精選 Curie 資料集（arXiv 2509.17464）：https://arxiv.org/html/2509.17464
- Materials Project API（磁化/磁序）：https://docs.materialsproject.org/downloading-data/using-the-api
- github-action-benchmark：https://github.com/benchmark-action/github-action-benchmark
- GHA artifacts/快取：https://docs.github.com/actions/using-workflows/storing-workflow-data-as-artifacts
