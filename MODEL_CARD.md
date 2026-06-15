# Model Card — alloy_engine（熱磁能量轉換設計引擎）

## 概述
從元素成分到整機效能的計算設計框架：ML 代理（Tc/Hc/Br/σy）+ GPU 遺傳演算法 +
整機熱力學/電磁模型 + 製冷對偶，並以真實資料（NEMAD Tc、Materials Project 磁化）與
文獻磁熱數據校準，輸出帶不確定度。

## 預期用途
- ✅ 熱磁/磁熱材料的**相對篩選與排序**、整機設計探索、瓶頸分析、最低成本材料選擇。
- ✅ 帶誤差條的整機效能**量級/天花板**估計。
- ❌ **不**作絕對功率密度的精確預測（發電側為理想化上界，~10× 高於真實原型）。
- ❌ **不**外推到未校準的化學體系而當絕對值。

## 訓練資料
- **Tc（真實）**：NEMAD `FM_with_curie.csv`（15,577 FM 化合物；過濾到本 14 元素空間後
  1,380 筆）。執行時抓取、不入版控（repo 無 license）。
- **磁化/Br（真實）**：Materials Project DFT（266 FM 化合物，需免費 API key）→ 真實 Br
  baseline（GBR, CV R²=0.58, MAE 0.27T；見 `docs/BR_CALIBRATION.md`）。
- **Hc/σy（合成）**：物理啟發式合成資料（無對應公開資料集，待真實校準）。
- **ΔS_M / 一階銳度 w**：文獻代表值（見 `docs/LITERATURE_CALIBRATION.md`）。

## 元素空間
14 元素：Fe, Ni, Co, Cr, Mn, Cu, Mo, Si, Al, V, Gd, La, P, Ge。

## 效能與信心（詳見 `docs/CAPABILITY_STATEMENT.md`）
| 量 | 信心 | 依據 |
|---|---|---|
| 材料相對排序 | 🟢 高 | GA 行為 + 文獻 + 真實 Tc 一致 |
| Tc | 🟡🟢 | 真實 NEMAD R²=0.78、MAE 91°C |
| ΔS_M / w | 🟡 | 文獻 ±12% |
| Br | 🟡🟢 | 真實 MP 訓練 GBR R²=0.58、MAE 0.27T（vs 合成 ≤0（無預測力））|
| 整機 η | 🟡 | 對標真實原型 ~2× 內 |
| 整機絕對 P/V | 🔴 | 理想化上界，~10× 高 |

## 已知限制
- 合成 Hc/Br/σy 未對標真實量測（Br 系統性偏保守）。
- 複合 connectivity、回熱 ε、利用率為工程假設（敏感度已量化，見 `SENSITIVITY_ANALYSIS`）。
- 發電側無自有原型對標（製冷側已對標 HMR）。
- 詳見 `docs/KNOWN_DEFECTS.md`。

## 倫理/安全
- 推薦器自動排除毒性（MnAs/As）、逆磁熱、極貴（FeRh/Rh）材料。
- MP API key 為機密（git-ignored）；曾於開發中外洩者應 rotate。

## 復現
`make pipeline` / `make test` / `make figures`；CI 守護 290+ 測試。

## 版本
v1.0.0（2026）。健康度：290+ 測試 + CI + 漂移守衛 + 兩輪人工/agent 審查（近期改動 + 核心）。
