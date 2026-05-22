"""壓力系統計算模組 — Darcy-Weisbach、局部損失、閥門選型"""
import math
from dataclasses import dataclass
from .fluid import reynolds_number, flow_regime, water_properties, flowrate_to_velocity


@dataclass
class PressureDropResult:
    friction_loss_pa: float    # 直管摩擦損失 (Pa)
    minor_loss_pa: float       # 局部損失 (Pa)
    total_loss_pa: float       # 總壓損 (Pa)
    total_loss_bar: float      # 總壓損 (bar)
    friction_factor: float     # Darcy 摩擦係數
    velocity: float            # 平均流速 (m/s)
    reynolds: float            # 雷諾數


def friction_factor(Re: float, relative_roughness: float = 0.0) -> float:
    """
    計算 Darcy 摩擦係數。
    層流: f = 64/Re
    紊流: Colebrook-White 方程式迭代求解
    """
    if Re < 2300:
        return 64.0 / Re
    # Swamee-Jain 近似（Colebrook-White 顯式解，誤差 < 3%）
    if relative_roughness == 0:
        relative_roughness = 1e-10  # 光滑管近似
    term = relative_roughness / 3.7 + 5.74 / Re**0.9
    return 0.25 / (math.log10(term))**2


def pressure_drop(
    diameter: float,
    length: float,
    flowrate_lpm: float,
    temperature_C: float = 20.0,
    roughness_m: float = 1.5e-5,
    minor_loss_K: float = 0.0,
) -> PressureDropResult:
    """
    Darcy-Weisbach 管路壓損計算。

    Args:
        diameter:       管道內徑 (m)
        length:         管道長度 (m)
        flowrate_lpm:   體積流量 (L/min)
        temperature_C:  流體溫度 (°C)
        roughness_m:    管壁粗糙度 (m)，鋼管預設 1.5e-5 m
        minor_loss_K:   局部損失係數總和 (彎頭、閥門等)
    """
    props = water_properties(temperature_C)
    velocity = flowrate_to_velocity(flowrate_lpm, diameter)
    Re = reynolds_number(diameter, velocity, props.kinematic_viscosity)
    relative_roughness = roughness_m / diameter
    f = friction_factor(Re, relative_roughness)

    # Darcy-Weisbach: ΔP = f × (L/D) × (ρV²/2)
    dynamic_pressure = 0.5 * props.density * velocity**2
    friction_loss = f * (length / diameter) * dynamic_pressure
    minor_loss = minor_loss_K * dynamic_pressure
    total_loss = friction_loss + minor_loss

    return PressureDropResult(
        friction_loss_pa=friction_loss,
        minor_loss_pa=minor_loss,
        total_loss_pa=total_loss,
        total_loss_bar=total_loss / 1e5,
        friction_factor=f,
        velocity=velocity,
        reynolds=Re,
    )


def available_nozzle_pressure(
    supply_pressure_bar: float,
    pipe_diameter: float,
    pipe_length: float,
    flowrate_lpm: float,
    temperature_C: float = 20.0,
    fittings_K: float = 2.0,
) -> float:
    """
    計算噴嘴前可用壓力。

    Args:
        supply_pressure_bar: 水源供應壓力 (bar)
        fittings_K:          管路配件局部損失係數總和（預設 2.0，含 2 個彎頭）

    Returns:
        噴嘴前壓力 (bar)
    """
    result = pressure_drop(
        diameter=pipe_diameter,
        length=pipe_length,
        flowrate_lpm=flowrate_lpm,
        temperature_C=temperature_C,
        minor_loss_K=fittings_K,
    )
    nozzle_pressure = supply_pressure_bar - result.total_loss_bar
    return max(nozzle_pressure, 0.0)


# 常用管路配件局部損失係數 K 值參考
FITTING_K_VALUES = {
    '90deg_elbow_standard': 0.9,
    '90deg_elbow_long':     0.6,
    '45deg_elbow':          0.4,
    'gate_valve_open':      0.2,
    'ball_valve_open':      0.1,
    'check_valve':          2.0,
    'tee_through':          0.6,
    'tee_branch':           1.8,
    'entry_sharp':          0.5,
    'exit':                 1.0,
}
