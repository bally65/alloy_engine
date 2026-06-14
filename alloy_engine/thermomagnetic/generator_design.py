"""
熱磁發電機 (Thermomagnetic Generator, TMG) 裝置層設計與推算模組
================================================================

本模組將 TMG 的設計從「材料層」延伸到「裝置層」。`properties.py` 負責
計算單一合金的循環物理量（delta_M、Cp、ρ、ΔS_M、循環頻率），本模組則
把這些材料量代入熱力學與電磁學方程式，推算整台發電機的功率密度、
效率與感應電壓，作為架構選型與尺寸設計的依據。

設計三階段（對應 README 的熱磁循環拆解）：
  1. 熱能輸入 Q_in  — 顯熱 + 磁熵潛熱
  2. 磁矩變化       — delta_M 驅動的磁功 W = μ₀ ∮ H dM
  3. 電磁功輸出     — 法拉第感應 V = -N dΦ/dt 與功率密度 P = W·f

底層方程式（與設計文件 docs/THERMOMAGNETIC_GENERATOR_DESIGN.md 對應）：

  磁功密度        w_mag = util · ΔJ · H_app          [J/m³ / cycle]
                  其中 H_app = B_app / μ₀，ΔJ = delta_M (T，即極化變化)
  熱輸入密度      q_in  = ρ·Cp·ΔT_swing·(1-ε_reg) + ρ·T_avg·ΔS_M
  材料效率        η     = w_mag / q_in
  卡諾效率        η_C   = 1 - T_cold/T_hot
  相對卡諾效率    η/η_C （無回熱 ≲0.55，回熱 ε_reg 可逼近 1）
  功率密度        p_vol = w_mag · f                  [W/m³]
  感應電壓        V_rms = k_wave · N · ΔΦ · f         （ΔΦ = ΔJ·A_core）

單位約定：沿用 repo 慣例，磁化量 delta_M / Ms / Br 皆為「磁極化」單位
(Tesla, J = μ₀M)；外加磁場以 B_app (Tesla) 表示，內部換算 H = B/μ₀。

科學依據：
  - Olsen 循環磁功面積：Solomon 1991, J. Appl. Phys. 70, 6453
  - 磁熵潛熱 ∫T dS_m ≈ T_avg·ΔS_M：Tishin & Spichkin 2003, ch.2
  - 無回熱 TMG 效率上限 ~0.55·η_C：Kishore & Priya 2018,
    Renew. Sustain. Energy Rev. 81, 33（綜述）
  - 回熱逼近卡諾：Brayton-like AMR 概念，Yu et al. 2010,
    Int. J. Refrig. 33, 1029
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

# 真空磁導率 (T·m/A)
MU_0 = 4.0e-7 * math.pi


# ───────────────────────── 階段 2：磁功輸出 ─────────────────────────
def magnetic_work_density(
    delta_M_T: float,
    B_applied_T: float = 1.0,
    cycle_utilization: float = 0.30,
) -> float:
    """
    單位體積、單一循環的磁功 w_mag (J/m³).

    理想矩形 Olsen 循環的上限為 ΔJ·H = delta_M · (B_app/μ₀)；實際 M-H
    迴線非矩形，故乘上利用率 util∈(0,1]。

    Args:
        delta_M_T:         熱磁循環淨磁極化變化 ΔJ (T)，來自 properties.delta_M
        B_applied_T:       永磁背景場 B_app (T)，NdFeB 氣隙典型 0.8–1.4 T
        cycle_utilization: 迴線面積/矩形面積比，Fe 系二階相變典型 0.2–0.4，
                           一階相變 (Gd / Heusler) 可達 0.5–0.7
    Returns:
        w_mag: J/m³ per cycle（理想上限 × util）
    """
    if delta_M_T < 0 or B_applied_T < 0:
        raise ValueError("delta_M_T 與 B_applied_T 必須為非負值")
    if not 0.0 < cycle_utilization <= 1.0:
        raise ValueError("cycle_utilization 必須落在 (0, 1]")
    H_applied = B_applied_T / MU_0          # A/m
    w_ideal = delta_M_T * H_applied          # J/m³（矩形上限）
    return cycle_utilization * w_ideal


# ───────────────────────── 階段 1：熱能輸入 ─────────────────────────
def heat_input_density(
    rho: float,
    cp_specific: float,
    delta_T_swing_K: float,
    T_avg_K: float,
    delta_S_M: float = 0.0,
    regenerator_effectiveness: float = 0.0,
) -> float:
    """
    單位體積、單一循環的熱輸入 q_in (J/m³).

    q_in = ρ·Cp·ΔT_swing·(1-ε_reg)  [顯熱，可回熱]
         + ρ·T_avg·ΔS_M             [磁熵潛熱，相變不可回熱]

    回熱器只回收顯熱（材料降溫釋放的熱預熱下一批），故僅作用在第一項。
    低溫廢熱情境下顯熱常佔 q_in 的 80–95%，因此 ε_reg 是突破
    0.55·η_C 天花板的關鍵槓桿。

    Args:
        rho:                       合金密度 (kg/m³)，properties.density_estimate
        cp_specific:               質量比熱 (J/kg·K)，properties.cp_estimate_specific
        delta_T_swing_K:           循環全溫差 T_hot - T_cold (K)
        T_avg_K:                   循環平均絕對溫度 (K)
        delta_S_M:                 磁熵變 (J/kg·K)，properties.delta_s_m_estimate
        regenerator_effectiveness: 回熱器效率 ε∈[0,1)，0=無回熱
    Returns:
        q_in: J/m³ per cycle
    """
    if not 0.0 <= regenerator_effectiveness < 1.0:
        raise ValueError("regenerator_effectiveness 必須落在 [0, 1)")
    if min(rho, cp_specific, delta_T_swing_K, T_avg_K) < 0:
        raise ValueError("熱物性與溫度輸入必須為非負值")
    sensible = rho * cp_specific * delta_T_swing_K * (1.0 - regenerator_effectiveness)
    latent = rho * T_avg_K * delta_S_M
    return sensible + latent


# ───────────────────────── 階段 4：效率推算 ─────────────────────────
def carnot_efficiency(T_cold_K: float, T_hot_K: float) -> float:
    """卡諾效率 η_C = 1 - T_cold/T_hot."""
    if T_hot_K <= 0 or T_cold_K <= 0:
        raise ValueError("溫度必須為正 (K)")
    if T_hot_K <= T_cold_K:
        raise ValueError("T_hot 必須大於 T_cold")
    return 1.0 - T_cold_K / T_hot_K


def material_efficiency(w_mag: float, q_in: float) -> float:
    """材料絕對效率 η = w_mag / q_in."""
    if q_in <= 0:
        raise ValueError("q_in 必須為正")
    return w_mag / q_in


# ───────────────────────── 階段 3：電磁功輸出 ─────────────────────────
def power_density(w_mag: float, f_Hz: float) -> float:
    """
    體積功率密度 p_vol = w_mag · f (W/m³).

    功率瓶頸不在單次磁功 (受材料 delta_M 物理上限)，而在循環頻率 f。
    f 來自 properties.cycle_frequency_estimate（熱擴散 α/2L²）。
    """
    if f_Hz < 0:
        raise ValueError("頻率必須為非負")
    return w_mag * f_Hz


def effective_frequency(f_Hz: float, f_max_Hz: float = 50.0) -> float:
    """
    工程可達頻率封頂（缺陷 D4 修復）。

    純擴散頻率 f = α/(2L²) 無上限，會讓功率密度模型「κ 永遠有益」（不物理）。
    實機在高頻受渦流損耗與換熱速率限制，故套用飽和：

        f_eff = f / (1 + f / f_max)

    低頻 f_eff≈f；高頻 f_eff→f_max（κ 邊際效益遞減到零）。

    Args:
        f_Hz:     純擴散頻率 (Hz)
        f_max_Hz: 工程上限 (Hz)，AMR/HMR 原型多在 1–10 Hz，預設 50 為寬鬆上限
    Returns:
        f_eff: 有效頻率 (Hz)
    """
    if f_Hz < 0 or f_max_Hz <= 0:
        raise ValueError("f_Hz 必須非負且 f_max_Hz 必須為正")
    return f_Hz / (1.0 + f_Hz / f_max_Hz)



def induced_voltage_rms(
    n_turns: int,
    delta_M_T: float,
    core_area_m2: float,
    f_Hz: float,
    waveform_factor: float = 1.11,
) -> float:
    """
    線圈感應電壓 V_rms (V) — 法拉第定律 V = -N dΦ/dt.

    半循環內磁通變化 ΔΦ = ΔJ · A_core（材料極化切斷/接通氣隙磁通）。
    平均 dΦ/dt ≈ ΔΦ·(2f)；對近似方波取 form factor k_wave 換算 RMS。

    Args:
        n_turns:         線圈匝數 N
        delta_M_T:       極化變化 ΔJ (T)
        core_area_m2:    磁芯/氣隙截面積 A (m²)
        f_Hz:            循環頻率 (Hz)
        waveform_factor: 波形因數，1.11≈正弦，1.0≈理想方波平均
    Returns:
        V_rms: 伏特
    """
    if min(n_turns, delta_M_T, core_area_m2, f_Hz) < 0:
        raise ValueError("感應電壓輸入必須為非負")
    delta_phi = delta_M_T * core_area_m2          # Wb (半循環磁通變化)
    v_avg = n_turns * delta_phi * 2.0 * f_Hz      # 平均感應電壓
    return waveform_factor * v_avg


# ───────────────────────── 高階設計：整機推算 ─────────────────────────
@dataclass
class TMGDesignReport:
    """單一設計點的完整推算結果。"""
    # 輸入回顯
    T_cold_C: float
    T_hot_C: float
    delta_M_T: float
    B_applied_T: float
    regenerator_effectiveness: float
    # 階段量
    w_mag_J_m3: float            # 單循環磁功密度
    q_in_J_m3: float             # 單循環熱輸入密度
    f_Hz: float                  # 循環頻率
    # 效能指標
    eta_material: float          # 材料絕對效率 W/Q
    eta_carnot: float            # 卡諾上限
    eta_relative_carnot: float   # η/η_C
    power_density_W_m3: float    # 體積功率密度
    v_rms_volts: float           # 感應電壓 (預設線圈幾何)
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            "═══════════ 熱磁發電機設計推算 ═══════════",
            f"工作區間        : {self.T_cold_C:.0f}°C → {self.T_hot_C:.0f}°C "
            f"(ΔT={self.T_hot_C - self.T_cold_C:.0f}K)",
            f"背景磁場 B_app  : {self.B_applied_T:.2f} T",
            f"循環極化變化 ΔJ : {self.delta_M_T:.3f} T",
            f"回熱效率 ε      : {self.regenerator_effectiveness:.2f}",
            "─────────── 三階段能量 ───────────",
            f"磁功密度 w_mag  : {self.w_mag_J_m3:,.0f} J/m³·cycle",
            f"熱輸入 q_in     : {self.q_in_J_m3:,.0f} J/m³·cycle",
            f"循環頻率 f      : {self.f_Hz:.3f} Hz",
            "─────────── 效能指標 ───────────",
            f"材料效率 η      : {self.eta_material * 100:.3f} %",
            f"卡諾上限 η_C    : {self.eta_carnot * 100:.2f} %",
            f"相對卡諾 η/η_C  : {self.eta_relative_carnot * 100:.1f} %",
            f"功率密度 P/V    : {self.power_density_W_m3:,.1f} W/m³",
            f"感應電壓 V_rms  : {self.v_rms_volts:.2f} V",
        ]
        if self.warnings:
            lines.append("─────────── 設計警示 ───────────")
            lines += [f"  ⚠ {w}" for w in self.warnings]
        lines.append("═" * 42)
        return "\n".join(lines)


def design_tmg(
    *,
    T_cold_C: float,
    T_hot_C: float,
    delta_M_T: float,
    rho: float,
    cp_specific: float,
    kappa: float,
    delta_S_M: float = 0.0,
    B_applied_T: float = 1.0,
    cycle_utilization: float = 0.30,
    regenerator_effectiveness: float = 0.0,
    plate_thickness_m: float = 1e-3,
    n_turns: int = 200,
    core_area_m2: float = 1e-4,
    waveform_factor: float = 1.11,
    f_max_Hz: float = 50.0,
) -> TMGDesignReport:
    """
    給定材料熱物性與裝置幾何，推算整台 TMG 的效能（單一設計點）。

    材料量 (delta_M / rho / cp_specific / kappa / delta_S_M) 可直接取自
    `properties.py` 對某合金的輸出，亦可填文獻值（如 Gd）。

    循環頻率採純擴散估計 f = α/(2L²)，α = κ/(ρ·Cp)，L = 板厚（與
    properties.cycle_frequency_estimate 一致）。

    Returns:
        TMGDesignReport
    """
    T_cold_K = T_cold_C + 273.15
    T_hot_K = T_hot_C + 273.15
    T_avg_K = 0.5 * (T_cold_K + T_hot_K)
    delta_T_swing = T_hot_K - T_cold_K

    w_mag = magnetic_work_density(delta_M_T, B_applied_T, cycle_utilization)
    q_in = heat_input_density(
        rho, cp_specific, delta_T_swing, T_avg_K,
        delta_S_M=delta_S_M,
        regenerator_effectiveness=regenerator_effectiveness,
    )
    # 熱擴散頻率 f = α / (2L²)，再套工程可達封頂（D4）
    alpha = kappa / (rho * cp_specific + 1e-9)
    f_raw = alpha / (2.0 * plate_thickness_m ** 2)
    f_Hz = effective_frequency(f_raw, f_max_Hz)

    eta_mat = material_efficiency(w_mag, q_in)
    eta_c = carnot_efficiency(T_cold_K, T_hot_K)
    eta_rel = eta_mat / eta_c

    p_vol = power_density(w_mag, f_Hz)
    v_rms = induced_voltage_rms(
        n_turns, delta_M_T, core_area_m2, f_Hz, waveform_factor
    )

    warnings_: list[str] = []
    if regenerator_effectiveness == 0.0 and eta_rel > 0.55:
        warnings_.append(
            "無回熱設計 η/η_C 超過 0.55 理論天花板——請檢查 util 或 ΔJ 是否高估"
        )
    if eta_rel > 1.0:
        warnings_.append("η 超過卡諾上限，模型輸入不物理——請檢查單位/利用率")
    if delta_M_T < 0.1:
        warnings_.append("ΔJ < 0.1 T，磁功偏低；建議選 Tc 更接近工作區的材料")
    if f_Hz < 0.05:
        warnings_.append(
            "循環頻率偏低；考慮減薄板材 (↓L) 或提高 κ 以增功率密度"
        )

    return TMGDesignReport(
        T_cold_C=T_cold_C,
        T_hot_C=T_hot_C,
        delta_M_T=delta_M_T,
        B_applied_T=B_applied_T,
        regenerator_effectiveness=regenerator_effectiveness,
        w_mag_J_m3=w_mag,
        q_in_J_m3=q_in,
        f_Hz=f_Hz,
        eta_material=eta_mat,
        eta_carnot=eta_c,
        eta_relative_carnot=eta_rel,
        power_density_W_m3=p_vol,
        v_rms_volts=v_rms,
        warnings=warnings_,
    )


@dataclass
class LayeredTMGReport:
    """分層 Tc 梯度堆疊發電床的聚合推算結果。"""
    n_layers: int
    T_cold_C: float
    T_hot_C: float
    per_layer_span_K: float             # 每層子溫差（層化的主要效率來源）
    extra_regeneration: float           # 額外固態回熱器（疊加在層化之上）
    layer_reports: list[TMGDesignReport]
    eta_material: float                 # 整床效率 ΣW/ΣQ
    eta_carnot: float
    eta_relative_carnot: float
    power_density_W_m3: float           # 體積平均功率密度
    v_rms_volts: float                  # 各層線圈串聯 → 電壓相加

    def summary(self) -> str:
        return "\n".join([
            "═══════════ 分層熱磁發電床 (Layered TMG) ═══════════",
            f"層數            : {self.n_layers}（Tc 由冷端到熱端梯度排列）",
            f"總溫差          : {self.T_cold_C:.0f}°C → {self.T_hot_C:.0f}°C",
            f"每層子溫差      : {self.per_layer_span_K:.1f} K",
            f"額外固態回熱 ε  : {self.extra_regeneration:.3f}",
            "─────────── 整床效能 ───────────",
            f"整床效率 η      : {self.eta_material * 100:.3f} %",
            f"卡諾上限 η_C    : {self.eta_carnot * 100:.2f} %",
            f"相對卡諾 η/η_C  : {self.eta_relative_carnot * 100:.1f} %",
            f"功率密度 P/V    : {self.power_density_W_m3:,.1f} W/m³",
            f"串聯電壓 V_rms  : {self.v_rms_volts:.2f} V",
            "═" * 50,
        ])


def design_layered_tmg(
    *,
    T_cold_C: float,
    T_hot_C: float,
    layer_delta_M_T: list[float],
    rho: float,
    cp_specific: float,
    kappa: float,
    delta_S_M: float = 0.0,
    B_applied_T: float = 1.0,
    cycle_utilization: float = 0.30,
    extra_regeneration: float = 0.0,
    plate_thickness_m: float = 1e-3,
    n_turns_per_layer: int = 200,
    core_area_m2: float = 1e-4,
    f_max_Hz: float = 50.0,
) -> LayeredTMGReport:
    """
    分層 Tc 梯度發電床（借鏡分層 AMR 的反向設計）。

    將總溫差均分為 N 段，每段填入 Tc 調至該段局部溫度的材料，使每層都在
    自己的最佳 delta_M 工作。**層化提升效率的主要機制是「每層只在小子溫差
    (span/N) 內循環」**——尖銳相變材料在窄溫窗即可得到完整 delta_M，卻只需
    付出 1/N 的顯熱，這正是分層 AMR 高效的根本原因。

    `extra_regeneration` 是疊加在層化之上、回收每層殘餘顯熱的「額外」固態
    回熱器（與層化本身的效益分開計，避免重複計算）。

    Args:
        layer_delta_M_T:    各層的 delta_M（長度=N），代表各層在其局部最佳
                            Tc、窄子溫窗下的循環磁化變化
        extra_regeneration: 額外固態回熱器效率 ε∈[0,1)，預設 0（純看層化效益）
        其餘參數同 design_tmg
    Returns:
        LayeredTMGReport
    """
    n = len(layer_delta_M_T)
    if n < 1:
        raise ValueError("至少需要一層")
    edges = [T_cold_C + (T_hot_C - T_cold_C) * i / n for i in range(n + 1)]
    per_layer_span = (T_hot_C - T_cold_C) / n

    reports: list[TMGDesignReport] = []
    for i, dM in enumerate(layer_delta_M_T):
        reports.append(design_tmg(
            T_cold_C=edges[i], T_hot_C=edges[i + 1],
            delta_M_T=dM, rho=rho, cp_specific=cp_specific, kappa=kappa,
            delta_S_M=delta_S_M, B_applied_T=B_applied_T,
            cycle_utilization=cycle_utilization,
            regenerator_effectiveness=extra_regeneration,
            plate_thickness_m=plate_thickness_m,
            n_turns=n_turns_per_layer, core_area_m2=core_area_m2,
            f_max_Hz=f_max_Hz,
        ))

    w_total = sum(r.w_mag_J_m3 for r in reports)
    q_total = sum(r.q_in_J_m3 for r in reports)
    eta = w_total / q_total
    eta_c = carnot_efficiency(T_cold_C + 273.15, T_hot_C + 273.15)
    p_vol = sum(r.power_density_W_m3 for r in reports) / n   # 體積平均
    v_rms = sum(r.v_rms_volts for r in reports)              # 串聯相加

    return LayeredTMGReport(
        n_layers=n,
        T_cold_C=T_cold_C,
        T_hot_C=T_hot_C,
        per_layer_span_K=per_layer_span,
        extra_regeneration=extra_regeneration,
        layer_reports=reports,
        eta_material=eta,
        eta_carnot=eta_c,
        eta_relative_carnot=eta / eta_c,
        power_density_W_m3=p_vol,
        v_rms_volts=v_rms,
    )


if __name__ == "__main__":
    # 示範：低溫廢熱情境，以 README 報告的 Fe₆₉Cr₂₁Cu₈Si₂ 代表值推算
    # （delta_M=0.20 T，Fe 系密度/比熱/熱導率代表值）
    demo = design_tmg(
        T_cold_C=120, T_hot_C=180,
        delta_M_T=0.20,
        rho=7700.0, cp_specific=460.0, kappa=109.0,
        delta_S_M=0.5,
        B_applied_T=1.0,
        cycle_utilization=0.30,
        regenerator_effectiveness=0.0,
    )
    print(demo.summary())
    print()
    print(">>> 加入 ε=0.8 固態回熱後：")
    demo_reg = design_tmg(
        T_cold_C=120, T_hot_C=180,
        delta_M_T=0.20,
        rho=7700.0, cp_specific=460.0, kappa=109.0,
        delta_S_M=0.5,
        B_applied_T=1.0,
        cycle_utilization=0.30,
        regenerator_effectiveness=0.8,
    )
    print(demo_reg.summary())
