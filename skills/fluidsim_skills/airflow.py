"""
空氣側壓降與積垢風量衰退計算模組
涵蓋：翅片陣列空氣側壓降（簡化 Poiseuille 通道流）、積垢層厚度估算、風量衰退預測

物理模型說明：
  翅片間通道在居家冷氣條件下（面風速 0.5–3 m/s，翅片間距 1.5–2.5 mm）
  屬於矩形通道低速流，Re < 2300，以層流 Hagen-Poiseuille 公式為主，
  加入入口/出口損失修正（Kc + Ke ≈ 1.3 倍）。

積垢對壓降的影響：
  積垢減小有效流通截面積，等效於縮小翅片間隙。
  層流矩形通道中 ΔP ∝ 1/gap³（Poiseuille），
  小量積垢可大幅提高壓降。
"""
import math
from dataclasses import dataclass, field
from typing import List


# 空氣物性查表（近似值，1 atm）
_AIR_TABLE = {
    # T(°C): (density kg/m³, dynamic_viscosity Pa·s, Pr, k W/m·K)
     0: (1.293, 1.716e-5, 0.715, 0.02364),
    10: (1.247, 1.761e-5, 0.713, 0.02442),
    20: (1.204, 1.808e-5, 0.713, 0.02514),
    25: (1.184, 1.849e-5, 0.713, 0.02551),
    30: (1.165, 1.872e-5, 0.712, 0.02588),
    40: (1.127, 1.906e-5, 0.711, 0.02660),
    50: (1.093, 1.963e-5, 0.710, 0.02793),
}

# 積垢層等效熱傳導率（W/m·K）
_K_DEPOSIT = {
    'dust':    0.12,   # 灰塵層（疏鬆）
    'grease':  0.18,   # 油脂層（較緻密）
    'biofilm': 0.60,   # 生物膜（含水，近似水的 k）
    'scale':   1.20,   # 礦物水垢（致密）
}
_K_DEPOSIT_DEFAULT = 0.15  # 混合積垢預設


@dataclass
class AirProperties:
    temperature_C: float
    density: float           # kg/m³
    dynamic_viscosity: float # Pa·s
    kinematic_viscosity: float  # m²/s
    prandtl: float
    thermal_conductivity: float  # W/m·K


@dataclass
class AirflowResult:
    """空氣側壓降與風量衰退分析結果"""
    face_velocity_ms: float         # 面風速 (m/s)
    max_velocity_ms: float          # 最小截面風速 (m/s)
    reynolds_number: float          # 基於水力直徑
    pressure_drop_clean_pa: float   # 乾淨翅片空氣側壓降 (Pa)
    pressure_drop_fouled_pa: float  # 積垢後壓降 (Pa)
    pressure_increase_pct: float    # 壓降增幅 (%)
    airflow_reduction_pct: float    # 同等風機壓力下風量衰退 (%)
    fouling_layer_um: float         # 積垢層估算厚度 (μm)，每側
    effective_gap_mm: float         # 積垢後有效翅片間距 (mm)
    power_increase_pct: float       # 維持原風量所需額外風機功率 (%)
    recommendation: str
    notes: List[str] = field(default_factory=list)


def air_properties(temperature_C: float = 25.0) -> AirProperties:
    """
    查表插值取得空氣物性（1 atm）。

    Args:
        temperature_C: 空氣溫度 (°C)，有效範圍 0–50°C

    Returns:
        AirProperties
    """
    t = max(0.0, min(50.0, temperature_C))
    keys = sorted(_AIR_TABLE.keys())
    for i in range(len(keys) - 1):
        t0, t1 = keys[i], keys[i + 1]
        if t0 <= t <= t1:
            frac = (t - t0) / (t1 - t0)
            d0, mu0, pr0, k0 = _AIR_TABLE[t0]
            d1, mu1, pr1, k1 = _AIR_TABLE[t1]
            density = d0 + frac * (d1 - d0)
            mu      = mu0 + frac * (mu1 - mu0)
            pr      = pr0 + frac * (pr1 - pr0)
            k       = k0  + frac * (k1 - k0)
            return AirProperties(t, density, mu, mu / density, pr, k)
    # 邊界值
    d, mu, pr, k = _AIR_TABLE[keys[-1]]
    return AirProperties(t, d, mu, mu / d, pr, k)


# 翅片幾何類型壓降修正係數
# plain=1.00, wavy ≈1.25（Wang et al. 1996）, louvered ≈1.45（Chang & Wang 1997）
_FIN_TYPE_CORRECTION: dict[str, float] = {
    'plain':    1.00,
    'wavy':     1.25,
    'louvered': 1.45,
}


