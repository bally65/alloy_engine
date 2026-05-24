"""
HVAC 清潔能源節約與 ROI 計算模組。

由積垢造成的額外耗電、清潔成本回收期、CO₂ 減排量估算。
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class EnergyROIReport:
    rated_power_kw: float
    power_increase_pct: float
    annual_hours: float
    annual_extra_kwh: float          # 積垢每年多耗電量 (kWh)
    annual_extra_cost: float         # 積垢每年多花費（電費，台幣）
    cleaning_cost: float             # 單次清潔費用（台幣）
    payback_months: float            # 清潔費用回收期（月）
    co2_reduction_kg: float          # 清潔後每年 CO₂ 減排量 (kg)
    recommendation: str


def energy_roi(
    rated_power_kw: float,
    power_increase_pct: float,
    annual_hours: float = 1500.0,
    electricity_price: float = 3.5,
    cleaning_cost: float = 1500.0,
    grid_emission_factor: float = 0.509,
) -> EnergyROIReport:
    """
    計算積垢造成的額外耗電與清潔投資回報。

    Args:
        rated_power_kw:       冷氣額定功率（壓縮機 + 風機）(kW)
        power_increase_pct:   因積垢造成的功率增幅 (%)，來自 analyse_airflow
        annual_hours:         年使用時數 (h)，台灣住宅典型 1200–1800 h
        electricity_price:    電費單價（台幣/kWh），台電住宅均價約 3.5
        cleaning_cost:        單次清潔費用（台幣），分離式約 800–2000
        grid_emission_factor: 電網排放係數（kg CO₂/kWh），台灣 2023 約 0.509

    Returns:
        EnergyROIReport

    Raises:
        ValueError: 功率 ≤ 0、power_increase_pct < 0、年時數 ≤ 0
    """
    if rated_power_kw <= 0:
        raise ValueError(f"額定功率必須 > 0，收到 {rated_power_kw}")
    if power_increase_pct < 0:
        raise ValueError(f"功率增幅不可為負，收到 {power_increase_pct}")
    if annual_hours <= 0:
        raise ValueError(f"年使用時數必須 > 0，收到 {annual_hours}")

    extra_kwh = rated_power_kw * (power_increase_pct / 100) * annual_hours
    extra_cost = extra_kwh * electricity_price
    co2_kg    = extra_kwh * grid_emission_factor

    if extra_cost > 0:
        payback_months = (cleaning_cost / extra_cost) * 12
    else:
        payback_months = float('inf')

    if payback_months <= 3:
        rec = (f"清潔效益顯著：每年節省 {extra_kwh:.0f} kWh（{extra_cost:.0f} 元），"
               f"清潔費用約 {payback_months:.1f} 個月內回收，強烈建議立即清潔。")
    elif payback_months <= 12:
        rec = (f"清潔有一定效益：每年節省 {extra_kwh:.0f} kWh（{extra_cost:.0f} 元），"
               f"約 {payback_months:.1f} 個月回收。建議列入年度保養計畫。")
    elif payback_months == float('inf'):
        rec = "積垢影響極微，電費節省不顯著，清潔可依衛生考量決定。"
    else:
        rec = (f"積垢影響有限，清潔費用需 {payback_months:.1f} 個月回收。"
               f"仍建議每 2 年清潔一次以維持設備壽命。")

    return EnergyROIReport(
        rated_power_kw=rated_power_kw,
        power_increase_pct=power_increase_pct,
        annual_hours=annual_hours,
        annual_extra_kwh=extra_kwh,
        annual_extra_cost=extra_cost,
        cleaning_cost=cleaning_cost,
        payback_months=payback_months,
        co2_reduction_kg=co2_kg,
        recommendation=rec,
    )


# ---------------------------------------------------------------------------
# References
# ---------------------------------------------------------------------------
# [1] Taiwan Power Company (2024). Residential electricity tariff schedule.
#     (電費單價 3.5 TWD/kWh 參考值)
# [2] Bureau of Energy, MOEA (2023). Taiwan grid emission factor 0.509 kg CO₂/kWh.
# [3] ASHRAE (2016). HVAC Systems and Equipment Handbook. Chapter 23
#     (fouling impact on compressor / fan power consumption).
# [4] Pak, B.C. et al. (1998). "Effect of fouling on air-side performance of
#     fin-and-tube heat exchangers." Int. J. Refrigeration, 21(5), 363–370.
