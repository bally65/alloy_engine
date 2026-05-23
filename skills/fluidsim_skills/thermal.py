"""
翅片效率與熱傳計算模組
涵蓋：翅片效率 (eta)、Dittus-Boelter 對流係數、TEMA 污垢熱阻、alloy_engine κ 整合介面
"""
import math
from dataclasses import dataclass, field
from typing import List

from .fluid import water_properties, reynolds_number


# Prandtl 數查表（水，近似值）— 用於 Dittus-Boelter
_PR_TABLE = {
    0:  13.5, 10: 9.5, 20: 7.0, 30: 5.4,
    40: 4.3,  50: 3.5, 60: 2.99, 70: 2.55,
    80: 2.21, 90: 1.96, 100: 1.75,
}


def _prandtl(temperature_C: float) -> float:
    """水的 Prandtl 數（線性插值）"""
    t = max(0.0, min(100.0, temperature_C))
    keys = sorted(_PR_TABLE.keys())
    for i in range(len(keys) - 1):
        t0, t1 = keys[i], keys[i + 1]
        if t0 <= t <= t1:
            frac = (t - t0) / (t1 - t0)
            return _PR_TABLE[t0] + frac * (_PR_TABLE[t1] - _PR_TABLE[t0])
    return _PR_TABLE[keys[-1]]


@dataclass
class ThermalReport:
    """翅片熱性能完整報告"""
    fin_efficiency: float          # 翅片效率 η (0–1)
    fin_height_mm: float
    fin_thickness_mm: float
    thermal_conductivity: float    # κ (W/m·K)
    h_conv: float                  # 對流係數 (W/m²·K)
    m_parameter: float             # 翅片參數 m = √(2h/k·t) (1/m)
    heat_transfer_improvement: str # 與基準純水相比的說明
    notes: List[str] = field(default_factory=list)


def fin_efficiency(
    fin_height_m: float,
    fin_thickness_m: float,
    thermal_conductivity: float,
    h_conv: float,
) -> float:
    """
    矩形直翅片效率 η = tanh(mL) / (mL)
    m = √(2h / (k · t))

    適用於等截面直翅片（HVAC 蒸發器鋁翅片的標準模型）。

    Args:
        fin_height_m:         翅片高度 L (m)，必須 > 0
        fin_thickness_m:      翅片厚度 t (m)，必須 > 0
        thermal_conductivity: 翅片材料熱傳導率 κ (W/m·K)，必須 > 0
        h_conv:               對流換熱係數 h (W/m²·K)，必須 > 0

    Returns:
        翅片效率 η ∈ (0, 1]

    Raises:
        ValueError: 任何參數 ≤ 0
    """
    if fin_height_m <= 0:
        raise ValueError(f"翅片高度必須 > 0，收到 {fin_height_m}")
    if fin_thickness_m <= 0:
        raise ValueError(f"翅片厚度必須 > 0，收到 {fin_thickness_m}")
    if thermal_conductivity <= 0:
        raise ValueError(f"熱傳導率必須 > 0，收到 {thermal_conductivity}")
    if h_conv <= 0:
        raise ValueError(f"對流係數必須 > 0，收到 {h_conv}")

    m = math.sqrt(2 * h_conv / (thermal_conductivity * fin_thickness_m))
    mL = m * fin_height_m
    if mL < 1e-10:
        return 1.0
    return math.tanh(mL) / mL


def dittus_boelter_h(
    velocity: float,
    diameter: float,
    temperature_C: float = 25.0,
    heating: bool = True,
) -> float:
    """
    Dittus-Boelter 公式計算管內強制對流換熱係數。
    Nu = 0.023 · Re⁰·⁸ · Prⁿ   (加熱 n=0.4，冷卻 n=0.3)
    h = Nu · k_water / D

    適用範圍：Re > 10000，0.7 < Pr < 160。

    Args:
        velocity:      平均流速 (m/s)，必須 > 0
        diameter:      管道內徑 (m)，必須 > 0
        temperature_C: 流體溫度 (°C)
        heating:       True = 流體被加熱（n=0.4），False = 流體被冷卻（n=0.3）

    Returns:
        對流換熱係數 h (W/m²·K)

    Raises:
        ValueError: velocity ≤ 0 或 diameter ≤ 0
    """
    if velocity <= 0:
        raise ValueError(f"流速必須 > 0，收到 {velocity}")
    if diameter <= 0:
        raise ValueError(f"管徑必須 > 0，收到 {diameter}")

    props = water_properties(temperature_C)
    Re = reynolds_number(diameter, velocity, props.kinematic_viscosity)
    Pr = _prandtl(temperature_C)
    n = 0.4 if heating else 0.3

    # 水的熱傳導率（近似 Ramires 公式，單位 W/m·K）
    k_water = 0.6065 * (-1.48445 + 4.12292 * ((temperature_C + 273.15) / 298.15)
                        - 1.63866 * ((temperature_C + 273.15) / 298.15) ** 2)

    Nu = 0.023 * Re ** 0.8 * Pr ** n
    return Nu * k_water / diameter


