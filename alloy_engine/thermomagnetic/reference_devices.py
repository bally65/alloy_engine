"""
基準熱磁發電機（TMG）原型的文獻效能 — 發電側「整機」對標（缺陷 D12）
====================================================================

製冷側我們已對標 CAS 全固態 HMR（8.4 vs 文獻 8.3 kW/kg，吻合）。但**發電側**
此前無真實原型錨點，整機 P/V、η 的絕對值無從驗證。本模組收錄已發表的 TMG
原型量測值，讓 `evaluate_reference_devices` 把本引擎 `generator_design` 的預測
放在真實原型旁邊，誠實量化「絕對值差多少」。

重要結論（見 evaluate_reference_devices）：本引擎發電側模型的**效率**與最佳真實
原型同量級（~2× 內），但**絕對功率密度是理想化上界**——即使頻率對齊，仍約
高 10×（理想磁功、未計渦流/磁滯/漏磁/耦合損耗）；用預設 f_max=50Hz 更高約
100×。故本引擎發電側適合**相對比較與天花板估計**，不宜當絕對功率預測。

數值出處
--------
- Kishore & Priya, 熱磁裝置設計與效能綜述（OSTI 1538781, 2018）：
  Ujihara 2007、Christiaanse & Brück、Hsu、Solomon、綜述代表值皆引自此文。
- 「High-performance thermomagnetic generator controlled by a magnetocaloric
  switch」, Nature Communications 14 (2023), PMC10412618：Gd 與 LaFeSiH/In。
- Waske et al., Nature Energy 4, 68–74 (2019)：pretzel 磁通拓撲（定性，
  數值未於本環境取得，列為定性參考）。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReferenceDevice:
    name: str
    year: int
    material: str
    T_cold_C: float
    T_hot_C: float
    frequency_Hz: float | None          # 循環頻率（None=未報告）
    power_density_mW_cm3: float | None   # 體積功率密度（材料體積，None=未報告）
    eta_rel_carnot_pct: float | None     # 相對卡諾效率 %（None=未報告）
    source: str
    note: str

    @property
    def delta_T_K(self) -> float:
        return self.T_hot_C - self.T_cold_C

    @property
    def power_density_W_m3(self) -> float | None:
        # 1 mW/cm³ = 1000 W/m³
        return None if self.power_density_mW_cm3 is None else self.power_density_mW_cm3 * 1000.0


# 已發表 TMG 原型量測值（量級正確；數值如出處所載）
REFERENCE_DEVICES: dict[str, ReferenceDevice] = {
    "Ujihara 2007": ReferenceDevice(
        "Ujihara 2007", 2007, "Gd", T_cold_C=20, T_hot_C=30,
        frequency_Hz=None, power_density_mW_cm3=0.42, eta_rel_carnot_pct=None,
        source="Kishore & Priya 綜述 (OSTI 1538781)",
        note="懸臂式共振 TMG；ΔT=10K",
    ),
    "Christiaanse & Brück": ReferenceDevice(
        "Christiaanse & Brück", 2014, "MnFe(P,As) 系", T_cold_C=20, T_hot_C=25,
        frequency_Hz=None, power_density_mW_cm3=0.11, eta_rel_carnot_pct=None,
        source="Kishore & Priya 綜述 (OSTI 1538781)",
        note="靜態概念驗證 TMG；ΔT=5K",
    ),
    "Kishore & Priya (綜述代表)": ReferenceDevice(
        "Kishore & Priya (綜述代表)", 2018, "Gd", T_cold_C=20, T_hot_C=70,
        frequency_Hz=2.0, power_density_mW_cm3=3.0, eta_rel_carnot_pct=None,
        source="Kishore & Priya 綜述 (OSTI 1538781)",
        note="綜述彙整代表值；2 Hz、ΔT=50K",
    ),
    "Nat.Commun.2023 Gd": ReferenceDevice(
        "Nat.Commun.2023 Gd", 2023, "Gd", T_cold_C=5, T_hot_C=90,
        frequency_Hz=0.25, power_density_mW_cm3=3.2, eta_rel_carnot_pct=0.18,
        source="Nat. Commun. 14 (2023), PMC10412618",
        note="磁熱開關控制；P_Dmax=3.2 mW/cm³（平均 156 µW/cm³）、ΔT=85K",
    ),
    "Nat.Commun.2023 LaFeSiH/In": ReferenceDevice(
        "Nat.Commun.2023 LaFeSiH/In", 2023, "La(Fe,Si)13H + In", T_cold_C=5, T_hot_C=90,
        frequency_Hz=0.25, power_density_mW_cm3=4.0, eta_rel_carnot_pct=0.14,
        source="Nat. Commun. 14 (2023), PMC10412618",
        note="一階材料 + In；P_Dmax=4.0 mW/cm³（平均 232 µW/cm³）、ΔT=85K",
    ),
}

# 真實 TMG 原型量級帶（供 sanity-check 用）：功率密度 mW/cm³ 與頻率 Hz
REAL_POWER_DENSITY_BAND_mW_cm3 = (0.1, 4.0)
REAL_FREQUENCY_BAND_Hz = (0.1, 2.0)
REAL_BEST_ETA_REL_CARNOT_PCT = 0.18


def get(name: str) -> ReferenceDevice:
    if name not in REFERENCE_DEVICES:
        raise KeyError(f"未知原型：{name}；可選 {list(REFERENCE_DEVICES)}")
    return REFERENCE_DEVICES[name]
