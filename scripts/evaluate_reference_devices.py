"""
D12：發電側整機對標——把本引擎 generator_design 的預測放在真實 TMG 原型旁邊。

對每個有功率密度量測的原型，用相同的工作溫度與（若有）循環頻率跑本引擎模型，
量化「絕對值差多少」。製冷側已對標 CAS HMR；本腳本補上發電側的誠實錨點。

執行：python scripts/evaluate_reference_devices.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from alloy_engine.thermomagnetic import reference_devices as rd
from alloy_engine.thermomagnetic import reference_materials as rm
from alloy_engine.thermomagnetic.generator_design import design_tmg

# 把原型材料對映到本引擎的文獻物性（量級用）
MATERIAL_PROPS = {
    "Gd": "Gd (純釓)",
    "La(Fe,Si)13H + In": "La(Fe,Si)13H",
    "MnFe(P,As) 系": "(Mn,Fe)2(P,Si)",
}


def _our_pd(dev: rd.ReferenceDevice, match_freq: bool) -> tuple[float, float]:
    """回傳 (本引擎 P/V [mW/cm³], η/η_C [%])，可選把 f_max 對齊原型頻率。"""
    mat_key = MATERIAL_PROPS.get(dev.material)
    mat = rm.get(mat_key) if mat_key else rm.get("Gd (純釓)")
    f_max = dev.frequency_Hz if (match_freq and dev.frequency_Hz) else 50.0
    r = design_tmg(
        T_cold_C=dev.T_cold_C, T_hot_C=dev.T_hot_C,
        delta_M_T=mat.delta_M_T, rho=mat.rho, cp_specific=mat.cp_specific,
        kappa=mat.kappa, delta_S_M=mat.delta_S_M,
        B_applied_T=1.0, plate_thickness_m=1e-3, f_max_Hz=f_max,
    )
    return r.power_density_W_m3 / 1000.0, r.eta_relative_carnot * 100.0


def main() -> None:
    print("═" * 84)
    print(" D12 — 發電側整機對標：本引擎 generator_design vs 真實 TMG 原型")
    print("═" * 84)
    print(f"{'原型':<26}{'材料':<14}{'真實 P/V':>10}{'本(預設)':>10}"
          f"{'本(對齊f)':>11}{'真實η/ηC':>9}{'本η/ηC':>8}")
    print(f"{'':<26}{'':<14}{'mW/cm³':>10}{'mW/cm³':>10}{'mW/cm³':>11}{'%':>9}{'%':>8}")
    print("-" * 84)

    ratios_matched = []   # 僅取有報告頻率的原型（真正的同頻對標）
    for dev in rd.REFERENCE_DEVICES.values():
        if dev.power_density_mW_cm3 is None:
            continue
        pd_def, eta_def = _our_pd(dev, match_freq=False)
        pd_mat, eta_mat = _our_pd(dev, match_freq=True)
        real_eta = f"{dev.eta_rel_carnot_pct:.2f}" if dev.eta_rel_carnot_pct else "—"
        tag = "" if dev.frequency_Hz else "  (無報告f)"
        print(f"{dev.name:<26}{dev.material:<14}{dev.power_density_mW_cm3:>10.2f}"
              f"{pd_def:>10.1f}{pd_mat:>11.1f}{real_eta:>9}{eta_mat:>8.2f}{tag}")
        if dev.frequency_Hz:
            ratios_matched.append(pd_mat / dev.power_density_mW_cm3)

    print("-" * 84)
    if ratios_matched:
        import statistics
        gm = statistics.geometric_mean(ratios_matched)
        lo, hi = min(ratios_matched), max(ratios_matched)
        print(f" 同頻對標（僅有報告頻率者 n={len(ratios_matched)}）：本引擎 P/V 高估 "
              f"≈ {gm:.0f}×（{lo:.0f}–{hi:.0f}×）")
        print(" 最乾淨的直接實測（Nat. Commun. 2023）為 ~10–12×。")
        print(" 解讀：效率與最佳真實原型同量級（~2× 內）；但絕對功率密度為理想化上界，")
        print("       即使同頻仍高約 10×（未計渦流/磁滯/漏磁/耦合損耗），預設 f_max=50Hz")
        print("       更高約 100×。發電側宜作相對比較與天花板估計，非絕對功率預測。")
    print("═" * 84)
    print(" 定性參考：Waske et al., Nature Energy 4, 68–74 (2019) — pretzel 磁通拓撲，")
    print("           以磁路設計把 TMG 效能提升數量級（本環境未取得其數值）。")


if __name__ == "__main__":
    main()
