"""
積垢動力學計算模組
涵蓋：Kern-Seaton 積垢模型、清潔週期預測、TEMA 積垢熱阻資料庫
"""
import math
from dataclasses import dataclass, field
from typing import List


# TEMA（Tubular Exchanger Manufacturers Association）標準積垢熱阻值 (m²·K/W)
# 參考：TEMA 9th Edition, Table RGP-T-2.4
FOULING_RESISTANCE_DB = {
    'ac_indoor_unit':    {'Rf_star': 1.76e-4, 'Kf': 8.0e-4, 'description': '冷氣室內蒸發器（家用，灰塵+油脂）'},
    'ac_outdoor_unit':   {'Rf_star': 3.52e-4, 'Kf': 5.0e-4, 'description': '冷氣室外冷凝器（露天，灰塵+油煙）'},
    'city_water':        {'Rf_star': 1.76e-4, 'Kf': 2.0e-3, 'description': '城市自來水（輕微水垢）'},
    'coastal_air':       {'Rf_star': 5.28e-4, 'Kf': 6.0e-4, 'description': '沿海空氣（鹽霧+潮濕）'},
    'industrial_air':    {'Rf_star': 8.80e-4, 'Kf': 4.0e-4, 'description': '工業環境（油煙+粉塵）'},
    'kitchen_exhaust':   {'Rf_star': 1.76e-3, 'Kf': 3.0e-3, 'description': '廚房排氣（油脂積聚嚴重）'},
}

# 建議清潔的效率損失門檻（%）
_CLEAN_THRESHOLD_PCT = 10.0


@dataclass
class FoulingReport:
    """積垢分析完整報告"""
    elapsed_hours: float          # 已積垢時間 (h)
    current_Rf: float             # 當前積垢熱阻 (m²·K/W)
    asymptotic_Rf: float          # 漸近積垢熱阻 Rf* (m²·K/W)
    efficiency_penalty_pct: float # 熱傳效率損失 (%)
    time_to_threshold_h: float    # 距達清潔門檻的剩餘時間 (h)，0 表示已超標
    recommendation: str
    notes: List[str] = field(default_factory=list)


def kern_seaton_fouling(
    time_h: float,
    asymptotic_resistance: float,
    fouling_rate_constant: float,
) -> float:
    """
    Kern-Seaton 積垢模型。
    Rf(t) = Rf* × (1 − exp(−Kf · t))

    隨時間增長趨近漸近值 Rf*，反映積垢生長速率逐漸降低的物理過程。

    Args:
        time_h:                運行時間 (h)，必須 ≥ 0
        asymptotic_resistance: 漸近積垢熱阻 Rf* (m²·K/W)，必須 > 0
        fouling_rate_constant: 積垢速率常數 Kf (1/h)，必須 > 0

    Returns:
        當前積垢熱阻 Rf (m²·K/W)

    Raises:
        ValueError: time_h < 0 或其他參數 ≤ 0
    """
    if time_h < 0:
        raise ValueError(f"時間必須 ≥ 0，收到 {time_h}")
    if asymptotic_resistance <= 0:
        raise ValueError(f"漸近積垢熱阻必須 > 0，收到 {asymptotic_resistance}")
    if fouling_rate_constant <= 0:
        raise ValueError(f"積垢速率常數必須 > 0，收到 {fouling_rate_constant}")

    return asymptotic_resistance * (1 - math.exp(-fouling_rate_constant * time_h))


def fouling_penalty(
    Rf: float,
    U_clean: float,
) -> float:
    """
    計算積垢造成的熱傳效率損失百分比。
    U_fouled = 1 / (1/U_clean + Rf)
    penalty = (1 - U_fouled/U_clean) × 100

    Args:
        Rf:      當前積垢熱阻 (m²·K/W)，必須 ≥ 0
        U_clean: 乾淨換熱係數 U_clean (W/m²·K)，必須 > 0

    Returns:
        效率損失百分比 (%)，範圍 [0, 100)

    Raises:
        ValueError: Rf < 0 或 U_clean ≤ 0
    """
    if Rf < 0:
        raise ValueError(f"積垢熱阻不可為負，收到 {Rf}")
    if U_clean <= 0:
        raise ValueError(f"乾淨換熱係數必須 > 0，收到 {U_clean}")

    U_fouled = 1.0 / (1.0 / U_clean + Rf)
    penalty = (1.0 - U_fouled / U_clean) * 100.0
    return min(penalty, 99.9)  # 理論最大為 100%，實際不可達