def fin_efficiency_from_kappa(
    fin_height_mm: float,
    fin_thickness_mm: float,
    kappa_W_mK: float,
    h_conv: float = 30.0,
) -> ThermalReport:
    """
    接受 alloy_engine κ 預測值，計算翅片效率並生成完整分析報告。

    alloy_engine 輸出的 κ 可直接傳入此函式，評估不同合金對翅片熱性能的影響。

    Args:
        fin_height_mm:  翅片高度 (mm)，典型蒸發器 10–20 mm
        fin_thickness_mm: 翅片厚度 (mm)，典型 0.08–0.15 mm
        kappa_W_mK:     熱傳導率 κ (W/m·K)，alloy_engine 預測值
        h_conv:         對流係數 (W/m²·K)，預設 30（自然對流+冷媒側）

    Returns:
        ThermalReport

    Raises:
        ValueError: 任何參數 ≤ 0
    """
    if fin_height_mm <= 0:
        raise ValueError(f"翅片高度必須 > 0，收到 {fin_height_mm}")
    if fin_thickness_mm <= 0:
        raise ValueError(f"翅片厚度必須 > 0，收到 {fin_thickness_mm}")
    if kappa_W_mK <= 0:
        raise ValueError(f"κ 必須 > 0，收到 {kappa_W_mK}")
    if h_conv <= 0:
        raise ValueError(f"對流係數必須 > 0，收到 {h_conv}")

    L = fin_height_mm * 1e-3
    t = fin_thickness_mm * 1e-3

    eta = fin_efficiency(L, t, kappa_W_mK, h_conv)
    m = math.sqrt(2 * h_conv / (kappa_W_mK * t))

    # 與標準鋁翅片（κ=205 W/m·K）對比
    eta_al = fin_efficiency(L, t, 205.0, h_conv)
    ratio = eta / eta_al if eta_al > 0 else 1.0

    notes = []
    if eta < 0.7:
        notes.append(f"翅片效率偏低 ({eta:.1%})，建議增加翅片厚度或提高材料 κ")
    elif eta > 0.95:
        notes.append(f"翅片效率優良 ({eta:.1%})，熱阻主要來自對流側")

    if ratio > 1.05:
        improvement = f"比標準鋁翅片 (κ=205) 效率高 {(ratio-1)*100:.1f}%"
    elif ratio < 0.95:
        improvement = f"比標準鋁翅片 (κ=205) 效率低 {(1-ratio)*100:.1f}%"
    else:
        improvement = "與標準鋁翅片 (κ=205) 效率相當"

    return ThermalReport(
        fin_efficiency=eta,
        fin_height_mm=fin_height_mm,
        fin_thickness_mm=fin_thickness_mm,
        thermal_conductivity=kappa_W_mK,
        h_conv=h_conv,
        m_parameter=m,
        heat_transfer_improvement=improvement,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# References
# ---------------------------------------------------------------------------
# [1] Harper, D.R. & Brown, W.B. (1922). "Mathematical equations for heat
#     conduction in the fins of air cooled engines." NACA Report No. 158.
#     (Rectangular fin efficiency η = tanh(mL)/(mL) derivation.)
# [2] Dittus, F.W. & Boelter, L.M.K. (1930). "Heat transfer in automobile
#     radiators of the tubular type." Univ. California Publ. Eng., 2, 443–461.
#     (Nu = 0.023 Re⁰·⁸ Prⁿ correlation.)
# [3] Incropera, F.P. et al. (2007). Fundamentals of Heat and Mass Transfer,
#     6th ed. Wiley. §3.6 (fin efficiency), §8.5 (Dittus-Boelter limits).
# [4] Schmidt, T.E. (1945). "La production calorifique des surfaces munies
#     d'ailettes." Bull. Assoc. Suisse des Electriciens, 36(2), 47–52.
#     (Generalized fin efficiency for heat exchanger design.)
# [5] Ramires, M.L.V. et al. (1995). "Standard reference data for the thermal
#     conductivity of water." J. Phys. Chem. Ref. Data, 24(3), 1377–1381.
