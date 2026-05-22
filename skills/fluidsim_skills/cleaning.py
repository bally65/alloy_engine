"""冷氣清潔系統設計計算模組"""
import math
from dataclasses import dataclass, field
from typing import List
from .fluid import water_properties
from .pressure import available_nozzle_pressure


@dataclass
class NozzleResult:
    orifice_diameter_mm: float   # 噴嘴孔徑 (mm)
    flowrate_lpm: float          # 實際流量 (L/min)
    exit_velocity: float         # 噴出流速 (m/s)
    impact_force_N: float        # 衝擊力 (N)
    impact_pressure_kpa: float   # 衝擊壓力 (kPa)，用於評估清潔效果
    spray_angle_deg: float       # 噴霧角度
    coverage_width_mm: float     # 在目標距離的覆蓋寬度 (mm)


@dataclass
class CleaningReport:
    equipment: str
    supply_pressure_bar: float
    nozzle: NozzleResult
    pipe_loss_bar: float
    nozzle_pressure_bar: float
    recommended_distance_mm: float
    estimated_cleaning_time_min: float
    warnings: List[str] = field(default_factory=list)
    procedure: List[str] = field(default_factory=list)


def nozzle_flowrate(
    pressure_bar: float,
    orifice_diameter_mm: float,
    discharge_coeff: float = 0.65,
) -> float:
    """
    Torricelli 定理計算噴嘴流量。
    Q = Cd × A × √(2ΔP/ρ)

    Args:
        pressure_bar:       噴嘴前壓力 (bar)
        orifice_diameter_mm: 孔徑 (mm)
        discharge_coeff:    流量係數 Cd（尖口噴嘴 0.61，圓角 0.82，預設 0.65）

    Returns:
        流量 (L/min)
    """
    rho = 998.2  # 水密度 kg/m³ @ 20°C
    delta_p = pressure_bar * 1e5  # Pa
    d = orifice_diameter_mm / 1000  # m
    area = math.pi * (d / 2) ** 2
    velocity = discharge_coeff * math.sqrt(2 * delta_p / rho)
    Q_m3s = area * velocity
    return Q_m3s * 1000 * 60  # L/min


def nozzle_impact_force(
    pressure_bar: float,
    orifice_diameter_mm: float,
    distance_mm: float = 150.0,
    spray_angle_deg: float = 15.0,
    discharge_coeff: float = 0.65,
) -> NozzleResult:
    """
    計算噴嘴衝擊力與覆蓋範圍。

    Args:
        distance_mm:   噴嘴到目標面距離 (mm)
        spray_angle_deg: 噴霧全角 (度)

    Returns:
        NozzleResult 包含流量、衝擊力、覆蓋寬度
    """
    rho = 998.2
    delta_p = pressure_bar * 1e5
    d = orifice_diameter_mm / 1000
    area = math.pi * (d / 2) ** 2

    exit_velocity = discharge_coeff * math.sqrt(2 * delta_p / rho)
    Q_m3s = area * exit_velocity
    Q_lpm = Q_m3s * 1000 * 60

    # 衝擊力 F = ρQV（動量守恆，假設完全停止）
    impact_force = rho * Q_m3s * exit_velocity

    # 衝擊壓力（以噴霧覆蓋面積計算）
    coverage_radius = distance_mm / 1000 * math.tan(math.radians(spray_angle_deg / 2))
    coverage_area = math.pi * coverage_radius ** 2
    impact_pressure_pa = impact_force / coverage_area if coverage_area > 0 else 0
    coverage_width_mm = coverage_radius * 2 * 1000

    return NozzleResult(
        orifice_diameter_mm=orifice_diameter_mm,
        flowrate_lpm=Q_lpm,
        exit_velocity=exit_velocity,
        impact_force_N=impact_force,
        impact_pressure_kpa=impact_pressure_pa / 1000,
        spray_angle_deg=spray_angle_deg,
        coverage_width_mm=coverage_width_mm,
    )


