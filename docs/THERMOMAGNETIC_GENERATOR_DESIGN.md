# 熱磁發電機 (TMG) 底層數學推算與架構設計方法

> 本文件把「材料篩選引擎」(`alloy_engine`) 的輸出延伸到「整機設計」。
> 材料層回答「用哪個合金」，本文回答「這個合金能組出怎樣的發電機」。
> 對應程式碼：`alloy_engine/thermomagnetic/generator_design.py`。

---

## 0. 設計方法論：從方程式反推架構

TMG 把熱力學循環映射到磁滯迴線 (M–H curve)。我們**不從硬體開始猜**，
而是先寫下三階段的支配方程式，再讓方程式告訴我們每個設計旋鈕該往哪轉：

| 階段 | 支配方程式 | 主要設計旋鈕 |
|------|-----------|-------------|
| ① 熱能輸入 Q_in | `q_in = ρ·Cp·ΔT·(1-ε) + ρ·T·ΔS_M` | 低 Cp 材料、回熱器 ε |
| ② 磁矩變化 (磁功) | `w = util·ΔJ·(B_app/μ₀)` | 陡峭 M(T) → 大 ΔJ、強永磁 B_app |
| ③ 電磁功輸出 | `V = -N·dΦ/dt`、`P = w·f` | 高匝數 N、聚磁、高頻率 f |

設計即是在 `η = w/q_in` 與 `P = w·f` 兩個目標間，用上表旋鈕做最佳化。

---

## 1. 底層數學模型

### 1.1 磁熱馬克士威關係式（選材最高準則）

$$\left(\frac{\partial M}{\partial T}\right)_H = \left(\frac{\partial S}{\partial H}\right)_T$$

材料在固定場下「磁化對溫度的變化率」等於「磁熵對磁場的變化率」。
工程意涵：要在居禮溫度 $T_c$ 附近有**陡峭的 M(T) 下降曲線**，才能同時
得到大的 $\partial M/\partial T$（→ 大 ΔJ）與大的磁熵變 ΔS_M。一階相變材料
（Gd、Ni-Mn 基 Heusler）的曲線最陡，是首選。

→ 程式中 ΔJ 由 `properties.magnetic_thermodynamic_score()['delta_M']` 提供，
ΔS_M 由 `properties.delta_s_m_estimate()` 提供。

### 1.2 磁功輸出

$$W = \mu_0 \oint H\,dM = -\mu_0 \oint M\,dH$$

單次循環磁功 = M–H 平面上冷端/熱端兩條等溫線所圍面積。理想矩形
（熱端磁性歸零、冷端飽和）給出上限。本 repo 以磁極化單位
$J = \mu_0 M$（Tesla）記錄磁化量，故每單位體積：

$$w_{\text{mag}} = \text{util}\cdot \Delta J \cdot H_{\text{app}}, \quad H_{\text{app}} = \frac{B_{\text{app}}}{\mu_0}$$

`util`∈(0,1] 是「實際迴線面積 / 矩形上限」的利用率：Fe 系二階相變
0.2–0.4，一階相變可達 0.5–0.7。→ `magnetic_work_density()`

### 1.3 熱能輸入

$$Q_{\text{in}} = \rho\!\int_{T_c}^{T_h}\! C_p(T)\,dT + \int T\,dS_m$$

離散化為「顯熱 + 磁熵潛熱」：

$$q_{\text{in}} = \underbrace{\rho\,C_p\,\Delta T_{\text{swing}}(1-\varepsilon)}_{\text{顯熱（可回熱）}} + \underbrace{\rho\,T_{\text{avg}}\,\Delta S_M}_{\text{磁熵潛熱}}$$

**關鍵洞察**：低溫廢熱下顯熱常佔 q_in 的 80–95%，磁功只佔分母的萬分之幾，
所以效率瓶頸是「把材料整塊加熱」這件事。降低 $C_p$ 與引入回熱器 $\varepsilon$
（只能回收顯熱）是唯二槓桿。→ `heat_input_density()`

### 1.4 效率極限

$$\eta = \frac{W}{Q_{\text{in}}}, \qquad \eta_{\text{Carnot}} = 1 - \frac{T_c}{T_h}$$

無回熱標準 TMG 的理論上限約為 $0.55\,\eta_{\text{Carnot}}$（顯熱完全回收的
理想假設下）。實務上若顯熱未回收，$\eta/\eta_C$ 會遠低於此值——這正是
下節推算所揭示的。導入固態回熱器後，顯熱項被 $(1-\varepsilon)$ 壓低，
$\eta/\eta_C$ 才有機會逼近 1。→ `material_efficiency()` / `carnot_efficiency()`

### 1.5 功率密度與感應電壓

$$P = W\cdot f \;[\text{W/m}^3], \qquad V = -N\frac{d\Phi}{dt},\;\; \Delta\Phi = \Delta J\cdot A_{\text{core}}$$

單次磁功有材料物理上限，**提高總輸出的唯一解是提高頻率 f**。
$f = \alpha/(2L^2)$，熱擴散率 $\alpha = \kappa/(\rho C_p)$，$L$=板厚。
減薄板材、選高 κ 材料 → 高頻 → 高功率密度。
→ `power_density()` / `induced_voltage_rms()`

