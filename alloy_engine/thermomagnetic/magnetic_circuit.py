"""熱磁發電機磁路設計（取代 design model 的 ln() 磁體估算）。

以「最大能量積工作點 + 漏磁 + 溫度修正剩磁」做磁體尺寸，並判斷簡單氣隙 vs 需聚磁/Halbach。

物理（研究佐證，見 docs 架構研究）：
- 簡單 C 型氣隙：B_gap ≤ Br/σ_leak ≈ 0.8·Br（無法超過剩磁）。要更高 → 軟磁聚磁 / Halbach
  （Halbach 內孔場 B=Br·ln(ro/ri) 可超 Br；2T 旋轉 Halbach 原型已實證）。
- 工作於最大能量積 (B_m≈Br/2, H_m≈-Hc/2) → 磁體體積最省：
      V_magnet ≈ 4·μ_rec·(B_gap/Br_T)²·(A_gap·l_gap)        [兩極/迴路合計]
      聚磁倍率 C = 2·B_gap/Br_T（>1 表示需聚磁極靴 / Halbach）
  V_magnet ∝ (B_gap/Br)²：高場代價為二次方；∝ 氣隙體積；∝ 1/Br²（高溫經 Br_T 受罰）。
- 剩磁溫度係數：Br_T = Br25·(1+α·(T-25)/100)；NdFeB α≈-0.11%/°C、SmCo≈-0.03%/°C。
- 溫度上限：NdFeB SH≤150 / EH≤200°C；>200°C 用 SmCo (Sm2Co17, ~350°C)。磁體宜置「冷側」遠離熱端。
"""
from __future__ import annotations

import math
from dataclasses import dataclass

MU_0 = 4.0e-7 * math.pi


@dataclass(frozen=True)
class MagnetGrade:
    name: str
    Br25: float        # 25°C 剩磁 (T)
    BHmax: float       # 最大能量積 (J/m³)
    rho: float         # 密度 (kg/m³)
    tmax: float        # 最高工作溫度 (°C)
    alpha_pctC: float  # 剩磁溫度係數 (%/°C)
    price_usd_kg: float
    mu_rec: float = 1.05


GRADES: dict[str, MagnetGrade] = {
    "NdFeB-N42SH": MagnetGrade("NdFeB N42SH", 1.30, 318e3, 7500, 150, -0.11, 70.0),
    "NdFeB-N38EH": MagnetGrade("NdFeB N38EH", 1.24, 287e3, 7500, 200, -0.11, 95.0),
    "SmCo-2:17":   MagnetGrade("SmCo Sm2Co17", 1.05, 200e3, 8400, 350, -0.030, 120.0),
}


def br_at(grade: MagnetGrade, T_C: float) -> float:
    return grade.Br25 * (1.0 + grade.alpha_pctC / 100.0 * (T_C - 25.0))


def pick_grade(T_magnet_C: float, margin_C: float = 20.0) -> str:
    """依磁體所在溫度選等級（磁體宜置冷側；此處保守用其工作溫度）。"""
    for key in ("NdFeB-N42SH", "NdFeB-N38EH", "SmCo-2:17"):
        if GRADES[key].tmax >= T_magnet_C + margin_C:
            return key
    return "SmCo-2:17"


def size_magnet(
    B_gap_T: float,
    gap_total_m: float,
    A_gap_m2: float,
    T_magnet_C: float,
    grade_key: str | None = None,
    sigma_leak: float = 1.25,
    leakage: float = 1.0,
) -> dict:
    """為目標氣隙場尺寸磁體（最大能量積工作點）。回傳體積/質量/聚磁倍率/工作點/可行性。

    leakage：2D FEM 量得的漏磁/邊緣耦合因子（fem_magnetics.py，1.0=無漏；未優化 C 型 ~0.48，
    Halbach/優化聚磁 ~0.85–0.95）。<1 表示磁極面需更高場補償 → 磁體體積 ∝ 1/leakage²。
    """
    gk = grade_key or pick_grade(T_magnet_C)
    g = GRADES[gk]
    Br_T = br_at(g, T_magnet_C)
    if Br_T <= 0:
        return {"feasible": False, "reason": "Br(T)<=0（磁體過熱）", "grade": gk}

    B_cap_simple = Br_T / sigma_leak
    C = 2.0 * B_gap_T / Br_T                                   # 聚磁倍率（磁極面積/氣隙面積）
    regime = "simple_gap" if B_gap_T <= B_cap_simple else "flux_concentration/Halbach"

    Beff = B_gap_T / max(leakage, 1e-3)                        # 補償漏磁：磁極面需更高有效場
    V_gap = A_gap_m2 * gap_total_m
    V_magnet = 4.0 * g.mu_rec * (Beff / Br_T) ** 2 * V_gap     # 最大能量積尺寸（含漏磁補償）
    l_m = 2.0 * g.mu_rec * (Beff / Br_T) * gap_total_m         # 磁體軸向長（迴路合計）
    A_m = max(A_gap_m2, C * A_gap_m2)
    mass = V_magnet * g.rho
    cost = mass * g.price_usd_kg

    # 退磁裕度：最大能量積工作點 B_m≈Br/2；高溫膝點上移，等級已依 tmax 選。
    demag_margin_C = g.tmax - T_magnet_C
    ro_ri = math.exp(B_gap_T / Br_T) if regime != "simple_gap" else None

    return {
        "feasible": True, "grade": g.name, "grade_key": gk,
        "Br_25_T": g.Br25, "Br_at_T": round(Br_T, 3), "regime": regime,
        "B_cap_simple_T": round(B_cap_simple, 3), "concentration_C": round(C, 2),
        "leakage": leakage, "ro_over_ri": (round(ro_ri, 2) if ro_ri else None),
        "magnet_length_mm": round(l_m * 1e3, 1), "magnet_area_cm2": round(A_m * 1e4, 1),
        "magnet_volume_cm3": round(V_magnet * 1e6, 1),
        "magnet_mass_kg": round(mass, 2), "magnet_cost_usd": round(cost, 0),
        "demag_margin_C": round(demag_margin_C, 0),
    }


def calibrate_kappa(engine_kappa: float, cap: float = 30.0) -> float:
    """校準熱導率：引擎以純元素線性混合會高估固溶體 κ（忽略溶質散射）。
    濃固溶 Fe-Co-Ni-Al-Cr 文獻 κ≈15–30 W/mK，故封頂至 alloy-class 上限。"""
    return min(float(engine_kappa), cap)
