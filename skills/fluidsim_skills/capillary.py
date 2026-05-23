"""
毛細滲透計算模組
涵蓋：Laplace-Young 毛細壓力、Lucas-Washburn 滲透動力學、翅片縫隙可滲透性評估

翅片間距僅 1.2–2.5 mm，清潔液能否自發滲入是清潔效果的關鍵物理機制。
"""
import math
from dataclasses import dataclass, field
from typing import List

# 標準重力加速度
_G = 9.81  # m/s²

# 空氣密度（用於計算毛細上升高度對比）
_RHO_AIR = 1.184  # kg/m³ @ 25°C


@dataclass
class CapillaryResult:
    can_penetrate: bool          # 是否可自發滲入（接觸角 < 90°）
    capillary_pressure_pa: float # 毛細壓力 (Pa)，正值代表可滲入
    capillary_rise_mm: float     # 垂直毛細上升高度 (mm)
    penetration_depth_mm: float  # 在給定時間內的滲透深度 (mm)
    penetration_time_s: float    # 滲透給定深度所需時間 (s)
    half_spacing_mm: float       # 翅片半間距（毛細管有效半徑）(mm)
    regime: str                  # 'spontaneous' | 'assisted' | 'blocked'
    notes: List[str] = field(default_factory=list)


@dataclass
class FinPenetrationReport:
    """翅片縫隙毛細滲透完整分析報告"""
    fin_spacing_mm: float
    fin_height_mm: float
    surface_tension_mN: float
    contact_angle_deg: float
    cleaner_name: str
    capillary_pressure_pa: float
    can_reach_full_depth: bool        # 能否在合理時間內滲透整個翅片高度
    time_to_full_penetration_s: float # 滲透至翅片底部所需時間 (s)
    time_to_half_penetration_s: float # 滲透至翅片高度一半所需時間 (s)
    vs_water: str                     # 與純水相比的改善程度
    recommendation: str


def capillary_pressure(
    surface_tension_mN: float,
    contact_angle_deg: float,
    channel_half_width_mm: float,
) -> float:
    """
    Laplace-Young 方程式計算毛細壓力。
    Pc = 2γ·cos(θ) / r

    正值代表毛細力促進滲入（θ < 90°）。
    負值代表毛細力阻礙滲入（θ > 90°，疏水面）。

    Args:
        surface_tension_mN:    清潔液表面張力 (mN/m)
        contact_angle_deg:     清潔液與翅片的接觸角 (°)
        channel_half_width_mm: 翅片半間距（毛細管有效半徑）(mm)

    Returns:
        毛細壓力 (Pa)

    Raises:
        ValueError: 輸入參數超出物理範圍
    """
    if surface_tension_mN <= 0:
        raise ValueError(f"表面張力必須 > 0，收到 {surface_tension_mN}")
    if channel_half_width_mm <= 0:
        raise ValueError(f"半間距必須 > 0，收到 {channel_half_width_mm}")
    if not (0 <= contact_angle_deg <= 180):
        raise ValueError(f"接觸角必須在 [0, 180]°，收到 {contact_angle_deg}")

    gamma = surface_tension_mN * 1e-3  # N/m
    theta = math.radians(contact_angle_deg)
    r = channel_half_width_mm * 1e-3   # m
    return 2 * gamma * math.cos(theta) / r


def capillary_rise_height(
    surface_tension_mN: float,
    contact_angle_deg: float,
    channel_half_width_mm: float,
    liquid_density: float = 998.2,
) -> float:
    """
    毛細上升高度 h = 2γ·cos(θ) / (ρgr)（Jurin 定律）

    Returns:
        毛細上升高度 (mm)，負值代表毛細壓低液面
    """
    pc = capillary_pressure(surface_tension_mN, contact_angle_deg, channel_half_width_mm)
    r = channel_half_width_mm * 1e-3
    h = pc / (liquid_density * _G)
    return h * 1000  # mm


def lucas_washburn_penetration(
    surface_tension_mN: float,
    contact_angle_deg: float,
    channel_half_width_mm: float,
    dynamic_viscosity: float,
    time_s: float,
) -> float:
    """
    Lucas-Washburn 方程式計算橫向毛細滲透深度。
    x(t) = √( r·γ·cos(θ) / (2μ) × t )

    適用於水平（重力不起作用）的翅片滲透。

    Args:
        dynamic_viscosity: 液體動力黏度 (Pa·s)
        time_s:            滲透時間 (s)

    Returns:
        滲透深度 (mm)
    """
    if contact_angle_deg >= 90:
        return 0.0  # 疏水面無法自發滲透

    gamma = surface_tension_mN * 1e-3
    theta = math.radians(contact_angle_deg)
    r = channel_half_width_mm * 1e-3

    if dynamic_viscosity <= 0 or time_s < 0:
        raise ValueError("黏度必須 > 0，時間必須 ≥ 0")

    x = math.sqrt(r * gamma * math.cos(theta) / (2 * dynamic_viscosity) * time_s)
    return x * 1000  # mm


