"""
端到端材料推薦（capstone）：把文獻數據 + 校準物理 + 成本 + 裝置現實整合成一個決策。
================================================================================

給定工作溫度、可用場強、稀土偏好，從文獻磁熱材料庫挑出最佳選擇，並回傳：
  - Tc 對齊（可調材料視為可對齊工作溫度）
  - 該場強下的 |ΔS_M|（文獻 + B^0.7 標度）
  - D5 一階銳度 w（文獻 FWHM 校準）
  - 原料成本（元素價格代理）
整合 literature_mce（文獻/成本/w）。透明加權，理由可追溯。
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from alloy_engine.thermomagnetic import literature_mce as lm


@dataclass
class Recommendation:
    name: str
    score: float
    tc_match: float
    dS_at_field: float
    cost_usd_kg: float
    w_K: float
    rare_earth_free: bool
    tc_tunable: bool
    rationale: str


def recommend_material(
    T_operating_C: float,
    field_T: float = 2.0,
    prefer_rare_earth_free: bool = False,
    tc_offset_K: float = 15.0,
    tc_sigma_K: float = 45.0,
) -> list[Recommendation]:
    """
    回傳依綜合分數排序的材料推薦清單。

    分數 = tc_match × ΔS(field) / sqrt(cost) × rare_earth_bonus
      - tc_match：可調 Tc 材料=1.0；否則對 |Tc-(T_op+offset)| 做 Gaussian。
      - ΔS(field)：文獻磁熵變（越大越好）。
      - 1/sqrt(cost)：成本懲罰（越便宜越好，開根號避免過度主導）。
      - rare_earth_bonus：偏好無稀土時 ×1.3。
    """
    T_op_K = T_operating_C + 273.15
    ideal_Tc = T_op_K + tc_offset_K
    out: list[Recommendation] = []
    for m in lm.LITERATURE_MCE.values():
        if m.tc_tunable:
            tc_match = 1.0
        else:
            tc_match = math.exp(-((m.Tc_K - ideal_Tc) ** 2) / (2 * tc_sigma_K ** 2))
        ds = m.dS_at_field(field_T)
        cost = m.cost_usd_kg()
        bonus = 1.3 if (prefer_rare_earth_free and m.rare_earth_free) else 1.0
        # 實用性警示（毒性/極貴/逆磁熱）大幅降權，避免推薦不可行材料
        caveat_penalty = 0.2 if m.caveat else 1.0
        score = tc_match * ds / math.sqrt(cost) * bonus * caveat_penalty
        bits = []
        bits.append("Tc 可調對齊" if m.tc_tunable else f"Tc={m.Tc_K:.0f}K 固定")
        bits.append(f"ΔS@{field_T:g}T={ds:.1f}")
        bits.append(f"${cost:.1f}/kg")
        if m.rare_earth_free:
            bits.append("無稀土")
        if m.caveat:
            bits.append(f"⚠ {m.caveat}")
        out.append(Recommendation(
            name=m.name, score=score, tc_match=tc_match, dS_at_field=ds,
            cost_usd_kg=cost, w_K=m.transition_width_w_K(),
            rare_earth_free=m.rare_earth_free, tc_tunable=m.tc_tunable,
            rationale="；".join(bits),
        ))
    out.sort(key=lambda r: r.score, reverse=True)
    return out
