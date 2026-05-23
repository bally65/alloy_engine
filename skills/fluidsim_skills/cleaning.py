"""冷氣清潔系統設計計算模組"""
import math
from dataclasses import dataclass, field
from typing import List
from .fluid import water_properties
from .pressure import available_nozzle_pressure, _NOZZLE_LOW_PRESSURE, _NOZZLE_MED_PRESSURE, _NOZZLE_HIGH_PRESSURE

# 翅片安全衝擊壓力上限（kPa）
_MAX_IMPACT_KPA_ALUMINUM = 50.0   # 鋁翅片（標準蒸發器）
_MAX_IMPACT_KPA_COPPER   = 100.0  # 銅翅片（較硬）

# 最小表面張力下限（mN/m）：低於此值代表清潔液可能已乾燥或變質
_MIN_SURFACE_TENSION_MN = 25.0

# 噴霧角有效範圍（度）
_SPRAY_ANGLE_MIN = 1.0
_SPRAY_ANGLE_MAX = 179.0


@dataclass
class NozzleResult:
    orifice_diameter_mm: float   # 噴嘴孔徑 (mm)
    flowrate_lpm: float          # 實際流量 (L/min)
    exit_velocity: float         # 噴出流速 (m/s)
    impact_force_N: float        # 衝擊力 (N)
    impact_pressure_kpa: float   # 衝擊壓力 (kPa)
    spray_angle_deg: float       # 噴霧角度 (°)
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
    water_used_L: float = 0.0          # 本次清潔預估總用水量 (L)
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
        pressure_bar:        噴嘴前壓力 (bar)，必須 ≥ 0
        orifice_diameter_mm: 孔徑 (mm)，必須 > 0
        discharge_coeff:     流量係數 Cd（尖口噴嘴 0.61，圓角 0.82，預設 0.65）

    Returns:
        流量 (L/min)

    Raises:
        ValueError: pressure_bar < 0 或 orifice_diameter_mm ≤ 0
    """
    if pressure_bar < 0:
        raise ValueError(f"壓力不可為負，收到 {pressure_bar} bar")
    if orifice_diameter_mm <= 0:
        raise ValueError(f"噴嘴孔徑必須 > 0，收到 {orifice_diameter_mm} mm")
    if pressure_bar == 0:
        return 0.0

    rho = 998.2  # 水密度 kg/m³ @ 20°C
    delta_p = pressure_bar * 1e5
    d = orifice_diameter_mm / 1000
    area = math.pi * (d / 2) ** 2
    velocity = discharge_coeff * math.sqrt(2 * delta_p / rho)
    return area * velocity * 1000 * 60  # L/min


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
        pressure_bar:        噴嘴前壓力 (bar)，必須 ≥ 0
        orifice_diameter_mm: 孔徑 (mm)，必須 > 0
        distance_mm:         噴嘴到目標面距離 (mm)，必須 > 0
        spray_angle_deg:     噴霧全角 (度)，有效範圍 [1, 179]

    Raises:
        ValueError: 任何參數超出有效範圍
    """
    if pressure_bar < 0:
        raise ValueError(f"壓力不可為負，收到 {pressure_bar} bar")
    if orifice_diameter_mm <= 0:
        raise ValueError(f"噴嘴孔徑必須 > 0，收到 {orifice_diameter_mm} mm")
    if distance_mm <= 0:
        raise ValueError(f"目標距離必須 > 0，收到 {distance_mm} mm")
    if not (_SPRAY_ANGLE_MIN <= spray_angle_deg <= _SPRAY_ANGLE_MAX):
        raise ValueError(
            f"噴霧角必須在 [{_SPRAY_ANGLE_MIN}, {_SPRAY_ANGLE_MAX}]° 範圍內，"
            f"收到 {spray_angle_deg}°"
        )

    if pressure_bar == 0:
        return NozzleResult(
            orifice_diameter_mm=orifice_diameter_mm, flowrate_lpm=0.0,
            exit_velocity=0.0, impact_force_N=0.0, impact_pressure_kpa=0.0,
            spray_angle_deg=spray_angle_deg, coverage_width_mm=0.0,
        )

    rho = 998.2
    delta_p = pressure_bar * 1e5
    d = orifice_diameter_mm / 1000
    area = math.pi * (d / 2) ** 2

    exit_velocity = discharge_coeff * math.sqrt(2 * delta_p / rho)
    Q_m3s = area * exit_velocity
    Q_lpm = Q_m3s * 1000 * 60

    impact_force = rho * Q_m3s * exit_velocity

    coverage_radius = (distance_mm / 1000) * math.tan(math.radians(spray_angle_deg / 2))
    coverage_area = math.pi * coverage_radius ** 2
    impact_pressure_pa = impact_force / coverage_area if coverage_area > 0 else 0.0

    return NozzleResult(
        orifice_diameter_mm=orifice_diameter_mm,
        flowrate_lpm=Q_lpm,
        exit_velocity=exit_velocity,
        impact_force_N=impact_force,
        impact_pressure_kpa=impact_pressure_pa / 1000,
        spray_angle_deg=spray_angle_deg,
        coverage_width_mm=coverage_radius * 2 * 1000,
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
        equipment_name:       冷氣型號或描述
        evaporator_width_mm:  蒸發器寬度 (mm)，必須 > 0
        evaporator_height_mm: 蒸發器高度 (mm)，必須 > 0
        supply_pressure_bar:  水源供應壓力 (bar)，必須 ≥ 0
        pipe_diameter_mm:     清潔管路內徑 (mm)，預設 9.5mm（3/8"）
        pipe_length_m:        清潔管路總長度 (m)
        target_distance_mm:   噴嘴到蒸發器距離 (mm)

    Raises:
        ValueError: 任何尺寸參數 ≤ 0 或壓力 < 0
    """
    if supply_pressure_bar < 0:
        raise ValueError(f"供應壓力不可為負，收到 {supply_pressure_bar}")
    if evaporator_width_mm <= 0 or evaporator_height_mm <= 0:
        raise ValueError("蒸發器尺寸必須 > 0")
    if pipe_diameter_mm <= 0:
        raise ValueError(f"管路內徑必須 > 0，收到 {pipe_diameter_mm}")

    warnings_list = []
    pipe_d = pipe_diameter_mm / 1000

    # 依供應壓力選擇噴嘴孔徑（閾值說明見 pressure.py 常數定義）
    if supply_pressure_bar < _NOZZLE_LOW_PRESSURE:
        orifice_d = 1.2
    elif supply_pressure_bar < _NOZZLE_MED_PRESSURE:
        orifice_d = 1.5
    elif supply_pressure_bar < _NOZZLE_HIGH_PRESSURE:
        orifice_d = 2.0
    else:
        orifice_d = 2.5

    # 迭代求解壓力-流量耦合平衡
    nozzle_p = supply_pressure_bar * 0.9
    for _ in range(15):
        Q = nozzle_flowrate(nozzle_p, orifice_d)
        new_nozzle_p = available_nozzle_pressure(
            supply_pressure_bar=supply_pressure_bar,
            pipe_diameter=pipe_d,
            pipe_length=pipe_length_m,
            flowrate_lpm=Q,
            temperature_C=temperature_C,
        )
        if abs(new_nozzle_p - nozzle_p) < 1e-4:
            break
        nozzle_p = new_nozzle_p

    pipe_loss = supply_pressure_bar - nozzle_p

    if nozzle_p < _NOZZLE_LOW_PRESSURE:
        warnings_list.append(
            f"警告：噴嘴前壓力僅 {nozzle_p:.2f} bar，清潔效果可能不足（建議 ≥ {_NOZZLE_LOW_PRESSURE} bar）"
        )

    spray_angle = 25.0 if nozzle_p >= _NOZZLE_MED_PRESSURE else 15.0
    nozzle = nozzle_impact_force(
        pressure_bar=nozzle_p,
        orifice_diameter_mm=orifice_d,
        distance_mm=target_distance_mm,
        spray_angle_deg=spray_angle,
    )

    # 清潔道次與時間估算
    if nozzle.coverage_width_mm > 0:
        passes_needed = math.ceil(evaporator_height_mm / nozzle.coverage_width_mm)
    else:
        passes_needed = 5
        warnings_list.append("無法計算噴霧覆蓋寬度，道次數使用預設值 5")

    time_per_pass_min = 0.5  # 每道次約 30 秒（手動掃噴經驗值）
    cleaning_time = passes_needed * time_per_pass_min + 2  # +2 分鐘設備準備

    if supply_pressure_bar < 2.0:
        warnings_list.append("水源壓力低於 2 bar，建議使用加壓泵")
    if nozzle.impact_pressure_kpa < 10:
        warnings_list.append("衝擊壓力偏低，翅片深層污垢清潔效果有限，建議搭配清潔劑")
    if nozzle.impact_pressure_kpa > _MAX_IMPACT_KPA_ALUMINUM:
        warnings_list.append(
            f"衝擊壓力 {nozzle.impact_pressure_kpa:.0f} kPa 超過鋁翅片安全上限 "
            f"{_MAX_IMPACT_KPA_ALUMINUM:.0f} kPa，注意翅片變形風險"
        )

    procedure = [
        "1. 切斷冷氣電源，確認安全後再開始",
        "2. 拆除冷氣前蓋，露出蒸發器翅片",
        f"3. 噴嘴維持距翅片 {target_distance_mm:.0f} mm，由上而下水平掃噴",
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
        water_used_L=nozzle.flowrate_lpm * cleaning_time,
        warnings=warnings_list,
        procedure=procedure,
    )
