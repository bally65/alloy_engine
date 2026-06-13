# 熱磁發電 ↔ 磁熱製冷：反向運作的對偶設計

> 本文回答「參考磁熱製冷 (MCR) 如何反向運作，來設計熱磁發電機 (TMG)」。
> 對應程式：`generator_design.py`（正向）、`magnetocaloric_refrigeration.py`（反向）。
> 兩者共用同一份材料物性（ΔS_M、Cp、ρ、Tc）與 `properties.py`。

---

## 1. 為什麼是「對偶」

TMG 與 MCR 是同一套磁熱物理、能量流方向相反的兩台機器：

| | 熱磁發電 TMG（正向） | 磁熱製冷 MCR（反向） |
|---|---|---|
| 輸入 | 熱 Q_in（廢熱） | 電磁功 W_in |
| 輸出 | 電磁功 W_out | 從冷端抽熱 Q_cold |
| 驅動 | 溫度變化 → 磁矩變化 | 磁場變化 → 磁矩變化 |
| 效能 | 效率 η = W/Q（追求 ↑） | COP = Q_cold/W（追求 ↑） |
| 上限 | 卡諾 η_C = 1 − T_c/T_h | 卡諾 COP_C = T_c/(T_h−T_c) |
| 共用 | 磁熱材料、Halbach 永磁陣列、AMR/回熱、磁滯損耗物理 | ← 完全相同 |

因為**材料與磁路完全共用**，MCR 領域數十年累積的工程數據（已商業化、有
實測原型）可以直接當作 TMG 設計的「反向參照」與校準錨點。

---

## 2. 模型對標：反向模型重現了文獻基準

`magnetocaloric_refrigeration.py` 以 La-Fe-Si 系（ΔS_M=11 J/kgK、Cp=700、
26K span、10 Hz、1.5T）推算，並對標使用者提供的 CAS 全固態 HMR（PNAS 2026）：

| 磁滯損耗 w_hyst | COP | 火用效率 ε_ex | 比冷卻功率 SCP |
|---|---|---|---|
| 50 J/kg（低磁滯一階材料） | 6.20 | **59.6 %** | **8.41 kW/kg** |
| 300 J/kg | 1.53 | 14.8 % | 5.91 kW/kg |
| 800 J/kg | 0.10 | 1.0 % | 0.91 kW/kg |

**低磁滯情況 8.41 kW/kg、ε_ex 59.6%** 與文獻 HMR 基準（8.3 kW/kg、54.2%）
量級吻合 → 模型可信。同時這張表量化證實了文獻的核心警告：
**磁滯是頭號殺手——w_hyst 從 50 升到 800 J/kg，COP 崩跌 60 倍。**

原因：在小溫差製冷下 COP_C 很高（此例 10.4），理想功輸入 w_in 只佔冷量
q_cold 的數 %（~9%）。因此任何與 w_in 同量級的磁滯損耗都會「等比例」吃掉
COP。這正對應文獻所述「磁滯熵生成 0.5%→1% 即使 COP 暴跌 50%」。

---

## 3. 反向運作帶回 TMG 的四條設計教訓

把 MCR 的工程經驗映射回發電機，得到四個可直接落到 `generator_design.py`
設計旋鈕的結論：

### 教訓一：磁滯是兩個方向共同的頭號殺手
MCR 中磁滯熱 w_hyst 同時抵銷冷量又增加耗功；TMG 中磁滯（Steinmetz
P_hyst ∝ f·Hc·Br）直接從淨輸出功扣除。→ 正向模型已用
`properties.quality_frequency_score` 懲罰 Hc·Br；**選材時低矯頑力 Hc、
窄磁滯迴線是發電與製冷雙贏**。一階相變材料 ΔS_M 大但磁滯也大，必須選
熱磁滯被壓低的配方（如文獻的 La-Ce-Fe-Si）。

