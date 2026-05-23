"""
液滴動力學計算模組
涵蓋：Weber 數、Ohnesorge 數、液滴破碎模式判斷、噴霧 SMD 估算
"""
import math
from dataclasses import dataclass


@dataclass
class DropletResult:
    """液滴動力學分析結果"""
    weber_number: float        # 韋伯數 We = ρv²d/γ
    ohnesorge_number: float    # 奧內佐格數 Oh = μ/√(ρ·d·γ)
    regime: str                # 'intact' | 'stretching_breakup' | 'catastrophic_breakup'
    sauter_mean_diameter_um: float  # 索特平均直徑 SMD (μm)，0 表示無法估算
    regime_description: str    # 中文流態說明
    critical_velocity: float   # 破碎臨界流速 (m/s)


def weber_number(
    velocity: float,
    diameter_m: float,
    density: float,
    surface_tension_Nm: float,
) -> float:
    """
    液滴 Weber 數：慣性力與表面張力之比。
    We = ρ · v² · d / γ

    We < 12：液滴保持完整
    12 ≤ We < 100：拉伸破碎
    We ≥ 100：劇烈破碎

    Args:
        velocity:          液滴或氣流相對速度 (m/s)，必須 > 0
        diameter_m:        液滴直徑 (m)，必須 > 0
        density:           液體密度 (kg/m³)，必須 > 0
        surface_tension_Nm: 表面張力 (N/m)，必須 > 0

    Returns:
        Weber 數（無因次）

    Raises:
        ValueError: 任何參數 ≤ 0
    """
    if velocity <= 0:
        raise ValueError(f"速度必須 > 0，收到 {velocity}")
    if diameter_m <= 0:
        raise ValueError(f"液滴直徑必須 > 0，收到 {diameter_m}")
    if density <= 0:
        raise ValueError(f"密度必須 > 0，收到 {density}")
    if surface_tension_Nm <= 0:
        raise ValueError(f"表面張力必須 > 0，收到 {surface_tension_Nm}")

    return density * velocity ** 2 * diameter_m / surface_tension_Nm


def ohnesorge_number(
    diameter_m: float,
    density: float,
    dynamic_viscosity: float,
    surface_tension_Nm: float,
) -> float:
    """
    液滴 Ohnesorge 數：黏性力 / √(慣性力 × 表面張力)。
    Oh = μ / √(ρ · d · γ)

    Oh < 0.1：表面張力主導（水性液體典型值）
    Oh > 1：黏性主導（高黏度液體）

    Raises:
        ValueError: 任何參數 ≤ 0
    """
    if diameter_m <= 0:
        raise ValueError(f"液滴直徑必須 > 0，收到 {diameter_m}")
    if density <= 0:
        raise ValueError(f"密度必須 > 0，收到 {density}")
    if dynamic_viscosity <= 0:
        raise ValueError(f"動力黏度必須 > 0，收到 {dynamic_viscosity}")
    if surface_tension_Nm <= 0:
        raise ValueError(f"表面張力必須 > 0，收到 {surface_tension_Nm}")

    return dynamic_viscosity / math.sqrt(density * diameter_m * surface_tension_Nm)


def droplet_regime(we: float, oh: float) -> str:
    """
    根據 Weber 數與 Ohnesorge 數判斷液滴破碎模式。

    分類依據（Pilch & Erdman 1987；適用 Oh < 0.1 的水性液體）：
    - We < 12:             intact（完整液滴）
    - 12 ≤ We < 100:       stretching_breakup（袋式/拉伸破碎）
    - We ≥ 100:            catastrophic_breakup（劇烈霧化）

    Raises:
        ValueError: we < 0 或 oh < 0
    """
    if we < 0:
        raise ValueError(f"Weber 數不可為負，收到 {we}")
    if oh < 0:
        raise ValueError(f"Ohnesorge 數不可為負，收到 {oh}")

    if we < 12:
        return 'intact'
    elif we < 100:
        return 'stretching_breakup'
    else:
        return 'catastrophic_breakup'