def cleaning_interval(
    U_clean: float,
    asymptotic_Rf: float,
    fouling_rate_constant: float,
    target_efficiency_loss_pct: float = _CLEAN_THRESHOLD_PCT,
) -> float:
    """
    計算達到可接受效率損失門檻所需的時間（即建議清潔週期）。
    由 penalty = target 反解 Kern-Seaton 方程：
    t = −ln(1 − Rf_target/Rf*) / Kf

    Args:
        U_clean:                  乾淨換熱係數 (W/m²·K)，必須 > 0
        asymptotic_Rf:            漸近積垢熱阻 Rf* (m²·K/W)，必須 > 0
        fouling_rate_constant:    積垢速率常數 Kf (1/h)，必須 > 0
        target_efficiency_loss_pct: 觸發清潔的效率損失門檻 (%)，預設 10%

    Returns:
        建議清潔週期 (h)，若漸近值無法達到門檻則回傳 float('inf')

    Raises:
        ValueError: U_clean ≤ 0 或 asymptotic_Rf ≤ 0 或 Kf ≤ 0
    """
    if U_clean <= 0:
        raise ValueError(f"乾淨換熱係數必須 > 0，收到 {U_clean}")
    if asymptotic_Rf <= 0:
        raise ValueError(f"漸近積垢熱阻必須 > 0，收到 {asymptotic_Rf}")
    if fouling_rate_constant <= 0:
        raise ValueError(f"積垢速率常數必須 > 0，收到 {fouling_rate_constant}")

    # Rf 達到 target 時的值：penalty = target → Rf_target = target/(100·U_clean)·(1/(1-target/100)-0) 的反推
    # penalty = (1 - 1/(1 + Rf·U_clean)) × 100 = target
    # → 1/(1 + Rf·U) = (100-target)/100
    # → Rf = (100/(100-target) - 1) / U = target/(U·(100-target))
    target_frac = target_efficiency_loss_pct / 100.0
    if target_frac >= 1.0:
        raise ValueError("效率損失門檻必須 < 100%")

    Rf_target = target_frac / (U_clean * (1.0 - target_frac))

    if Rf_target >= asymptotic_Rf:
        return float('inf')  # 漸近值永遠不會達到門檻

    t = -math.log(1.0 - Rf_target / asymptotic_Rf) / fouling_rate_constant
    return t


def analyse_fouling(
    elapsed_hours: float,
    environment: str = 'ac_indoor_unit',
    U_clean: float = 50.0,
    target_loss_pct: float = _CLEAN_THRESHOLD_PCT,
) -> FoulingReport:
    """
    根據運行時間與環境類型生成積垢完整分析報告。

    Args:
        elapsed_hours: 上次清潔後已運行時數 (h)
        environment:   環境類型，需為 FOULING_RESISTANCE_DB 的鍵值
        U_clean:       乾淨換熱係數 (W/m²·K)，預設 50（典型分離式冷氣蒸發器）
        target_loss_pct: 觸發清潔的效率損失門檻 (%)

    Returns:
        FoulingReport

    Raises:
        ValueError: environment 不在 FOULING_RESISTANCE_DB 中
    """
    if environment not in FOULING_RESISTANCE_DB:
        valid = ', '.join(FOULING_RESISTANCE_DB.keys())
        raise ValueError(f"未知環境類型 '{environment}'，有效值：{valid}")

    db = FOULING_RESISTANCE_DB[environment]
    Rf_star = db['Rf_star']
    Kf = db['Kf']

    Rf = kern_seaton_fouling(elapsed_hours, Rf_star, Kf)
    penalty = fouling_penalty(Rf, U_clean)

    t_threshold = cleaning_interval(U_clean, Rf_star, Kf, target_loss_pct)
    remaining = 0.0 if t_threshold == float('inf') else max(0.0, t_threshold - elapsed_hours)

    # 計算此環境下漸近積垢的最大可能效率損失
    max_penalty = fouling_penalty(Rf_star, U_clean)

    notes = [f"環境：{db['description']}"]
    if penalty >= target_loss_pct:
        recommendation = f"已超過效率損失門檻 ({penalty:.1f}% ≥ {target_loss_pct:.0f}%)，建議立即清潔。"
        notes.append("積垢已影響冷暖效果，電費可能增加。")
    elif remaining == 0.0 and t_threshold == float('inf'):
        # 此環境漸近積垢不足以觸發門檻
        recommendation = (
            f"此環境積垢量輕微，即使長期運行效率損失最多僅 {max_penalty:.1f}%，"
            f"低於 {target_loss_pct:.0f}% 門檻。建議每 1–2 年定期清潔即可。"
        )
        notes.append(f"漸近最大效率損失：{max_penalty:.2f}%（此環境不會觸發 {target_loss_pct:.0f}% 門檻）")
    elif remaining < 200:
        recommendation = f"距清潔門檻約剩 {remaining:.0f} 小時，建議近期安排清潔。"
    else:
        recommendation = f"積垢在可接受範圍（效率損失 {penalty:.1f}%），下次清潔可在 {remaining:.0f} 小時後。"

    return FoulingReport(
        elapsed_hours=elapsed_hours,
        current_Rf=Rf,
        asymptotic_Rf=Rf_star,
        efficiency_penalty_pct=penalty,
        time_to_threshold_h=remaining,
        recommendation=recommendation,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# References
# ---------------------------------------------------------------------------
# [1] Kern, D.Q. & Seaton, R.E. (1959). "A theoretical analysis of thermal
#     surface fouling." British Chemical Engineering, 4(5), 258–262.
#     (Rf(t) = Rf*(1 − e^{−Kf·t}) asymptotic fouling model.)
# [2] Tubular Exchanger Manufacturers Association (TEMA, 2007).
#     Standards of the Tubular Exchanger Manufacturers Association, 9th ed.
#     Section 10 (fouling resistance values).
# [3] Müller-Steinhagen, H. (2000). Heat Exchanger Fouling: Mitigation and
#     Cleaning Techniques. IChemE. (Practical fouling data for HVAC systems.)
# [4] Somerscales, E.F.C. & Knudsen, J.G. (1981). Fouling of Heat Transfer
#     Equipment. Hemisphere Publishing. (Comprehensive fouling model review.)
# [5] ASHRAE Handbook — HVAC Systems and Equipment (2016). Chapter 23
#     (heat exchanger fouling factors for air-conditioning equipment).