---

## 2. 推算結果（代表設計點）

以 README 報告的低溫廢熱最佳配方 **Fe₆₉Cr₂₁Cu₈Si₂**（ΔJ=0.20 T，
κ=109 W/mK）為代表，工作區間 120→180°C、B_app=1 T、util=0.30、
板厚 1 mm：

| 指標 | 無回熱 (ε=0) | 固態回熱 (ε=0.8) |
|------|-------------|-----------------|
| 磁功密度 w_mag | 47,746 J/m³·cycle | （同左，與熱無關）|
| 熱輸入 q_in | 2.14×10⁸ J/m³ | 4.41×10⁷ J/m³ |
| 循環頻率 f | 15.4 Hz | 15.4 Hz |
| 材料效率 η | **0.022 %** | **0.108 %** |
| 卡諾上限 η_C | 13.24 % | 13.24 % |
| 相對卡諾 η/η_C | 0.2 % | 0.8 % |
| 功率密度 P/V | 7.3×10⁵ W/m³ | 7.3×10⁵ W/m³ |
| 感應電壓 V_rms | 0.14 V | 0.14 V |

**推算結論**：

1. **效率被顯熱完全主導**。q_in ≈ 2×10⁸ J/m³ 幾乎全來自 `ρ·Cp·ΔT`，
   磁功只有 ~5×10⁴ J/m³，相差約 4500 倍 → η 僅 0.02%。這證實了
   方程式 §1.3 的洞察：**TMG 的死穴不是磁功太小，而是要把整塊金屬反覆加熱。**
2. **回熱器是效率的主槓桿**。ε=0.8 把顯熱砍掉 80%，η 與 η/η_C 同步約 ×5。
   要逼近 0.55·η_C 天花板，需要 ε≳0.97 等級的高效固態回熱。
3. **功率密度尚可，效率很差**。15 Hz × 4.8×10⁴ J/m³ ≈ 0.73 MW/m³ 的體積
   功率密度在廢熱回收屬可接受，但 0.02–0.1% 的效率說明：**Fe 系 ΔJ=0.2 T
   材料適合「免費廢熱、重功率密度」場景，不適合追求高轉換效率。**
4. 想要量級提升，方程式指向兩條路：(a) 換 ΔJ→0.5–1 T 的一階相變/稀土
   材料（直接放大分子 w_mag）；(b) 降 Cp + 高 ε 回熱（壓低分母 q_in）。

---

## 3. 基於推算的架構設計方案

| 層 | 設計邏輯（方程式依據） | 硬體配置 |
|----|----------------------|---------|
| **核心材料層**<br>磁路開關 | `w=util·ΔJ·H`：材料當「快切磁開關」而非笨重磁軛 | Gd / Ni-Mn Heusler 薄片或多孔燒結，↑比表面積→↑dT/dt |
| **磁路拓樸層**<br>聚磁閉環 | `V=-N·dΦ/dt`：讓 Φ 變化最劇烈 | NdFeB Halbach 陣列提供穩定 B_app，材料置於氣隙；加熱失磁=切斷磁通，冷卻復磁=接通，外繞 N 匝銅線圈 |
| **熱流動態層**<br>高頻 + 回熱 | `P=w·f`、`q_in` 顯熱項 | 強制微通道熱交換器使冷/熱水高頻交替沖刷；固態混合回熱回收顯熱 ε，突破 0.55·η_C |

**總結方案**：低熱容巨磁熱材料作高頻磁開關 + 優化永磁閉環陣列 +
主動式流體回熱循環。鎖定 100°C 以下低溫工業廢熱（全球廢熱 ~65%），
用最少材料截取最大 $\mu_0\oint H\,dM$ 面積，換取高功率密度。

---

## 4. 與材料引擎的串接

```python
import torch
from alloy_engine.thermomagnetic import properties as P
from alloy_engine.thermomagnetic.generator_design import design_tmg

comp = torch.tensor([[0.69, 0, 0, 0.21, 0, 0.08, 0, 0.02, 0, 0]])  # Fe69Cr21Cu8Si2
Ms, Tc_K = torch.tensor([1.0]), torch.tensor([448.15])             # 來自 surrogate
mag = P.magnetic_thermodynamic_score(Ms, Tc_K, T_target_C=150)
rep = design_tmg(
    T_cold_C=120, T_hot_C=180,
    delta_M_T=float(mag["delta_M"]),
    rho=float(P.density_estimate(comp)),
    cp_specific=float(P.cp_estimate_specific(comp)),
    kappa=float(P.thermal_conductivity_estimate(comp)),
    regenerator_effectiveness=0.8,
)
print(rep.summary())
```

## 5. 模型限制

- `util` / `ε` 為設計假設值，非第一原理推導；實機需由 M-H 迴線量測校準。
- 顯熱主導下 η 對 Cp、ΔT_swing 極敏感，絕對值僅供量級判斷與相對比較。
- 頻率 f 採純擴散估計，忽略對流換熱與機構慣性，為上限值。
- ΔS_M、ΔJ 繼承 `properties.py` 的 Fe-Ni 系校準限制（見 MODEL_CARD.md）。
