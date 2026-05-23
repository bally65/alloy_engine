"""壓力系統計算模組 — Darcy-Weisbach、局部損失、閥門選型"""
import math
from dataclasses import dataclass
from .fluid import reynolds_number, flow_regime, water_properties, flowrate_to_velocity

# 噴嘴壓力選擇閾值（bar）：依 ASHRAE 清潔設備壓力分級定義
_NOZZLE_LOW_PRESSURE    = 1.5   # 低於此值警告清潔效果不足
_NOZZLE_MED_PRESSURE    = 3.0   # 一般居家清潔適用上限
_NOZZLE_HIGH_PRESSURE   = 6.0   # 商用加壓設備範圍


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
    層流 (Re < 2300): f = 64/Re
    紊流: Swamee-Jain 近似（Colebrook-White 顯式解，誤差 < 3%）

    Raises:
        ValueError: Re ≤ 0
    """
    if Re <= 0:
        raise ValueError(f"雷諾數必須 > 0，收到 {Re}")
    if Re < 2300:
        return 64.0 / Re
    rr = max(relative_roughness, 1e-10)  # 光滑管用極小粗糙度防 log(0)
    term = rr / 3.7 + 5.74 / Re ** 0.9
    return 0.25 / (math.log10(term)) ** 2


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
        diameter:      管道內徑 (m)，必須 > 0
        length:        管道長度 (m)，必須 ≥ 0
        flowrate_lpm:  體積流量 (L/min)，必須 ≥ 0
        temperature_C: 流體溫度 (°C)
        roughness_m:   管壁粗糙度 (m)；鋼管 1.5e-5，銅/PVC 1.5e-6
        minor_loss_K:  局部損失係數總和（彎頭、閥門等）

    Raises:
        ValueError: diameter ≤ 0、length < 0、flowrate_lpm < 0
    """
    if diameter <= 0:
        raise ValueError(f"管道內徑必須 > 0，收到 {diameter}")
    if length < 0:
        raise ValueError(f"管道長度不可為負，收到 {length}")
    if flowrate_lpm < 0:
        raise ValueError(f"流量不可為負值，收到 {flowrate_lpm}")

    props = water_properties(temperature_C)
    velocity = flowrate_to_velocity(flowrate_lpm, diameter)

    # 零流量：直接回傳零壓損
    if flowrate_lpm == 0:
        return PressureDropResult(
            friction_loss_pa=0.0, minor_loss_pa=0.0,
            total_loss_pa=0.0, total_loss_bar=0.0,
            friction_factor=0.0, velocity=0.0, reynolds=0.0,
        )

    Re = reynolds_number(diameter, velocity, props.kinematic_viscosity)
    relative_roughness = roughness_m / diameter
    f = friction_factor(Re, relative_roughness)

    dynamic_pressure = 0.5 * props.density * velocity ** 2
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
    計算噴嘴前可用壓力（供應壓力 - 管路壓損）。

    Returns:
        噴嘴前壓力 (bar)，最小為 0

    Raises:
        ValueError: supply_pressure_bar < 0
    """
    if supply_pressure_bar < 0:
        raise ValueError(f"供應壓力不可為負，收到 {supply_pressure_bar}")
    result = pressure_drop(
        diameter=pipe_diameter,
        length=pipe_length,
        flowrate_lpm=flowrate_lpm,
        temperature_C=temperature_C,
        minor_loss_K=fittings_K,
    )
    return max(supply_pressure_bar - result.total_loss_bar, 0.0)


# 常用管路配件局部損失係數 K 值（Crane TP-410 手冊）
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


# ---------------------------------------------------------------------------
# References
# ---------------------------------------------------------------------------
# [1] Weisbach, J. (1845). Lehrbuch der Ingenieur- und Maschinen-Mechanik.
#     (Original Darcy-Weisbach formulation.)
# [2] Darcy, H. (1857). "Recherches expérimentales relatives au mouvement
#     de l'eau dans les tuyaux." Mémoires présentés à l'Académie des Sciences.
# [3] Moody, L.F. (1944). "Friction factors for pipe flow."
#     Trans. ASME, 66(8), 671–684.
# [4] Colebrook, C.F. (1939). "Turbulent flow in pipes, with particular
#     reference to the transition region between smooth and rough pipe laws."
#     J. Inst. Civil Engineers, 11(4), 133–156.
# [5] Idelchik, I.E. (2008). Handbook of Hydraulic Resistance, 4th ed.
#     Begell House. (K-value fitting loss database.)
