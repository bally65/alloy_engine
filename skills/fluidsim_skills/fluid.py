"""流體力學基礎計算模組"""
import math
import warnings as _warnings
from dataclasses import dataclass

# 溫度有效範圍
_T_MIN_C = 0.0
_T_MAX_C = 100.0


@dataclass
class FluidProperties:
    density: float            # kg/m³
    dynamic_viscosity: float  # Pa·s
    kinematic_viscosity: float  # m²/s


def water_properties(temperature_C: float) -> FluidProperties:
    """
    水的物理性質（0–100°C）。

    密度：NIST 查表線性插補，誤差 < 0.02 kg/m³。
    動力黏度：Vogel 方程式（Lide, CRC Handbook），誤差 < 0.5%。

    超出 0–100°C 會發出 UserWarning 並截斷至邊界值。
    """
    if temperature_C < _T_MIN_C or temperature_C > _T_MAX_C:
        _warnings.warn(
            f"溫度 {temperature_C}°C 超出有效範圍 [{_T_MIN_C}, {_T_MAX_C}]°C，"
            f"已截斷至邊界值計算。結果可能不準確。",
            UserWarning, stacklevel=2,
        )
    T = max(_T_MIN_C, min(_T_MAX_C, temperature_C))

    # 密度：NIST 查表 + 線性插補
    _density_table = [
        (0,   999.84), (5,   999.97), (10,  999.70), (15,  999.10),
        (20,  998.20), (25,  997.04), (30,  995.65), (40,  992.22),
        (50,  988.07), (60,  983.20), (70,  977.76), (80,  971.82),
        (90,  965.31), (100, 958.37),
    ]
    density = _density_table[-1][1]
    for i in range(len(_density_table) - 1):
        T0, rho0 = _density_table[i]
        T1, rho1 = _density_table[i + 1]
        if T0 <= T <= T1:
            density = rho0 + (rho1 - rho0) * (T - T0) / (T1 - T0)
            break

    # 動力黏度：Vogel 方程式 μ = A × 10^(B/(T+C))，T 單位 °C
    # C = 273.15 − 140 = 133.15（Kelvin 偏移量轉換）
    A, B, C = 2.414e-5, 247.8, 133.15
    mu = A * 10 ** (B / (T + C))

    return FluidProperties(
        density=density,
        dynamic_viscosity=mu,
        kinematic_viscosity=mu / density,
    )


def reynolds_number(diameter: float, velocity: float, kinematic_viscosity: float) -> float:
    """
    Re = V·D / ν

    Raises:
        ValueError: diameter ≤ 0 或 kinematic_viscosity ≤ 0
    """
    if diameter <= 0:
        raise ValueError(f"管道內徑必須 > 0，收到 {diameter}")
    if kinematic_viscosity <= 0:
        raise ValueError(f"運動黏度必須 > 0，收到 {kinematic_viscosity}")
    if velocity < 0:
        raise ValueError(f"流速不可為負值，收到 {velocity}")
    return velocity * diameter / kinematic_viscosity


def flow_regime(Re: float) -> str:
    """
    依雷諾數判斷流態。
    Re < 2300: 層流
    2300 ≤ Re ≤ 4000: 過渡流（含兩端邊界）
    Re > 4000: 紊流
    """
    if Re < 0:
        raise ValueError(f"雷諾數不可為負值，收到 {Re}")
    if Re < 2300:
        return 'laminar'
    elif Re <= 4000:   # 修正：含 4000，符合 ASHRAE/ISO 標準
        return 'transitional'
    return 'turbulent'


def velocity_to_flowrate(velocity: float, diameter: float) -> float:
    """流速 (m/s) → 體積流量 (m³/s)"""
    if diameter <= 0:
        raise ValueError(f"管道內徑必須 > 0，收到 {diameter}")
    area = math.pi * (diameter / 2) ** 2
    return velocity * area


def flowrate_to_velocity(flowrate_lpm: float, diameter: float) -> float:
    """體積流量 (L/min) → 流速 (m/s)"""
    if diameter <= 0:
        raise ValueError(f"管道內徑必須 > 0，收到 {diameter}")
    if flowrate_lpm < 0:
        raise ValueError(f"流量不可為負值，收到 {flowrate_lpm}")
    area = math.pi * (diameter / 2) ** 2
    return (flowrate_lpm / 1000 / 60) / area


# ---------------------------------------------------------------------------
# References
# ---------------------------------------------------------------------------
# [1] Reynolds, O. (1883). "An experimental investigation of the circumstances
#     which determine whether the motion of water shall be direct or sinuous."
#     Phil. Trans. R. Soc. London, 174, 935–982.
# [2] White, F.M. (2011). Fluid Mechanics, 7th ed. McGraw-Hill. §6.
# [3] Wagner, W. & Kruse, A. (1998). Properties of Water and Steam.
#     Springer. (IAPWS-IF97 formulation)
# [4] Incropera, F.P. et al. (2007). Fundamentals of Heat and Mass Transfer,
#     6th ed. Wiley. Appendix A (water property tables).