def spray_droplet_size(
    pressure_bar: float,
    orifice_diameter_mm: float,
    surface_tension_mN: float = 72.8,
    density: float = 998.2,
) -> float:
    """
    噴嘴噴霧索特平均直徑（SMD）估算。
    採用 Hiroyasu & Arai 經驗式（壓力霧化噴嘴）：
        SMD = C · d · We⁻⁰·⁴⁰
    其中 C 為校正係數（圓孔壓力噴嘴 C ≈ 3.08），
    We 基於噴嘴出口流速與孔徑計算。

    Args:
        pressure_bar:         噴嘴前壓力 (bar)，必須 > 0
        orifice_diameter_mm:  噴嘴孔徑 (mm)，必須 > 0
        surface_tension_mN:   液體表面張力 (mN/m)，預設水 @20°C
        density:              液體密度 (kg/m³)

    Returns:
        SMD (μm)

    Raises:
        ValueError: pressure_bar ≤ 0 或 orifice_diameter_mm ≤ 0
    """
    if pressure_bar <= 0:
        raise ValueError(f"壓力必須 > 0，收到 {pressure_bar} bar")
    if orifice_diameter_mm <= 0:
        raise ValueError(f"孔徑必須 > 0，收到 {orifice_diameter_mm} mm")

    gamma = surface_tension_mN * 1e-3  # N/m
    d = orifice_diameter_mm * 1e-3     # m
    delta_p = pressure_bar * 1e5       # Pa

    # 噴嘴出口速度（Torricelli，Cd=0.65）
    velocity = 0.65 * math.sqrt(2 * delta_p / density)

    We = weber_number(velocity, d, density, gamma)
    C = 3.08
    smd_m = C * d * We ** (-0.40)
    return smd_m * 1e6  # μm


def analyse_droplet(
    velocity: float,
    diameter_mm: float,
    surface_tension_mN: float = 72.8,
    density: float = 998.2,
    dynamic_viscosity: float = 1.002e-3,
) -> DropletResult:
    """
    完整液滴動力學分析。

    Args:
        velocity:          液滴速度或噴出流速 (m/s)
        diameter_mm:       液滴直徑 (mm)
        surface_tension_mN: 表面張力 (mN/m)
        density:           密度 (kg/m³)
        dynamic_viscosity: 動力黏度 (Pa·s)

    Returns:
        DropletResult
    """
    d_m = diameter_mm * 1e-3
    gamma = surface_tension_mN * 1e-3

    We = weber_number(velocity, d_m, density, gamma)
    Oh = ohnesorge_number(d_m, density, dynamic_viscosity, gamma)
    regime = droplet_regime(We, Oh)

    # 臨界破碎流速（We_crit=12 反推）
    v_crit = math.sqrt(12 * gamma / (density * d_m))

    descriptions = {
        'intact':              '液滴完整，主要受表面張力維持球形',
        'stretching_breakup':  '袋式/拉伸破碎，液滴變形後分裂成細霧',
        'catastrophic_breakup':'劇烈霧化，瞬間碎裂成微細液滴',
    }

    return DropletResult(
        weber_number=We,
        ohnesorge_number=Oh,
        regime=regime,
        sauter_mean_diameter_um=0.0,  # 需已知噴嘴壓力才能估算 SMD
        regime_description=descriptions[regime],
        critical_velocity=v_crit,
    )


# ---------------------------------------------------------------------------
# References
# ---------------------------------------------------------------------------
# [1] Weber, C. (1931). "Zum Zerfall eines Flüssigkeitsstrahles."
#     ZAMM – Zeitschrift für Angewandte Mathematik und Mechanik, 11(2), 136–154.
#     (Weber number We = ρv²d/γ definition.)
# [2] Ohnesorge, W. (1936). "Formation of drops by nozzles and the breakup
#     of liquid jets." ZAMM, 16(6), 355–358.
#     (Ohnesorge number Oh = μ/√(ρdγ) definition.)
# [3] Reitz, R.D. & Bracco, F.V. (1982). "Mechanism of atomization of a liquid
#     jet." Physics of Fluids, 25(10), 1730–1742. (Breakup regime boundaries.)
# [4] Hiroyasu, H. & Arai, M. (1990). "Structures of fuel sprays in diesel
#     engines." SAE Technical Paper 900475.
#     (Empirical SMD correlation for plain-orifice sprays.)
# [5] Lefebvre, A.H. & McDonell, V.G. (2017). Atomization and Sprays, 2nd ed.
#     CRC Press. Chapter 2 (spray characterization and SMD definitions).
