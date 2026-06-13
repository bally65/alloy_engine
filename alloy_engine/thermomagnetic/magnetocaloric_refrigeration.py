"""
磁熱製冷 (Magnetocaloric Refrigeration, MCR) — 熱磁發電的「反向運作」設計模組
=========================================================================

熱磁發電機 (TMG, generator_design.py) 與磁熱製冷機 (MCR) 是同一套物理的
**熱力學對偶 (thermodynamic dual)**：共用磁熱材料、Halbach 永磁陣列、
AMR/回熱架構與磁滯損耗物理，只是能量流方向相反。

    熱磁發電 (正向)：熱 Q_in  ──磁矩變化──▶ 電磁功 W_out      (η = W/Q)
    磁熱製冷 (反向)：電磁功 W_in ──磁矩變化──▶ 從冷端抽熱 Q_cold (COP = Q_cold/W)

本模組把使用者提供的 MCR 文獻（AMR / 分層 AMR / 全固態 HMR / 磁滯損耗）
落成可計算模型，目的有二：
  1. 讓同一份材料物性（ΔS_M、Cp、ρ、Tc）能同時設計「發電」與「製冷」。
  2. 把 MCR 成熟的工程教訓（磁滯是頭號殺手、全固態 HMR 消除泵浦寄生損、
     分層 AMR 拉大溫差）反饋回 TMG 設計。

核心方程式：
  絕熱溫變 (MCE 定義量)  ΔT_ad = T·|ΔS_M| / Cp
  製冷卡諾 COP           COP_C = T_cold / (T_hot - T_cold)
  單循環冷端吸熱         q_cold = util · T_cold · |ΔS_M|              [J/kg]
  理想磁功輸入           w_in   = q_cold / COP_C
  磁滯損耗 (頭號殺手)    w_hyst = μ₀ ∮ H dM_irr （以 J/kg 輸入）
  實際 COP               COP    = (q_cold - w_hyst) / (w_in + w_hyst)
  比冷卻功率             SCP    = (q_cold - w_hyst) · f               [W/kg]
  二階律(火用)效率       ε_ex   = COP / COP_C

科學依據與校準基準（皆來自使用者提供之文獻彙整）：
  - MCE / ΔT_ad / ΔS_M 基礎：Tishin & Spichkin 2003
  - AMR 架構：US Patent 4332135；分層 AMR 84% Carnot COP @ 41K span
  - 全固態 HMR：CAS, PNAS 2026 — 10 Hz 下 26K span、8.3 kW/kg、ε_ex=54.2%
  - 磁滯敏感性：磁滯熵生成 0.5%→1% 使 COP 暴跌 ~50%（高 Cp 材料 >0.04%
    即內部產熱抵銷製冷）—— 因 w_in 僅佔 q_cold 的數 %，微量磁滯即致命
"""
from __future__ import annotations

from dataclasses import dataclass, field

# 反向模組共用正向模組的常數，維持單一真實來源
from alloy_engine.thermomagnetic.generator_design import MU_0  # noqa: F401


# ───────────────────────── MCE 基礎量 ─────────────────────────
def adiabatic_temperature_change(
    T_K: float, cp_specific: float, delta_S_M: float
) -> float:
    """
    絕熱溫變 ΔT_ad (K) — 磁熱效應的定義量。

    ΔT_ad = T · |ΔS_M| / Cp

    Gd@1.5T 校驗：T=294, ΔS_M≈5, Cp≈300 → ΔT_ad≈4.9K（文獻 3–5K）。
    """
    if cp_specific <= 0 or T_K <= 0:
        raise ValueError("T_K 與 cp_specific 必須為正")
    return T_K * abs(delta_S_M) / cp_specific


def carnot_cop_cooling(T_cold_K: float, T_hot_K: float) -> float:
    """製冷卡諾 COP = T_cold / (T_hot - T_cold)."""
    if T_cold_K <= 0 or T_hot_K <= 0:
        raise ValueError("溫度必須為正 (K)")
    if T_hot_K <= T_cold_K:
        raise ValueError("T_hot 必須大於 T_cold")
    return T_cold_K / (T_hot_K - T_cold_K)


