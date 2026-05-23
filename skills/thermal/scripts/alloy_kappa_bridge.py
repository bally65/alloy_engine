"""
alloy_engine κ 橋接腳本 — 從合金成分直接計算翅片熱效率
將 alloy_engine 的 thermal_conductivity_estimate() 接入 fin_efficiency_from_kappa()

用法:
  python scripts/alloy_kappa_bridge.py \\
    --Fe 0.70 --Ni 0.20 --Co 0.10 \\
    --fin-height 15 --fin-thickness 0.1 --h-conv 30

成分輸入順序對應 alloy_engine ELEMENTS = [Fe, Ni, Co, Cr, Mn, Cu, Mo, Si, Al, V]
成分之和應為 1.0（atomic fraction）
"""
import argparse
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from fluidsim_skills.thermal import fin_efficiency_from_kappa


def main():
    parser = argparse.ArgumentParser(
        description='alloy_engine κ → 翅片熱效率橋接',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    # 合金成分（atomic fractions）
    parser.add_argument('--Fe', type=float, default=0.0)
    parser.add_argument('--Ni', type=float, default=0.0)
    parser.add_argument('--Co', type=float, default=0.0)
    parser.add_argument('--Cr', type=float, default=0.0)
    parser.add_argument('--Mn', type=float, default=0.0)
    parser.add_argument('--Cu', type=float, default=0.0)
    parser.add_argument('--Mo', type=float, default=0.0)
    parser.add_argument('--Si', type=float, default=0.0)
    parser.add_argument('--Al', type=float, default=0.0)
    parser.add_argument('--V',  type=float, default=0.0)
    # 翅片幾何
    parser.add_argument('--fin-height',    type=float, default=15.0, help='翅片高度 (mm)')
    parser.add_argument('--fin-thickness', type=float, default=0.10, help='翅片厚度 (mm)')
    parser.add_argument('--h-conv',        type=float, default=30.0, help='對流係數 (W/m²·K)')
    args = parser.parse_args()

    composition = [args.Fe, args.Ni, args.Co, args.Cr, args.Mn,
                   args.Cu, args.Mo, args.Si, args.Al, args.V]
    total = sum(composition)

    if total <= 0:
        print("錯誤：請輸入至少一種元素的成分（--Fe 0.7 等）")
        sys.exit(1)

    # 正規化（容忍浮點誤差）
    composition = [x / total for x in composition]

    # 嘗試使用 alloy_engine 計算 κ
    kappa = None
    try:
        import torch
        from alloy_engine.thermomagnetic.properties import thermal_conductivity_estimate
        comp_tensor = torch.tensor([composition], dtype=torch.float32)
        kappa = thermal_conductivity_estimate(comp_tensor).item()
        source = "alloy_engine linear mixing"
    except ImportError:
        # alloy_engine 未安裝時，用純元素加權計算（與 alloy_engine 公式相同）
        KAPPA_PURE = [80.0, 91.0, 100.0, 94.0, 7.8, 401.0, 138.0, 149.0, 237.0, 31.0]
        kappa = sum(c * k for c, k in zip(composition, KAPPA_PURE))
        source = "linear mixing fallback（alloy_engine 未安裝）"

    report = fin_efficiency_from_kappa(
        fin_height_mm=args.fin_height,
        fin_thickness_mm=args.fin_thickness,
        kappa_W_mK=kappa,
        h_conv=args.h_conv,
    )

    elements = ['Fe', 'Ni', 'Co', 'Cr', 'Mn', 'Cu', 'Mo', 'Si', 'Al', 'V']
    comp_str = ', '.join(f"{e}={c:.3f}" for e, c in zip(elements, composition) if c > 1e-6)

    print(f"\nalloy_engine κ → 翅片效率橋接")
    print(f"{'═'*50}")
    print(f"  成分:         {comp_str}")
    print(f"  κ 來源:       {source}")
    print(f"  κ 估算值:     {kappa:.2f} W/m·K")
    print(f"{'─'*50}")
    print(f"  翅片高度:     {report.fin_height_mm:.1f} mm")
    print(f"  翅片厚度:     {report.fin_thickness_mm:.2f} mm")
    print(f"  翅片參數 m:   {report.m_parameter:.2f} m⁻¹")
    print(f"  翅片效率 η:   {report.fin_efficiency:.3f} ({report.fin_efficiency:.1%})")
    print(f"  vs 標準鋁:    {report.heat_transfer_improvement}")
    for note in report.notes:
        print(f"  → {note}")
    print(f"{'═'*50}")


if __name__ == '__main__':
    main()