### 教訓二：全固態回熱（HMR）消滅泵浦寄生損
文獻指出水基 AMR 的液壓泵浦吃掉 **50% 總功耗、貢獻 45% 不可逆熵生成**；
CAS 改用高導熱固態棒（HMR）後火用效率達 54.2%。→ 對 TMG，這驗證了
`generator_design.heat_input_density` 中**高回熱效率 ε** 的價值，並指向
**捨棄流體迴路、改用固態導熱**的架構，避免把好不容易發出的電又花在泵浦上。

### 教訓三：分層 AMR 用「Tc 梯度堆疊」拉大可用溫差
單一材料最佳磁熱響應只在 Tc 附近窄峰。文獻的 16 層 AMR（相鄰 Tc 間距
~2.5K）達無限分層 90% 冷卻功率、41K span 下 84% 卡諾 COP。→ TMG 同理：
**用一系列 Tc 漸變的合金由冷端到熱端堆疊**，讓每層都在自己最佳 Tc 工作，
把 `delta_M` 的有效溫窗從單點拓寬到整段廢熱溫區。這正是 `scenarios.py`
三種廢熱情境可以串成「分層發電床」的依據。

### 教訓四：Halbach 1.24–1.5T 是務實的背景磁場
室溫 MCR 普遍用 NdFeB Halbach 陣列達 1.24–1.5T（高溫用 SmCo）。→ 正向
`design_tmg` 預設 B_app=1.0T 偏保守，**可上調至 1.24–1.5T** 直接放大磁功
（w_mag ∝ B_app）。`OptiMag` 數位雙生（磁-熱耦合）削減 NdFeB 用量的思路
也適用於 TMG 的磁路成本優化。

---

## 4. 共用材料、雙向設計的範例

```python
import torch
from alloy_engine.thermomagnetic import properties as P
from alloy_engine.thermomagnetic.generator_design import design_tmg
from alloy_engine.thermomagnetic.magnetocaloric_refrigeration import design_refrigerator

comp = torch.tensor([[0.69, 0, 0, 0.21, 0, 0.08, 0, 0.02, 0, 0]])
Ms, Tc_K = torch.tensor([1.0]), torch.tensor([448.15])
cp  = float(P.cp_estimate_specific(comp))
dSm = float(P.delta_s_m_estimate(comp, Tc_K, 150, Ms, H_external_T=1.5))
dM  = float(P.magnetic_thermodynamic_score(Ms, Tc_K, 150)["delta_M"])

# 正向：當發電機用
gen = design_tmg(T_cold_C=120, T_hot_C=180, delta_M_T=dM,
                 rho=float(P.density_estimate(comp)), cp_specific=cp,
                 kappa=float(P.thermal_conductivity_estimate(comp)),
                 delta_S_M=dSm, B_applied_T=1.5, regenerator_effectiveness=0.8)

# 反向：同一材料當製冷機用
fri = design_refrigerator(T_cold_C=-3, T_hot_C=23, delta_S_M=dSm,
                          cp_specific=cp, B_applied_T=1.5,
                          f_Hz=10.0, hysteresis_loss_J_kg=50.0)
print(gen.summary()); print(fri.summary())
```

## 5. 模型限制

- MCR 模型的 `utilization` / `hysteresis_loss` 為設計輸入，需由 M-H 迴線量測
  與 AMR 實驗校準；絕對值僅供量級判斷。
- ΔT_ad、ΔS_M 繼承 `properties.py` 的 Fe-Ni 系校準（見 MODEL_CARD.md），
  Gd / La-Fe-Si / Mn-Fe-P / 稀土系需重新校準 `field_scaling`。
- 不含一階相變的熱磁滯遲滯回線形狀，僅以單一 w_hyst 標量近似。
- 超低溫量子製冷（如 EuCo₂Al₉ 自旋超固體，106 mK）屬不同物理區間，
  本模型（室溫平均場）不適用。
