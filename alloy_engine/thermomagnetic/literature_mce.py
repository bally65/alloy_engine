"""
文獻磁熱數據校準 + 最低成本材料分析（無儀器，純文獻 backfill）
================================================================

動機：學校外借磁量測儀器（VSM/PPMS）麻煩 → 採「文獻優先」校準。Gd / Gd5(Si,Ge)4 /
La(Fe,Si)13(H) / (Mn,Fe)2(P,Si) 是磁熱領域被量最多的材料，已發表 ΔS_M / Tc /
ΔT_ad / 磁滯數據充足，可直接回填模型，無需自行量測。

本模組：
  1. 收錄各材料的文獻代表值（含場強、相變階數、磁滯、引用）。
  2. 以元素價格代理計算原料相對成本（$/kg 量級）。
  3. 算「效能/成本」優值，找最低成本、可行的材料。

數值為文獻代表值（成分/場強相依，量級正確）：
  - ΔS_M 等溫磁熵變 |ΔS| (J/kg·K)；標明場強 2T（永磁裝置相關）或 5T。
  - 順序 order: "1st"（一階，巨磁熱、有磁滯）/ "2nd"（二階，無磁滯）。

引用見 docs/LITERATURE_CALIBRATION.md（Sources 一節）。
"""
from __future__ import annotations

from dataclasses import dataclass, field


# 元素原料價格代理（USD/kg，2020s 量級；用於相對成本排序，非精確報價）
ELEMENT_PRICE_USD_KG: dict[str, float] = {
    "Fe": 0.5, "Mn": 2.0, "P": 3.0, "Si": 2.0, "Al": 2.0, "Co": 30.0,
    "Ni": 15.0, "Cu": 8.0, "Cr": 9.0, "Mo": 30.0, "V": 25.0,
    "La": 5.0, "Gd": 60.0, "Ge": 1200.0,
}
# 原子量（g/mol），算質量分率用
_ATOMIC_MASS = {
    "Fe": 55.85, "Mn": 54.94, "P": 30.97, "Si": 28.09, "Ge": 72.63,
    "La": 138.91, "Gd": 157.25,
}


@dataclass(frozen=True)
class LiteratureMCE:
    name: str
    Tc_K: float
    dS_2T: float          # |ΔS_M| @ 2T (J/kg·K)
    dS_5T: float          # |ΔS_M| @ 5T (J/kg·K)
    dT_ad_2T: float       # ΔT_ad @ 2T (K)
    order: str            # "1st" / "2nd"
    hysteresis: str       # 定性：none / low / moderate / large
    approx_atoms: dict    # 近似原子配比（算成本用）
    source: str
    note: str
    rare_earth_free: bool = field(default=False)

    def cost_usd_kg(self) -> float:
        """以質量分率 × 元素價格估原料相對成本（$/kg 量級）。"""
        masses = {e: n * _ATOMIC_MASS[e] for e, n in self.approx_atoms.items()}
        m_tot = sum(masses.values())
        return sum((masses[e] / m_tot) * ELEMENT_PRICE_USD_KG[e]
                   for e in self.approx_atoms)

    def figure_of_merit_per_cost(self) -> float:
        """效能/成本：ΔS_M@2T ÷ 原料成本（越高越划算）。"""
        return self.dS_2T / (self.cost_usd_kg() + 1e-9)


# ── 文獻代表值（含場強、引用）──────────────────────────────────────────────
LITERATURE_MCE: dict[str, LiteratureMCE] = {
    "Gd": LiteratureMCE(
        "Gd", Tc_K=294.0, dS_2T=5.0, dS_5T=9.8, dT_ad_2T=5.7,
        order="2nd", hysteresis="none",
        approx_atoms={"Gd": 1.0},
        source="Dan'kov et al. PRB 1998；Pecharsky & Gschneidner",
        note="二階基準；無磁滯但稀土昂貴",
    ),
    "Gd5Si2Ge2": LiteratureMCE(
        "Gd5Si2Ge2", Tc_K=272.0, dS_2T=14.0, dS_5T=18.5, dT_ad_2T=7.3,
        order="1st", hysteresis="moderate",
        approx_atoms={"Gd": 5.0, "Si": 2.0, "Ge": 2.0},
        source="Pecharsky & Gschneidner PRL 1997（巨磁熱發現）",
        note="巨磁熱聖杯；Ge 使成本極高、有磁滯",
    ),
    "La(Fe,Si)13H": LiteratureMCE(
        "La(Fe,Si)13H", Tc_K=320.0, dS_2T=19.0, dS_5T=26.0, dT_ad_2T=6.5,
        order="1st", hysteresis="low",
        approx_atoms={"La": 1.0, "Fe": 11.5, "Si": 1.5},
        source="Fujita et al. PRB 2003；Brück 綜述 2011；APL 101,162406(2012)",
        note="Tc 可由氫化調 200–400K；氫化降磁滯；La 為廉價稀土",
    ),
    "(Mn,Fe)2(P,Si)": LiteratureMCE(
        "(Mn,Fe)2(P,Si)", Tc_K=290.0, dS_2T=14.0, dS_5T=17.6, dT_ad_2T=3.0,
        order="1st", hysteresis="low (tunable)",
        approx_atoms={"Mn": 1.0, "Fe": 1.0, "P": 0.5, "Si": 0.5},
        source="Tegus et al. Nature 2002；Dung/Brück；Rare Metals 2018 綜述",
        note="無稀土、巨磁熱；磁滯可由 Co/Ni/B/V/N 摻雜調低",
        rare_earth_free=True,
    ),
}


def get(name: str) -> LiteratureMCE:
    if name not in LITERATURE_MCE:
        raise KeyError(f"未知材料：{name}；可選 {list(LITERATURE_MCE)}")
    return LITERATURE_MCE[name]


def rank_by_value_per_cost() -> list[tuple[str, float, float, float]]:
    """回傳 [(name, ΔS@2T, cost$/kg, ΔS/cost)]，依 ΔS/cost 由高到低排序。"""
    rows = [(m.name, m.dS_2T, m.cost_usd_kg(), m.figure_of_merit_per_cost())
            for m in LITERATURE_MCE.values()]
    return sorted(rows, key=lambda r: r[3], reverse=True)
