"""
基準磁熱材料整機效能評估 — 「換材料」會把天花板抬升多少？
==========================================================

把 reference_materials.py 的文獻材料逐一餵進整機設計模組：
  - 正向：design_layered_tmg（8 層 + 回熱的升級架構），各材料在自己 Tc 窗工作
  - 反向：design_refrigerator（室溫製冷對偶）

輸出：results/tmg_design/
  - reference_materials.md   比較表
  - reference_materials.png  ΔM / 功率密度 / 效率 / COP 對照長條圖

執行：python scripts/evaluate_reference_materials.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alloy_engine.thermomagnetic.reference_materials import REFERENCE_MATERIALS
from alloy_engine.thermomagnetic.generator_design import design_layered_tmg
from alloy_engine.thermomagnetic.magnetocaloric_refrigeration import design_refrigerator

OUT = Path(__file__).resolve().parent.parent / "results" / "tmg_design"
OUT.mkdir(parents=True, exist_ok=True)

# 升級架構參數（與 simulate_tmg_design.py 一致）
B_APP = 1.4
EPS_REGEN = 0.90
PLATE_L = 5e-4
N_LAYERS = 8
HALF_WINDOW = 30.0   # 各材料在 Tc ± 30K 工作


def evaluate() -> list[dict]:
    rows = []
    for name, m in REFERENCE_MATERIALS.items():
        t_lo = m.Tc_C - HALF_WINDOW
        t_hi = m.Tc_C + HALF_WINDOW
        gen = design_layered_tmg(
            T_cold_C=t_lo, T_hot_C=t_hi,
            layer_delta_M_T=[m.delta_M_T] * N_LAYERS,
            rho=m.rho, cp_specific=m.cp_specific, kappa=m.kappa,
            delta_S_M=m.delta_S_M, B_applied_T=B_APP,
            extra_regeneration=EPS_REGEN, plate_thickness_m=PLATE_L,
        )
        # 反向製冷：固定室溫 26K span，磁滯依相變類型給代表值
        w_hyst = 50.0 if m.transition == "2nd" else 250.0   # 一階磁滯較大
        fri = design_refrigerator(
            T_cold_C=-3, T_hot_C=23, delta_S_M=m.delta_S_M,
            cp_specific=m.cp_specific, B_applied_T=B_APP, f_Hz=10.0,
            hysteresis_loss_J_kg=w_hyst,
        )
        rows.append(dict(m=m, gen=gen, fri=fri, f_Hz=gen.layer_reports[0].f_Hz))
    return rows


def make_plot(rows: list[dict]) -> None:
    names = [r["m"].name.split(" ")[0] for r in rows]
    x = np.arange(len(names))
    dM = [r["m"].delta_M_T for r in rows]
    pden = [r["gen"].power_density_W_m3 / 1e3 for r in rows]
    eta = [r["gen"].eta_material * 100 for r in rows]
    cop = [r["fri"].cop for r in rows]

    fig, ax = plt.subplots(2, 2, figsize=(13, 9))
    colors = ["C0", "C1", "C2", "C3", "C4"]
    ax[0, 0].bar(x, dM, color=colors)
    ax[0, 0].set(title="(a) Cycle polarization swing delta_M (T)", ylabel="T")
    ax[0, 1].bar(x, pden, color=colors)
    ax[0, 1].set(title="(b) Generator power density (kW/m^3)", ylabel="kW/m^3")
    ax[1, 0].bar(x, eta, color=colors)
    ax[1, 0].set(title="(c) Generator efficiency (%)", ylabel="%")
    ax[1, 1].bar(x, cop, color=colors)
    ax[1, 1].set(title="(d) Reverse-mode cooling COP", ylabel="COP")
    for a in ax.flat:
        a.set_xticks(x)
        a.set_xticklabels(names, rotation=20, ha="right", fontsize=8)
        a.grid(alpha=0.3, axis="y")
    fig.suptitle("Reference MCM what-if: same upgraded device, different material",
                 fontsize=13)
    fig.tight_layout()
    fig.savefig(OUT / "reference_materials.png", dpi=130)
    plt.close(fig)


def write_report(rows: list[dict]) -> None:
    base_p = rows[0]["gen"].power_density_W_m3
    base_e = rows[0]["gen"].eta_material
    lines = [
        "# 基準磁熱材料整機 What-if 評估",
        "",
        "> 由 `scripts/evaluate_reference_materials.py` 產生。所有材料套用同一",
        f"> 升級架構（B={B_APP}T、{N_LAYERS} 層、回熱 ε={EPS_REGEN}、板厚",
        f"> {PLATE_L*1e3:.1f}mm），各自在其 Tc±{HALF_WINDOW:.0f}K 窗內工作。",
        "> 註：Gd/La-Fe-Si/Mn-Fe-P 含稀土或非引擎元素，GA 無法搜出，僅作 what-if。",
        "",
        "| 材料 | 相變 | Tc(°C) | ΔM(T) | Cp | κ | 功率密度(kW/m³) | 效率 η(%) | 對基準功率 | 反向COP |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        m, g, f = r["m"], r["gen"], r["fri"]
        p_ratio = g.power_density_W_m3 / base_p
        lines.append(
            f"| {m.name} | {m.transition} | {m.Tc_C:.0f} | {m.delta_M_T:.2f} | "
            f"{m.cp_specific:.0f} | {m.kappa:.0f} | {g.power_density_W_m3/1e3:,.0f} | "
            f"{g.eta_material*100:.3f} | ×{p_ratio:.1f} | {f.cop:.2f} |"
        )
    lines += [
        "",
        "## 重點觀察",
        "",
        f"- **ΔM 是功率的直接槓桿**：ΔM 從 0.20T（Fe 系）提到 1.1T（Mn-Fe-P）"
        f"，磁功 ∝ ΔM，但功率密度同時受 κ（→頻率）牽制。",
        "- **κ 是隱形殺手**：Gd5Si2Ge2/Mn-Fe-P 的 ΔM 大，但 κ 只有 3–5 W/mK"
        "（Fe 系 109），熱擴散慢→頻率低→功率密度被拉回，未必贏。",
        "- **Cp 決定效率**：Gd 的低 Cp（235）讓效率領先；La-Fe-Si 的高 Cp"
        "（700）即使 ΔM 大，效率仍被顯熱吃掉。",
        "- **結論**：單看 ΔM 會誤判。整機要的是 **高 ΔM × 高 κ × 低 Cp** 的組合；"
        "Fe 系贏在 κ，稀土系贏在 ΔM/ΔS。最佳解可能是 **高 κ 基底 + 高 ΔM 相**"
        "的複合材料（呼應文獻的 α-Fe / Al 強化 La-Fe-Si 思路）。",
        "",
        "詳見 `reference_materials.png`。",
    ]
    (OUT / "reference_materials.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    rows = evaluate()
    make_plot(rows)
    write_report(rows)
    print("═══════════ 基準材料整機 What-if 評估 ═══════════")
    base_p = rows[0]["gen"].power_density_W_m3
    for r in rows:
        m, g, f = r["m"], r["gen"], r["fri"]
        print(f"\n【{m.name}】({m.transition} order, Tc={m.Tc_C:.0f}°C, "
              f"ΔM={m.delta_M_T:.2f}T, κ={m.kappa:.0f})")
        print(f"  發電: P/V={g.power_density_W_m3/1e3:,.0f} kW/m³ "
              f"(×{g.power_density_W_m3/base_p:.1f} 基準)  η={g.eta_material*100:.3f}%  "
              f"f={r['f_Hz']:.1f}Hz  V={g.v_rms_volts:.1f}V")
        print(f"  製冷: COP={f.cop:.2f}  ε_ex={f.exergy_efficiency*100:.1f}%  "
              f"SCP={f.specific_cooling_power_W_kg/1e3:.2f} kW/kg")
    print(f"\n輸出 → {OUT}/ (reference_materials.md, reference_materials.png)")


if __name__ == "__main__":
    main()
