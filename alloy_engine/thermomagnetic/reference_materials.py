"""
基準磁熱材料 (reference MCMs) 的文獻物性 — 整機「換材料」what-if 研究
====================================================================

本引擎的元素空間為 Fe-Ni-Co-Cr-Mn-Cu-Mo-Si-Al-V，**不含稀土**，故 GA 結構上
無法搜出 Gd / La-Fe-Si 等高 ΔM 材料。本模組以文獻代表值收錄這些基準材料，
讓我們把它們直接餵進 generator_design / magnetocaloric_refrigeration，量化
「若改用這些材料，整機效能的天花板會抬升多少」。

數值為室溫附近、~1.5T 場下的**文獻代表估計值**（量級正確，非單點精確值）：
  delta_M  = 循環淨磁極化變化 ΔJ (T)，居禮溫度 ±30K 窗內的可恢復極化擺幅
  cp       = 質量比熱 (J/kg·K)        rho   = 密度 (kg/m³)
  kappa    = 熱導率 (W/m·K)           delta_S_M = 等溫磁熵變 (J/kg·K)

主要參考：Tishin & Spichkin 2003；Gschneidner & Pecharsky 2000；
         使用者提供之磁熱製冷文獻彙整（La-Fe-Si-H、Mn-Fe-P、Gd 各體系）。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReferenceMaterial:
    name: str
    Tc_C: float           # 居禮溫度 (°C)
    delta_M_T: float      # 循環淨磁極化變化 ΔJ (T)
    cp_specific: float    # J/kg·K
    rho: float            # kg/m³
    kappa: float          # W/m·K
    delta_S_M: float      # J/kg·K（文獻 @2T；與 literature_mce.dS_2T 對齊）
    transition: str       # "2nd" | "1st"
    note: str


# 文獻代表值。delta_S_M 已校準至文獻 @2T 值（單一真實來源 = literature_mce，
# 引用見 docs/LITERATURE_CALIBRATION.md），典型不確定度 ±12%。
REFERENCE_MATERIALS: dict[str, ReferenceMaterial] = {
    "Fe-Cr-Cu-Si (本引擎)": ReferenceMaterial(
        "Fe-Cr-Cu-Si (本引擎)", Tc_C=150, delta_M_T=0.20,
        cp_specific=460.0, rho=7700.0, kappa=109.0, delta_S_M=0.6,
        transition="2nd", note="GA 最佳 Fe 系；高 κ、低 ΔM，發電基準",
    ),
    "Gd (純釓)": ReferenceMaterial(
        "Gd (純釓)", Tc_C=21, delta_M_T=0.60,
        cp_specific=235.0, rho=7900.0, kappa=10.5, delta_S_M=5.0,
        transition="2nd", note="二階基準；@2T ΔS≈5（Dan'kov PRB 1998）；κ 低、稀土昂貴",
    ),
    "Gd5Si2Ge2": ReferenceMaterial(
        "Gd5Si2Ge2", Tc_C=3, delta_M_T=0.90,
        cp_specific=350.0, rho=7500.0, kappa=5.0, delta_S_M=14.0,
        transition="1st", note="巨磁熱；@2T ΔS≈14（Pecharsky & Gschneidner 1997）；κ 極低、Ge 昂貴",
    ),
    "La(Fe,Si)13H": ReferenceMaterial(
        "La(Fe,Si)13H", Tc_C=47, delta_M_T=1.00,
        cp_specific=700.0, rho=7200.0, kappa=9.0, delta_S_M=19.0,
        transition="1st", note="@2T ΔS≈19（Fujita 2003）；Tc 可氫化調 200–400K；高 Cp、氫脆",
    ),
    "(Mn,Fe)2(P,Si)": ReferenceMaterial(
        "(Mn,Fe)2(P,Si)", Tc_C=27, delta_M_T=1.10,
        cp_specific=600.0, rho=6800.0, kappa=3.5, delta_S_M=14.0,
        transition="1st", note="無稀土；@2T ΔS≈14（Tegus Nature 2002）；κ 極低、成型難",
    ),
}


def get(name: str) -> ReferenceMaterial:
    if name not in REFERENCE_MATERIALS:
        raise KeyError(f"未知材料：{name}；可選 {list(REFERENCE_MATERIALS)}")
    return REFERENCE_MATERIALS[name]