def time_to_penetrate(
    surface_tension_mN: float,
    contact_angle_deg: float,
    channel_half_width_mm: float,
    dynamic_viscosity: float,
    target_depth_mm: float,
) -> float:
    """
    計算達到指定滲透深度所需時間。
    t = x² × 2μ / (r·γ·cos(θ))

    Returns:
        所需時間 (s)，若無法滲透則回傳 float('inf')
    """
    if contact_angle_deg >= 90:
        return float('inf')

    gamma = surface_tension_mN * 1e-3
    theta = math.radians(contact_angle_deg)
    r = channel_half_width_mm * 1e-3
    x = target_depth_mm * 1e-3

    return x ** 2 * 2 * dynamic_viscosity / (r * gamma * math.cos(theta))


def analyse_fin_penetration(
    fin_spacing_mm: float,
    fin_height_mm: float,
    surface_tension_mN: float,
    contact_angle_deg: float,
    dynamic_viscosity: float,
    cleaner_name: str = '清潔液',
    water_surface_tension_mN: float = 72.8,
    water_contact_angle_deg: float = 60.0,
) -> FinPenetrationReport:
    """
    翅片縫隙毛細滲透完整分析。

    Args:
        fin_spacing_mm:    翅片間距 (mm)
        fin_height_mm:     翅片高度（清潔液需滲透的深度）(mm)
        surface_tension_mN: 清潔液表面張力 (mN/m)
        contact_angle_deg: 清潔液對翅片材質的接觸角 (°)
        dynamic_viscosity: 清潔液動力黏度 (Pa·s)
        water_surface_tension_mN: 純水表面張力（對照基準）
        water_contact_angle_deg:  純水在鋁翅片的接觸角（對照基準）
    """
    r = fin_spacing_mm / 2  # 半間距作為毛細管有效半徑

    pc = capillary_pressure(surface_tension_mN, contact_angle_deg, r)
    can_penetrate = contact_angle_deg < 90

    t_full = time_to_penetrate(surface_tension_mN, contact_angle_deg, r,
                                dynamic_viscosity, fin_height_mm)
    t_half = time_to_penetrate(surface_tension_mN, contact_angle_deg, r,
                                dynamic_viscosity, fin_height_mm / 2)

    # 對照純水
    t_full_water = time_to_penetrate(water_surface_tension_mN, water_contact_angle_deg,
                                      r, 1.002e-3, fin_height_mm)
    if t_full_water > 0 and t_full < float('inf'):
        ratio = t_full_water / t_full
        if ratio > 2:
            vs_water = f"比純水快 {ratio:.1f} 倍滲透"
        elif ratio > 1.1:
            vs_water = f"比純水快 {ratio:.1f} 倍滲透"
        elif ratio > 0.9:
            vs_water = "與純水相當"
        else:
            vs_water = f"比純水慢（純水更快 {1/ratio:.1f} 倍）"
    elif not can_penetrate:
        vs_water = "無法自發滲透（接觸角 ≥ 90°）"
    else:
        vs_water = "純水也無法自發滲透，清潔液有改善"

    can_reach = t_full < 120  # 2 分鐘內能滲透整個翅片

    if not can_penetrate:
        recommendation = "清潔液無法自發滲入翅片縫隙，需靠水壓強制推入。建議增加清潔劑濃度以降低接觸角。"
    elif t_full < 10:
        recommendation = "優秀：清潔液可在 10 秒內自發滲透整個翅片，靜置即可達到深層清潔。"
    elif t_full < 60:
        recommendation = f"良好：靜置 {t_full:.0f} 秒可達完全滲透，施藥後稍等再水洗效果最佳。"
    elif t_full < 300:
        recommendation = f"可接受：需靜置 {t_full/60:.1f} 分鐘達完全滲透，符合一般清潔操作時間。"
    else:
        recommendation = f"滲透慢（需 {t_full/60:.0f} 分鐘），建議提高清潔劑濃度或延長靜置時間。"

    return FinPenetrationReport(
        fin_spacing_mm=fin_spacing_mm,
        fin_height_mm=fin_height_mm,
        surface_tension_mN=surface_tension_mN,
        contact_angle_deg=contact_angle_deg,
        cleaner_name=cleaner_name,
        capillary_pressure_pa=pc,
        can_reach_full_depth=can_reach,
        time_to_full_penetration_s=t_full if t_full < float('inf') else -1,
        time_to_half_penetration_s=t_half if t_half < float('inf') else -1,
        vs_water=vs_water,
        recommendation=recommendation,
    )


# ---------------------------------------------------------------------------
# References
# ---------------------------------------------------------------------------
# [1] Young, T. (1805). "An essay on the cohesion of fluids."
#     Phil. Trans. R. Soc. London, 95, 65–87. (Contact angle / Laplace-Young.)
# [2] Laplace, P.S. (1805). Traité de Mécanique Céleste, Supplement.
#     (Capillary pressure formulation.)
# [3] Lucas, R. (1918). "Ueber das Zeitgesetz des kapillaren Aufstiegs von
#     Flüssigkeiten." Kolloid-Zeitschrift, 23(1), 15–22.
# [4] Washburn, E.W. (1921). "The dynamics of capillary flow."
#     Physical Review, 17(3), 273–283.
# [5] Adamson, A.W. & Gast, A.P. (1997). Physical Chemistry of Surfaces,
#     6th ed. Wiley. Chapter 10 (capillary phenomena in porous media).
# [6] Kim, C.J. & Bergles, A.E. (1988). "Particulate fouling of structured
#     heat transfer surfaces." ASME HTD-Vol. 96, 47–55.
#     (Fin geometry and wetting context.)
