# 生產級管線結果（Production Pipeline Report）

> 由 `scripts/run_full_pipeline.sh` 跑出的「正式版」數字（生產級 8000 樣本 / 300
> epochs，14 元素含 P/Ge）。checkpoint 為二進位、git-ignored、且容器 ephemeral，
> 故此處**以可復現的文字結果保存**；任何人 `bash scripts/run_full_pipeline.sh`
> 即可重生。最近一次：2026-06-15（CPU）。

---

## 1. 合成代理（4 property heads，合成 held-out R²）

| 屬性 | best R² |
|---|---|
| Tc (K)   | 0.990 |
| Hc (A/m) | 0.856 |
| Br (T)   | 0.962 |
| σy (MPa) | 0.935 |

> 註：此為**合成資料內**的 R²（學會合成物理），非真實可信度；真實 Tc 見下節。

## 2. 真實 NEMAD Tc baseline（P/Ge 擴張後）

| 指標 | 1,014-set（12 元素）| **1,380-set（14 元素, 含 P/Ge）** |
|---|---|---|
| 整體測試 R² | 0.88 | **0.78** |
| MAE | 81°C | **91°C** |
| 樣本（過濾後）| 1,014 | **1,380（+366）** |

**誠實發現**：把 P/Ge 解鎖的 +366 筆化合物（Fe-P、Mn-Fe-P、La-Fe-Si-Ge 等）納入後，
真實 Tc baseline R² 由 0.88 **降到 0.78**——更廣的化學空間更難擬合，是覆蓋率與
精度的權衡。但相對合成代理的 **R²=−0.17** 仍是壓倒性改善，且涵蓋了真正重要的
一階 MCE 體系。窄帶子集（n=5–12）R² 為負屬樣本太少，以整體 0.78 為準。

## 3. 烘焙統一 bundle（D2）

- Tc 平均變動 **82.5 K**（合成 Tc 與真實的系統差）；Hc/Br/σy 不變 ✅
- 產出 `bundle_real_tc.pt`：真實 Tc(R²=0.78) + 合成 Hc/Br/σy，下游免 `--hybrid-tc`。

## 4. 真實 Br vs MP（溫度修正，D3）

| 對標 | MAE | bias |
|---|---|---|
| 對 MP 0K（raw） | 0.48 T | **−0.47 T** |
| 對 MP@300K（溫度修正）| 0.61 T | **−0.12 T** |

→ 與先前一致（−0.50→−0.15 量級）：原偏差多為 0K-vs-室溫的溫度差，非系統性低估。

## 5. 發電側對標真實 TMG 原型（D12）

- 同頻對標（有報告頻率 n=3）：本引擎 P/V 高估 ≈ **19×**（10–56×）；最乾淨直接實測
  （Nat. Commun. 2023）為 **~10–12×**。效率 ~2× 內同量級。
- 結論不變：發電側絕對功率密度為**理想化上界**，宜作相對比較與天花板估計。

---

## 復現

```bash
bash scripts/run_full_pipeline.sh                 # 生產級（8000/300）
N_SAMPLES=4000 EPOCHS=80 bash scripts/run_full_pipeline.sh   # 快速版
ALLOY_DEVICE=cpu bash scripts/run_full_pipeline.sh           # 強制 CPU（M5 預設用 MPS）
```

- **Mac M5**：自動使用 MPS（Apple Silicon GPU）；checkpoint 存
  `alloy_engine/models/checkpoints/`，你本機保留。
- **不想本地跑**：手動觸發 GitHub Actions `retrain-pipeline`，CI 當算力、
  把 checkpoint + 本報告上傳成 artifact（30 天）。