def fin_channel_pressure_drop(
    face_velocity_ms: float,
    fin_pitch_mm: float,
    fin_height_mm: float,
    fin_thickness_mm: float,
    temperature_C: float = 25.0,
    fin_type: str = 'plain',
) -> tuple[float, float, float]:
    """
    翅片通道空氣側壓降（矩形通道 Hagen-Poiseuille + 幾何修正）。

    支援三種翅片幾何：plain（平直）、wavy（波浪）、louvered（百葉）。
    入口 + 出口損失以 1.3 倍修正係數涵蓋，翅片幾何以額外修正係數乘算。

    Args:
        face_velocity_ms:  面風速 (m/s)，必須 > 0
        fin_pitch_mm:      翅片間距（相鄰翅片中心距）(mm)
        fin_height_mm:     翅片深度（氣流方向長度）(mm)
        fin_thickness_mm:  翅片厚度 (mm)
        temperature_C:     空氣溫度 (°C)
        fin_type:          翅片幾何類型 'plain'|'wavy'|'louvered'

    Returns:
        (pressure_drop_pa, max_velocity_ms, reynolds_number)

    Raises:
        ValueError: 任何尺寸 ≤ 0、面風速 ≤ 0 或 fin_type 不支援
    """
    if face_velocity_ms <= 0:
        raise ValueError(f"面風速必須 > 0，收到 {face_velocity_ms}")
    if fin_pitch_mm <= fin_thickness_mm:
        raise ValueError("翅片間距必須大於翅片厚度")
    if fin_height_mm <= 0:
        raise ValueError(f"翅片深度必須 > 0，收到 {fin_height_mm}")
    if fin_type not in _FIN_TYPE_CORRECTION:
        raise ValueError(f"fin_type 必須為 {list(_FIN_TYPE_CORRECTION)}，收到 '{fin_type}'")

    geom_factor = _FIN_TYPE_CORRECTION[fin_type]
    props = air_properties(temperature_C)
    gap = (fin_pitch_mm - fin_thickness_mm) * 1e-3   # m，通道寬度（實際間隙）
    L   = fin_height_mm * 1e-3                        # m，通道長度（氣流方向）

    # 連續方程：最小截面速度 = 面風速 × (間距/(間距-厚度))
    sigma = (fin_pitch_mm - fin_thickness_mm) / fin_pitch_mm  # 自由流面積比
    v_max = face_velocity_ms / sigma

    # 水力直徑（扁矩形通道：h=gap, w→∞ 近似）
    Dh = 2 * gap

    Re = props.density * v_max * Dh / props.dynamic_viscosity

    if Re < 2300:
        f_darcy = 64.0 / Re
    else:
        # 過渡流：平滑插值
        f_darcy = 64.0 / 2300 * (4000 - Re) / 1700 + 0.316 / Re ** 0.25 * (Re - 2300) / 1700

    # 直管摩擦損失
    dp_friction = f_darcy * (L / Dh) * (0.5 * props.density * v_max ** 2)

    # 入口/出口損失修正（1.3） × 翅片幾何修正
    dp_total = dp_friction * 1.3 * geom_factor

    return dp_total, v_max, Re


def fouling_layer_thickness(
    Rf: float,
    deposit_type: str = 'dust',
) -> float:
    """
    由積垢熱阻 Rf 估算積垢層厚度。
    δ = Rf × k_deposit

    Args:
        Rf:           積垢熱阻 (m²·K/W)，必須 ≥ 0
        deposit_type: 'dust' | 'grease' | 'biofilm' | 'scale'

    Returns:
        積垢層厚度 (μm)

    Raises:
        ValueError: Rf < 0
    """
    if Rf < 0:
        raise ValueError(f"積垢熱阻不可為負，收到 {Rf}")
    k = _K_DEPOSIT.get(deposit_type, _K_DEPOSIT_DEFAULT)
    return Rf * k * 1e6   # m → μm


