# Alloy Discovery Engine

工業廢熱消磁合金 GPU 加速虛擬高通量篩選引擎。

尋找滿足下列條件的合金配方：
- 居禮溫度 (Tc) 落在工業廢熱範圍（150 / 350 / 500°C）
- 矯頑力 (Hc) 與剩磁 (Br) 越低越好（軟磁特性）
- 降伏強度 σy ≥ 設定下限（保留機械強度）

## Quick Start

```bash
pip install -r requirements.txt
python scripts/train_surrogate.py
python scripts/run_search.py --scenario all
```

結果輸出至 `results/`：
- `top_alloy_candidates.csv` — 各情境前 10 名配方
- `ga_convergence.png` — 收斂曲線
- `top_compositions.png` — 配方熱圖

## 目錄結構

```
alloy_engine/          # 核心套件
  config.py            # 裝置、路徑、超參數預設值（改這裡切 CPU/GPU 或調路徑）
  data/
    elements.py        # 元素物理性質表（9 種屬性，已移除 Tc leakage）
    synthetic.py       # 稀疏 Dirichlet 合成訓練資料生成
  features/
    engineering.py     # Oliynyk 特徵工程（GPU 與 numpy 兩版）
  models/
    surrogate.py       # PropertyMLP + SurrogateBundle（訓練/推論/checkpoint）
    MODEL_CARD.md      # 模型詳細說明、驗證結果、已知限制
    checkpoints/       # 訓練好的模型權重（git-ignored）
  ga/
    gpu_ga.py          # GPU 向量化基因演算法（含化學約束）
  scenarios.py         # 三種廢熱情境設定
  visualization.py     # 收斂曲線與配方熱圖

scripts/
  train_surrogate.py   # 訓練 MLP，支援 --n-samples / --epochs / --seed / --output
  run_search.py        # 跑 GA 搜尋，支援 --scenario / --population-size / --n-generations

external/
  NEMAD/               # NEMAD 磁性材料資料庫（git-ignored）
```

## CLI 參數

### train_surrogate.py

| 參數 | 預設 | 說明 |
|---|---|---|
| `--n-samples` | 8000 | 訓練樣本數 |
| `--epochs` | 300 | 訓練週期 |
| `--seed` | 42 | 隨機種子 |
| `--output` | `models/checkpoints/bundle.pt` | checkpoint 輸出路徑 |

### run_search.py

| 參數 | 預設 | 說明 |
|---|---|---|
| `--scenario` | all | `低溫廢熱_150C` / `中溫廢熱_350C` / `高溫廢熱_500C` / `all` |
| `--population-size` | 200000 | GA 族群大小 |
| `--n-generations` | 150 | 演化世代數 |
| `--checkpoint` | `models/checkpoints/bundle.pt` | 模型路徑 |
| `--output-dir` | `results/` | 輸出目錄 |
| `--no-chemistry-constraints` | False | 停用化學可合成性懲罰（對照實驗用） |
| `--diversity-filter` | False | 啟用 K-means 多樣性篩選 |

## Final Results (v2.0)

### 三廢熱情境最佳配方

| 情境 | 目標 Tc | 最佳配方（at%） | 預測 Tc | Fitness |
|------|---------|---------------|---------|---------|
| 低溫廢熱 | 150°C | Fe₂₄Ni₂₈Co₁₇Cr₄Si₁₈V₈ | 149.3°C | 0.8003 |
| 中溫廢熱 | 350°C | Fe₂₈Ni₃₀Co₁₈Al₆V₁₈ | 350.0°C | 0.7960 |
| 高溫廢熱 | 500°C | Fe₂₀Ni₂₄Co₃₆Mo₅V₁₅ | 497.7°C | 0.7866 |

GA 搜尋條件：100K 族群 × 150 代，化學約束啟用（DO₃/μ-phase/σ-phase/FM 基底懲罰）。

### 著名合金 Sanity Check（v2.0 模型）

| 合金 | 預測 Tc | 實驗 Tc (NEMAD) | 誤差 |
|------|--------|----------------|------|
| Permalloy Ni₈₀Fe₂₀ | 437°C | 434°C | +3°C |
| Fe₆₀Co₂₀Ni₂₀ | 746°C | 784°C | −38°C |
| Hiperco50 Fe₅₀Co₅₀ | 954°C | 1031°C | −77°C |
| Supermalloy Ni₇₉Mo₅Fe₁₆ | 372°C | 465°C | −93°C |
| Sendust Fe₈₅Si₉Al₆ | 534°C | 697°C | −163°C |
| Alnico5 Fe₅₁Co₂₄Ni₁₄Al₈Cu₃ | 613°C | 870°C | −257°C |
| Fe₆₅Ni₃₅ (Invar) | 649°C | 257°C | +392°C * |

\* Invar 磁體積異常，組成特徵無法編碼，為已知物理限制。

### NEMAD 真實資料驗證

- 資料集：618 筆篩選後 NEMAD 實驗資料（Fe/Ni/Co/Cr/Mn/Cu/Mo/Si/Al/V 十元素空間）
- 整體 R² = −0.24，MAE = 282°C
- 模型系統性高估 ~280°C（合成 Tc 公式偏差），但所有預測值在物理合理範圍內（−100 ~ 1300°C）

### 已知限制

- 系統性 Tc 高估約 280°C（合成訓練資料與真實合金的 sim-to-real gap）
- Invar 類磁體積異常合金不適用
- Mo > 5 at% 或 V > 8 at% 區域實驗資料極稀（NEMAD Mo: 9 筆，V: 47 筆），預測可信度低
- 模型假設無序固溶體，不適用有序金屬間化合物

詳見 `alloy_engine/models/MODEL_CARD.md`。

## Reproducibility

所有結果可完整重現：

```bash
# 固定 seed=42，8000 筆稀疏 Dirichlet 訓練樣本
python scripts/train_surrogate.py --n-samples 8000 --epochs 300 --seed 42

# 100K 族群 × 150 代 GA 搜尋
python scripts/run_search.py --scenario all --population-size 100000 --n-generations 150
```
