# 熱磁發動機合金虛擬高通量篩選

工業廢熱 Curie 馬達合金 GPU 加速虛擬高通量篩選引擎。

尋找滿足下列條件的合金配方：
- 居禮溫度 (Tc) 落在工業廢熱範圍（150 / 350 / 500°C），偏高 +20~30K 為工程最佳區
- 熱磁循環淨磁化變化 (delta_M = M(T-30K) - M(T+30K)) 最大化（Olsen 循環能量代理）
- 熱導率 (κ) 足夠（促進循環頻率），合理上限 130 W/mK
- 降伏強度 σy ≥ 150 MPa（薄片感應器用途）

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

## Final Results

### 熱磁模式 (mode=thermomagnetic, v4.1)

GA 以 Olsen 循環能量最大化為主要目標（delta_M + tc_window_score），並施加 Cu 含量與 delta_M 硬約束。

| 情境 | 目標 Tc | 最佳配方（at%） | Tc 偏差 | delta_M | kappa | 工業類比 |
|------|---------|---------------|---------|---------|-------|---------|
| 低溫廢熱 | 150°C | Fe₆₉Cr₂₁Cu₈Si₂ | +15°C | 0.20 T | 109 W/mK | Silicon Steel 系 |
| 中溫廢熱 | 350°C | Fe₇₇Cr₁₁Cu₁₀Mo₁Mn₁ | +23°C | 0.20 T | 115 W/mK | Fe-Cr 軟磁 |
| 高溫廢熱 | 500°C | Fe₈₃Cu₁₁Cr₄Mn₁ | +24°C | 0.20 T | 115 W/mK | 高溫 Fe-Cu 合金 |

GA 搜尋條件：100K 族群 × 150 代，化學約束啟用（DO₃/μ-phase/σ-phase/FM 基底/Cu 反稀釋懲罰）。

### 軟磁模式 (mode=softmag, v3.x 行為)

低矯頑力、低剩磁最佳化，適合磁心材料。詳見 v3.0 release notes。

| 情境 | 目標 Tc | 最佳配方（at%） | 預測 Tc | Fitness |
|------|---------|---------------|---------|---------|
| 低溫廢熱 | 150°C | Fe₂₀Ni₂₄Co₁₆Cr₁₀Si₁₉V₇Mn₃Mo₁ | 149.9°C | 0.8048 |
| 中溫廢熱 | 350°C | Fe₂₄Ni₂₇Co₁₉Si₂₀V₆Cr₃Mn₁ | 350.1°C | 0.8012 |
| 高溫廢熱 | 500°C | Fe₂₁Ni₂₅Co₃₁V₂₀Mo₂Cr₁ | 498.5°C | 0.7926 |

### 已知限制

- Tc 系統性偏差仍存在（NEMAD sim-to-real gap，MAE ~239°C）
- delta_M = 0.20 T 受元素空間限制，工業 Gd 可達 0.6 T
- 無稀土元素（Gd/Tb/Dy），低溫熱磁應用受限
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