# ───────────────────────── 循環能量 ─────────────────────────
def cooling_capacity_per_cycle(
    T_cold_K: float, delta_S_M: float, utilization: float = 0.30
) -> float:
    """
    單循環冷端吸熱 q_cold (J/kg) = util · T_cold · |ΔS_M|.

    util 涵蓋等溫熵變實現比與 AMR 蓄冷效率（典型 0.2–0.4）。
    """
    if T_cold_K <= 0:
        raise ValueError("T_cold_K 必須為正")
    if not 0.0 < utilization <= 1.0:
        raise ValueError("utilization 必須落在 (0, 1]")
    return utilization * T_cold_K * abs(delta_S_M)


def ideal_work_input(q_cold: float, cop_carnot: float) -> float:
    """理想（無損）磁功輸入 w_in = q_cold / COP_C."""
    if cop_carnot <= 0:
        raise ValueError("cop_carnot 必須為正")
    return q_cold / cop_carnot


def hysteresis_penalized_cop(
    q_cold: float, w_in: float, w_hyst: float
) -> tuple[float, float, float]:
    """
    含磁滯損耗的實際效能。

    磁滯熱 w_hyst 同時 (a) 加熱材料抵銷冷量，(b) 變成額外必須付出的功：
        q_net   = q_cold - w_hyst        （淨冷量，可能為負=無法製冷）
        w_total = w_in + w_hyst
        COP     = q_net / w_total

    Returns:
        (q_net, w_total, cop)；q_net<0 時 cop 回傳 0.0（系統淨產熱）。
    """
    if w_in < 0 or w_hyst < 0:
        raise ValueError("功輸入與磁滯損耗必須為非負")
    q_net = q_cold - w_hyst
    w_total = w_in + w_hyst
    if q_net <= 0 or w_total <= 0:
        return q_net, w_total, 0.0
    return q_net, w_total, q_net / w_total


def specific_cooling_power(q_net: float, f_Hz: float) -> float:
    """比冷卻功率 SCP (W/kg) = q_net · f."""
    if f_Hz < 0:
        raise ValueError("頻率必須為非負")
    return max(q_net, 0.0) * f_Hz


# ───────────────────────── 高階設計：整機推算 ─────────────────────────
@dataclass
class MCRDesignReport:
    """單一磁熱製冷設計點的完整推算結果。"""
    T_cold_C: float
    T_hot_C: float
    delta_S_M: float
    B_applied_T: float
    delta_T_ad_K: float
    q_cold_J_kg: float
    w_hyst_J_kg: float
    q_net_J_kg: float
    f_Hz: float
    cop: float
    cop_carnot: float
    exergy_efficiency: float          # = COP / COP_C （= 相對卡諾）
    specific_cooling_power_W_kg: float
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            "═══════════ 磁熱製冷機設計推算（反向） ═══════════",
            f"工作區間        : 冷端 {self.T_cold_C:.0f}°C / 熱端 {self.T_hot_C:.0f}°C "
            f"(span={self.T_hot_C - self.T_cold_C:.0f}K)",
            f"背景磁場 B_app  : {self.B_applied_T:.2f} T",
            f"絕熱溫變 ΔT_ad  : {self.delta_T_ad_K:.2f} K",
            "─────────── 單循環能量 ───────────",
            f"冷端吸熱 q_cold : {self.q_cold_J_kg:,.0f} J/kg",
            f"磁滯損耗 w_hyst : {self.w_hyst_J_kg:,.0f} J/kg",
            f"淨冷量 q_net    : {self.q_net_J_kg:,.0f} J/kg",
            f"循環頻率 f      : {self.f_Hz:.1f} Hz",
            "─────────── 效能指標 ───────────",
            f"性能係數 COP    : {self.cop:.2f}",
            f"卡諾 COP        : {self.cop_carnot:.2f}",
            f"火用效率 ε_ex   : {self.exergy_efficiency * 100:.1f} %",
            f"比冷卻功率 SCP  : {self.specific_cooling_power_W_kg / 1000:.2f} kW/kg",
        ]
        if self.warnings:
            lines.append("─────────── 設計警示 ───────────")
            lines += [f"  ⚠ {w}" for w in self.warnings]
        lines.append("═" * 48)
        return "\n".join(lines)