def analyse_airflow(
    face_velocity_ms: float,
    fin_pitch_mm: float,
    fin_height_mm: float,
    fin_thickness_mm: float,
    Rf_current: float,
    deposit_type: str = 'dust',
    temperature_C: float = 25.0,
    fin_type: str = 'plain',
) -> AirflowResult:
    """
    完整空氣側壓降與積垢風量衰退分析。

    Args:
        face_velocity_ms:  面風速 (m/s)
        fin_pitch_mm:      翅片間距 (mm)
        fin_height_mm:     翅片深度（氣流方向）(mm)
        fin_thickness_mm:  翅片厚度 (mm)
        Rf_current:        當前積垢熱阻 (m²·K/W)（可由 kern_seaton_fouling 取得）
        deposit_type:      積垢類型 ('dust'|'grease'|'biofilm'|'scale')
        temperature_C:     空氣溫度 (°C)
        fin_type:          翅片幾何 'plain'|'wavy'|'louvered'

    Returns:
        AirflowResult
    """
    # 乾淨翅片壓降
    dp_clean, v_max, Re = fin_channel_pressure_drop(
        face_velocity_ms, fin_pitch_mm, fin_height_mm, fin_thickness_mm, temperature_C, fin_type
    )

    # 積垢層厚度（每側）
    delta_um = fouling_layer_thickness(Rf_current, deposit_type)
    delta_m = delta_um * 1e-6

    # 積垢後有效間距
    gap_clean = (fin_pitch_mm - fin_thickness_mm) * 1e-3   # m
    gap_fouled = max(gap_clean - 2 * delta_m, gap_clean * 0.1)  # 不讓間距縮到零
    effective_pitch_mm = gap_fouled * 1e3 + fin_thickness_mm

    # 積垢後壓降（以縮小後的 pitch 重新計算）
    dp_fouled, _, _ = fin_channel_pressure_drop(
        face_velocity_ms, effective_pitch_mm, fin_height_mm, fin_thickness_mm, temperature_C, fin_type
    )

    # 壓降增幅
    dp_increase_pct = (dp_fouled - dp_clean) / dp_clean * 100

    # 同等風機壓力下的風量衰退
    # 層流通道：Q ∝ ΔP × gap³（Poiseuille），ΔP 固定時 Q ∝ gap³
    # 用更保守的平方根法（系統曲線 ΔP ∝ Q²）：Q_fouled/Q_clean = sqrt(ΔP_clean/ΔP_fouled)
    airflow_reduction_pct = (1 - math.sqrt(dp_clean / dp_fouled)) * 100

    # 維持風量所需額外功率（風機功率 ∝ Q × ΔP）
    power_increase_pct = (dp_fouled / dp_clean - 1) * 100

    notes = []
    if Re < 2300:
        notes.append(f"Re={Re:.0f}，層流通道（ΔP ∝ 1/gap³，對積垢非常敏感）")
    elif Re < 4000:
        notes.append(f"Re={Re:.0f}，過渡流，壓降模型精度較低")

    if delta_um > 50:
        notes.append(f"積垢層 {delta_um:.1f} μm 較厚，建議清潔")

    if airflow_reduction_pct < 1:
        recommendation = f"積垢影響輕微，風量衰退 < 1%，暫不影響冷氣效能。"
    elif airflow_reduction_pct < 5:
        recommendation = (
            f"風量衰退 {airflow_reduction_pct:.1f}%，冷效輕微下降，"
            f"建議下次保養時一併清潔。"
        )
    elif airflow_reduction_pct < 15:
        recommendation = (
            f"風量衰退 {airflow_reduction_pct:.1f}%，壓降增加 {dp_increase_pct:.1f}%，"
            f"冷氣效能明顯下降，建議近期清潔。"
        )
    else:
        recommendation = (
            f"風量衰退 {airflow_reduction_pct:.1f}%，翅片嚴重堵塞，"
            f"可能導致蒸發器結冰，立即清潔。"
        )

    return AirflowResult(
        face_velocity_ms=face_velocity_ms,
        max_velocity_ms=v_max,
        reynolds_number=Re,
        pressure_drop_clean_pa=dp_clean,
        pressure_drop_fouled_pa=dp_fouled,
        pressure_increase_pct=dp_increase_pct,
        airflow_reduction_pct=airflow_reduction_pct,
        fouling_layer_um=delta_um,
        effective_gap_mm=gap_fouled * 1e3,
        power_increase_pct=power_increase_pct,
        recommendation=recommendation,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# References
# ---------------------------------------------------------------------------
# [1] Shah, R.K. & London, A.L. (1978). Laminar Flow Forced Convection in
#     Ducts. Academic Press. (Hydraulic diameter Dh = 2·gap for parallel
#     plates; rectangular channel friction factor f·Re correlations.)
# [2] Hagen, G. (1839). "Ueber die Bewegung des Wassers in engen zylindrischen
#     Röhren." Poggendorffs Ann. Phys. Chem., 46, 423–442.
# [3] Poiseuille, J.L.M. (1840). "Recherches expérimentales sur le mouvement
#     des liquides dans les tubes de très-petits diamètres."
#     Comptes Rendus, 11, 961–967. (Hagen-Poiseuille: f = 64/Re.)
# [4] Wang, C.C. et al. (1996). "Airside performance of herringbone wavy
#     fin-and-tube heat exchangers." Int. J. Refrigeration, 20(1), 28–35.
#     (Fin-channel pressure drop correction factors.)
# [5] Pakdaman, M.F. et al. (2012). "Performance degradation of a natural-
#     draft dry cooling tower due to deposits and fouling."
#     Applied Thermal Engineering, 36, 218–227.
#     (Fouling layer effect on airside ΔP and flow rate degradation.)
# [6] ASHRAE (2017). ASHRAE Handbook — Fundamentals. Chapter 21
#     (air-side pressure drop across fin-and-tube coils).