def design_cleaning_system(
    equipment_name: str,
    evaporator_width_mm: float,
    evaporator_height_mm: float,
    supply_pressure_bar: float,
    pipe_diameter_mm: float = 9.5,
    pipe_length_m: float = 3.0,
    target_distance_mm: float = 150.0,
    temperature_C: float = 20.0,
) -> CleaningReport:
    """
    完整冷氣清潔系統設計。

    Args:
        equipment_name:      冷氣型號或描述
        evaporator_width_mm: 蒸發器寬度 (mm)
        evaporator_height_mm: 蒸發器高度 (mm)
        supply_pressure_bar: 水源供應壓力 (bar)
        pipe_diameter_mm:    清潔管路內徑 (mm)，預設 3/8" = 9.5mm
        pipe_length_m:       清潔管路總長度 (m)
        target_distance_mm:  噴嘴到蒸發器距離 (mm)
    """
    warnings = []
    pipe_d = pipe_diameter_mm / 1000

    # 先用中等孔徑估算流量，計算管路壓損
    initial_nozzle_d = 2.0  # mm，初始估算
    initial_Q = nozzle_flowrate(supply_pressure_bar * 0.8, initial_nozzle_d)

    nozzle_p = available_nozzle_pressure(
        supply_pressure_bar=supply_pressure_bar,
        pipe_diameter=pipe_d,
        pipe_length=pipe_length_m,
        flowrate_lpm=initial_Q,
        temperature_C=temperature_C,
    )
    pipe_loss = supply_pressure_bar - nozzle_p

    # 根據可用壓力選擇噴嘴孔徑
    if nozzle_p < 1.5:
        warnings.append(f"警告：噴嘴前壓力僅 {nozzle_p:.1f} bar，清潔效果可能不足（建議 ≥ 2 bar）")
        orifice_d = 1.2
    elif nozzle_p < 3.0:
        orifice_d = 1.5
    elif nozzle_p < 6.0:
        orifice_d = 2.0
    else:
        orifice_d = 2.5

    nozzle = nozzle_impact_force(
        pressure_bar=nozzle_p,
        orifice_diameter_mm=orifice_d,
        distance_mm=target_distance_mm,
        spray_angle_deg=25.0 if nozzle_p >= 3.0 else 15.0,
    )

    # 蒸發器面積 → 清潔時間估算
    evap_area_m2 = (evaporator_width_mm / 1000) * (evaporator_height_mm / 1000)
    coverage_per_pass_m2 = (nozzle.coverage_width_mm / 1000) * (evaporator_width_mm / 1000)
    passes_needed = math.ceil(evaporator_height_mm / nozzle.coverage_width_mm) if nozzle.coverage_width_mm > 0 else 5
    time_per_pass_min = 0.5  # 每道次約 30 秒
    cleaning_time = passes_needed * time_per_pass_min + 2  # +2 分鐘準備

    if supply_pressure_bar < 2.0:
        warnings.append("水源壓力低於 2 bar，建議使用加壓泵")
    if nozzle.impact_pressure_kpa < 10:
        warnings.append("衝擊壓力偏低，翅片深層污垢清潔效果有限，建議搭配清潔劑")

    procedure = [
        "1. 切斷冷氣電源，確認安全後再開始",
        "2. 拆除冷氣前蓋，露出蒸發器翅片",
        f"3. 噴嘴維持距翅片 {target_distance_mm:.0f}mm，由上而下水平掃噴",
        f"4. 操作水壓設定於 {supply_pressure_bar:.1f} bar",
        f"5. 預計清潔道次：{passes_needed} 道，總時間約 {cleaning_time:.0f} 分鐘",
        "6. 清潔後確認排水管暢通，等待翅片風乾後再通電",
    ]

    return CleaningReport(
        equipment=equipment_name,
        supply_pressure_bar=supply_pressure_bar,
        nozzle=nozzle,
        pipe_loss_bar=pipe_loss,
        nozzle_pressure_bar=nozzle_p,
        recommended_distance_mm=target_distance_mm,
        estimated_cleaning_time_min=cleaning_time,
        warnings=warnings,
        procedure=procedure,
    )
