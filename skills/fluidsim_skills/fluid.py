"""流體力學基礎計算模組"""
from dataclasses import dataclass
import math


@dataclass
class FluidProperties:
    density: float           # kg/m³
    dynamic_viscosity: float # Pa·s
    kinematic_viscosity: float  # m²/s


def water_properties(temperature_C: float) -> FluidProperties:
    """水的物理性質（0–100°C），使用多項式近似。"""
    T = temperature_C
    # 密度近似（±0.3 kg/m³ within 0-100°C）
    density = 999.842 - 0.0623 * T - 0.00368 * T**2 + 1.47e-5 * T**3
    # 動力黏度近似（Pa·s）
    mu = 1.7879e-3 * math.exp(-0.02539 * T + 9.6e-5 * T**2 - 4.0e-7 * T**3)
    return FluidProperties(
        density=density,
        dynamic_viscosity=mu,
        kinematic_viscosity=mu / density,
    )


def reynolds_number(diameter: float, velocity: float, kinematic_viscosity: float) -> float:
    """Re = V·D / ν"""
    return velocity * diameter / kinematic_viscosity


def flow_regime(Re: float) -> str:
    """依雷諾數判斷流態。"""
    if Re < 2300:
        return 'laminar'
    elif Re < 4000:
        return 'transitional'
    return 'turbulent'


def velocity_to_flowrate(velocity: float, diameter: float) -> float:
    """流速(m/s) → 體積流量(m³/s)"""
    area = math.pi * (diameter / 2) ** 2
    return velocity * area


def flowrate_to_velocity(flowrate_lpm: float, diameter: float) -> float:
    """體積流量(L/min) → 流速(m/s)"""
    area = math.pi * (diameter / 2) ** 2
    return (flowrate_lpm / 1000 / 60) / area