def design_refrigerator(
    *,
    T_cold_C: float,
    T_hot_C: float,
    delta_S_M: float,
    cp_specific: float,
    B_applied_T: float = 1.5,
    utilization: float = 0.30,
    f_Hz: float = 10.0,
    hysteresis_loss_J_kg: float = 0.0,
) -> MCRDesignReport:
    """
    給定材料磁熵變與比熱，推算磁熱製冷機效能（單一設計點）。

    材料量 (delta_S_M / cp_specific) 可直接取自 properties.delta_s_m_estimate
    與 properties.cp_estimate_specific，與正向 TMG 設計共用同一份輸入。

    Args:
        delta_S_M:            等溫磁熵變 (J/kg·K)，1.5T 場下 Gd≈5、La-Fe-Si≈7–11
        cp_specific:          質量比熱 (J/kg·K)
        B_applied_T:          Halbach 永磁場，室溫 MCR 典型 1.24–1.5 T
        utilization:          ΔS_M 實現比 × AMR 蓄冷效率
        f_Hz:                 運作頻率（HMR 原型 10 Hz）
        hysteresis_loss_J_kg: 單循環磁滯損耗 w_hyst（一階相變材料的頭號殺手）
    """
    T_cold_K = T_cold_C + 273.15
    T_hot_K = T_hot_C + 273.15
    T_avg_K = 0.5 * (T_cold_K + T_hot_K)

    dT_ad = adiabatic_temperature_change(T_avg_K, cp_specific, delta_S_M)
    cop_c = carnot_cop_cooling(T_cold_K, T_hot_K)
    q_cold = cooling_capacity_per_cycle(T_cold_K, delta_S_M, utilization)
    w_in = ideal_work_input(q_cold, cop_c)
    q_net, _w_total, cop = hysteresis_penalized_cop(
        q_cold, w_in, hysteresis_loss_J_kg
    )
    scp = specific_cooling_power(q_net, f_Hz)
    eps_ex = cop / cop_c if cop_c > 0 else 0.0

    warnings_: list[str] = []
    span = T_hot_K - T_cold_K
    if span > dT_ad and utilization >= 1.0:
        warnings_.append("溫差超過單次 ΔT_ad，必須採用 AMR/分層蓄冷才能達成")
    if q_net <= 0:
        warnings_.append(
            "磁滯損耗已超過冷端吸熱 → 內部產熱抵銷製冷，系統無淨冷量"
        )
    elif hysteresis_loss_J_kg > 0.5 * w_in:
        warnings_.append(
            "磁滯損耗 > 50% 理想功輸入 → COP 大幅衰退；建議改用低磁滯材料"
        )
    if eps_ex > 1.0:
        warnings_.append("火用效率 > 100% 不物理 → 檢查 util 或磁滯輸入")

    return MCRDesignReport(
        T_cold_C=T_cold_C,
        T_hot_C=T_hot_C,
        delta_S_M=delta_S_M,
        B_applied_T=B_applied_T,
        delta_T_ad_K=dT_ad,
        q_cold_J_kg=q_cold,
        w_hyst_J_kg=hysteresis_loss_J_kg,
        q_net_J_kg=q_net,
        f_Hz=f_Hz,
        cop=cop,
        cop_carnot=cop_c,
        exergy_efficiency=eps_ex,
        specific_cooling_power_W_kg=scp,
        warnings=warnings_,
    )


if __name__ == "__main__":
    # 對標 CAS 全固態 HMR 基準：La-Fe-Si 系，10 Hz，~26K span
    # 目標：SCP ~8.3 kW/kg、ε_ex ~54%
    print(">>> 對標 CAS 全固態 HMR (PNAS 2026) 基準：")
    hmr = design_refrigerator(
        T_cold_C=-3, T_hot_C=23,           # 26K span
        delta_S_M=11.0, cp_specific=700.0, # La-Fe-Si @1.5T 代表值
        B_applied_T=1.5, utilization=0.30,
        f_Hz=10.0, hysteresis_loss_J_kg=50.0,  # 低磁滯一階材料
    )
    print(hmr.summary())

    print("\n>>> 磁滯敏感性示範（低磁滯 vs 高磁滯）：")
    for w_h in (50.0, 300.0, 800.0):
        r = design_refrigerator(
            T_cold_C=-3, T_hot_C=23,
            delta_S_M=11.0, cp_specific=700.0,
            f_Hz=10.0, hysteresis_loss_J_kg=w_h,
        )
        print(
            f"  w_hyst={w_h:>5.0f} J/kg → COP={r.cop:5.2f}, "
            f"ε_ex={r.exergy_efficiency*100:4.1f}%, SCP={r.specific_cooling_power_W_kg/1000:4.2f} kW/kg"
        )
