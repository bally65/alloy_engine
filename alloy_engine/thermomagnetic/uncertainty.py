"""
不確定度傳播（UQ）：把文獻 ±12% 的散布傳過整機模型 → 預測帶誤差條，而非單點值。
================================================================================

文獻 ΔS_M / ΔM 有典型 ±10–15% 的散布（多篇獨立量測）。本模組以 Monte Carlo 抽樣
這些不確定度，跑 design_tmg，回傳整機功率密度與效率的 mean ± std——讓預測誠實地
帶上誤差條。並附 D12 的「絕對功率為理想化上界」現實折減提示。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from alloy_engine.thermomagnetic import reference_materials as rm
from alloy_engine.thermomagnetic import literature_mce as lm
from alloy_engine.thermomagnetic.generator_design import design_tmg

# reference_materials → literature_mce 名稱對應（單一真實來源）
_REF_TO_LIT = {
    "Gd (純釓)": "Gd",
    "Gd5Si2Ge2": "Gd5Si2Ge2",
    "La(Fe,Si)13H": "La(Fe,Si)13H",
    "(Mn,Fe)2(P,Si)": "(Mn,Fe)2(P,Si)",
}


@dataclass
class UQResult:
    material: str
    T_operating_C: float
    power_W_m3_mean: float
    power_W_m3_std: float
    eta_rel_carnot_mean: float
    eta_rel_carnot_std: float
    power_realistic_W_m3: float   # 套 D12 折減（÷10）的現實估計
    n_samples: int

    def summary(self) -> str:
        p, ps = self.power_W_m3_mean, self.power_W_m3_std
        e, es = self.eta_rel_carnot_mean * 100, self.eta_rel_carnot_std * 100
        return (f"{self.material} @ {self.T_operating_C:g}°C："
                f"P/V = {p/1e3:.1f} ± {ps/1e3:.1f} kW/m³（理想），"
                f"現實 ≈ {self.power_realistic_W_m3/1e3:.1f} kW/m³（÷10, D12）；"
                f"η/η_C = {e:.2f} ± {es:.2f}%")


def device_performance_with_uncertainty(
    material_name: str,
    T_operating_C: float,
    *,
    delta_T_window: float = 30.0,
    B_applied_T: float = 1.4,
    plate_thickness_m: float = 5e-4,
    n_samples: int = 2000,
    d12_discount: float = 10.0,
    seed: int = 0,
) -> UQResult:
    """
    對某參考材料，Monte Carlo 傳播文獻 ΔM/ΔS 不確定度 → P/V、η 的 mean±std。

    ΔM 與 ΔS_M 以相對不確定度（取自 literature_mce，預設 ±12%）抽常態樣本。
    """
    mat = rm.get(material_name)
    # reference_materials 名稱 → literature_mce 名稱（單一真實來源；解決 "Gd (純釓)"≠"Gd"）
    lit_name = _REF_TO_LIT.get(material_name)
    rel_unc = lm.get(lit_name).dS_rel_uncertainty if lit_name else 0.12
    rng = np.random.default_rng(seed)

    # 註：design_tmg 以 delta_M_T（循環淨極化擺幅）為輸入，本身不取 logistic 銳度 w；
    # w 的文獻校準用於 GA 材料評分（magnetic_thermodynamic_score），不在此整機路徑。

    dM_samples = rng.normal(mat.delta_M_T, mat.delta_M_T * rel_unc, n_samples).clip(min=1e-3)
    dS_samples = rng.normal(mat.delta_S_M, mat.delta_S_M * rel_unc, n_samples).clip(min=0.0)

    powers, etas = [], []
    for dM, dS in zip(dM_samples, dS_samples):
        r = design_tmg(
            T_cold_C=T_operating_C - delta_T_window,
            T_hot_C=T_operating_C + delta_T_window,
            delta_M_T=float(dM), rho=mat.rho, cp_specific=mat.cp_specific,
            kappa=mat.kappa, delta_S_M=float(dS), B_applied_T=B_applied_T,
            plate_thickness_m=plate_thickness_m,
        )
        powers.append(r.power_density_W_m3)
        etas.append(r.eta_relative_carnot)
    powers, etas = np.array(powers), np.array(etas)

    p_mean = float(powers.mean())
    return UQResult(
        material=material_name, T_operating_C=T_operating_C,
        power_W_m3_mean=p_mean, power_W_m3_std=float(powers.std()),
        eta_rel_carnot_mean=float(etas.mean()), eta_rel_carnot_std=float(etas.std()),
        power_realistic_W_m3=p_mean / d12_discount, n_samples=n_samples,
    )
