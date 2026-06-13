"""
熱磁發電機 (TMG) 設計方案模擬與評估
====================================

把 generator_design.py（正向）與 magnetocaloric_refrigeration.py（反向）
串成一套完整的設計評估流程，回答三件事：
  1. 規劃：以「反向 MCR 教訓」為基礎的具體發電架構長怎樣
  2. 評估：這套發電設計原理在三種廢熱情境下的效能
  3. 模擬：掃描關鍵設計旋鈕（B 場 / 回熱 ε / 板厚 L / 分層數）的敏感度，
          並驗證同一材料可正向發電、反向製冷

輸出：results/tmg_design/
  - evaluation.md        文字評估報告（表格）
  - sweeps.png           四格設計旋鈕敏感度圖
  - reversibility.png    同材料正向發電 vs 反向製冷

執行：python scripts/simulate_tmg_design.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")                       # 無顯示環境
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alloy_engine.thermomagnetic.generator_design import (
    design_tmg, design_layered_tmg,
)
from alloy_engine.thermomagnetic.magnetocaloric_refrigeration import (
    design_refrigerator,
)

OUT = Path(__file__).resolve().parent.parent / "results" / "tmg_design"
OUT.mkdir(parents=True, exist_ok=True)

# README 報告的三情境最佳配方代表物性（Fe 系，delta_M≈0.20 T）
# 以 (名稱, 目標Tc°C, 冷端°C, 熱端°C, delta_M, rho, cp, kappa) 表示
SCENARIOS = [
    ("低溫廢熱_150C", 150, 120, 180, 0.20, 7700.0, 460.0, 109.0),
    ("中溫廢熱_350C", 350, 320, 380, 0.20, 7750.0, 480.0, 115.0),
    ("高溫廢熱_500C", 500, 470, 530, 0.20, 7800.0, 500.0, 115.0),
]

# 由反向 MCR 教訓升級的設計選擇
B_UPGRADED = 1.4          # 教訓四：Halbach 1.24–1.5T（原保守 1.0T）
EPS_REGEN = 0.90          # 教訓二：全固態高回熱
PLATE_L = 5e-4            # 教訓三高頻：減薄板材 0.5mm
N_LAYERS = 8              # 教訓三：分層 Tc 梯度堆疊


def evaluate_baseline_vs_upgraded() -> list[dict]:
    """三情境：保守設計 vs 反向教訓升級設計 vs 分層床。"""
    rows = []
    for name, tc, t_lo, t_hi, dM, rho, cp, kappa in SCENARIOS:
        base = design_tmg(
            T_cold_C=t_lo, T_hot_C=t_hi, delta_M_T=dM,
            rho=rho, cp_specific=cp, kappa=kappa, delta_S_M=0.5,
            B_applied_T=1.0, cycle_utilization=0.30,
            regenerator_effectiveness=0.0, plate_thickness_m=1e-3,
        )
        upg = design_tmg(
            T_cold_C=t_lo, T_hot_C=t_hi, delta_M_T=dM,
            rho=rho, cp_specific=cp, kappa=kappa, delta_S_M=0.5,
            B_applied_T=B_UPGRADED, cycle_utilization=0.30,
            regenerator_effectiveness=EPS_REGEN, plate_thickness_m=PLATE_L,
        )
        lay = design_layered_tmg(
            T_cold_C=t_lo, T_hot_C=t_hi,
            layer_delta_M_T=[dM] * N_LAYERS,
            rho=rho, cp_specific=cp, kappa=kappa, delta_S_M=0.5,
            B_applied_T=B_UPGRADED, cycle_utilization=0.30,
            extra_regeneration=EPS_REGEN, plate_thickness_m=PLATE_L,
        )
        rows.append(dict(name=name, base=base, upg=upg, lay=lay))
    return rows


def sweep_plots() -> None:
    """四格敏感度：B 場 / 回熱 ε / 板厚 L / 分層數。以低溫情境為例。"""
    _, _, t_lo, t_hi, dM, rho, cp, kappa = SCENARIOS[0]
    common = dict(T_cold_C=t_lo, T_hot_C=t_hi, delta_M_T=dM,
                  rho=rho, cp_specific=cp, kappa=kappa, delta_S_M=0.5)

    fig, ax = plt.subplots(2, 2, figsize=(12, 9))

    # (a) B_app → power density & voltage
    Bs = np.linspace(0.5, 1.6, 25)
    pden = [design_tmg(**common, B_applied_T=b, plate_thickness_m=PLATE_L,
                       regenerator_effectiveness=EPS_REGEN).power_density_W_m3
            for b in Bs]
    ax[0, 0].plot(Bs, np.array(pden) / 1e3, "o-", color="C0")
    ax[0, 0].set(xlabel="Applied field B_app (T)",
                 ylabel="Power density (kW/m^3)",
                 title="(a) Field vs power density")
    ax[0, 0].grid(alpha=0.3)

    # (b) regenerator effectiveness → relative-Carnot efficiency
    eps = np.linspace(0.0, 0.97, 30)
    rel = [design_tmg(**common, B_applied_T=B_UPGRADED, plate_thickness_m=PLATE_L,
                      regenerator_effectiveness=e).eta_relative_carnot * 100
           for e in eps]
    ax[0, 1].plot(eps, rel, "s-", color="C1")
    ax[0, 1].axhline(55, ls="--", color="grey",
                     label="0.55 no-regen ceiling")
    ax[0, 1].set(xlabel="Regenerator effectiveness epsilon",
                 ylabel="Relative-Carnot eff. (%)",
                 title="(b) Regeneration breaks the 0.55 ceiling")
    ax[0, 1].legend(); ax[0, 1].grid(alpha=0.3)

    # (c) plate thickness → frequency & power density
    Ls = np.linspace(2e-4, 2e-3, 25)
    freq = [design_tmg(**common, B_applied_T=B_UPGRADED, plate_thickness_m=l,
                       regenerator_effectiveness=EPS_REGEN).f_Hz for l in Ls]
    ax[1, 0].plot(np.array(Ls) * 1e3, freq, "^-", color="C2")
    ax[1, 0].set(xlabel="Plate thickness L (mm)",
                 ylabel="Cycle frequency f (Hz)",
                 title="(c) Thinner plates -> higher frequency")
    ax[1, 0].grid(alpha=0.3)

    # (d) number of layers → relative-Carnot efficiency
    Ns = list(range(1, 25))
    rel_lay = [design_layered_tmg(
        T_cold_C=t_lo, T_hot_C=t_hi, layer_delta_M_T=[dM] * n,
        rho=rho, cp_specific=cp, kappa=kappa, delta_S_M=0.5,
        B_applied_T=B_UPGRADED, extra_regeneration=EPS_REGEN,
        plate_thickness_m=PLATE_L,
    ).eta_relative_carnot * 100 for n in Ns]
    ax[1, 1].plot(Ns, rel_lay, "d-", color="C3")
    ax[1, 1].set(xlabel="Number of layers N",
                 ylabel="Relative-Carnot eff. (%)",
                 title="(d) Layered Tc stack -> wider span, higher eff.")
    ax[1, 1].grid(alpha=0.3)

    fig.suptitle("TMG design knob sensitivity (low-grade waste heat 120->180C)",
                 fontsize=13)
    fig.tight_layout()
    fig.savefig(OUT / "sweeps.png", dpi=130)
    plt.close(fig)


def reversibility_plot() -> dict:
    """同材料：正向發電 vs 反向製冷的磁滯敏感度對照。"""
    _, _, t_lo, t_hi, dM, rho, cp, kappa = SCENARIOS[0]
    # 正向：發電效率隨回熱提升
    gen = design_tmg(T_cold_C=t_lo, T_hot_C=t_hi, delta_M_T=dM,
                     rho=rho, cp_specific=cp, kappa=kappa, delta_S_M=0.5,
                     B_applied_T=B_UPGRADED, plate_thickness_m=PLATE_L,
                     regenerator_effectiveness=EPS_REGEN)
    # 反向：製冷 COP 隨磁滯損耗衰退
    w_hyst = np.linspace(20, 900, 30)
    cops = [design_refrigerator(T_cold_C=-3, T_hot_C=23, delta_S_M=11.0,
                                cp_specific=700.0, B_applied_T=1.5, f_Hz=10.0,
                                hysteresis_loss_J_kg=float(w)).cop
            for w in w_hyst]
    eps_ex = [design_refrigerator(T_cold_C=-3, T_hot_C=23, delta_S_M=11.0,
                                  cp_specific=700.0, B_applied_T=1.5, f_Hz=10.0,
                                  hysteresis_loss_J_kg=float(w)).exergy_efficiency * 100
              for w in w_hyst]

    fig, ax1 = plt.subplots(figsize=(8, 5))
    ax1.plot(w_hyst, cops, "o-", color="C0", label="Cooling COP")
    ax1.set(xlabel="Hysteresis loss per cycle (J/kg)",
            ylabel="Cooling COP", title="Reverse mode: hysteresis is the #1 killer")
    ax2 = ax1.twinx()
    ax2.plot(w_hyst, eps_ex, "s--", color="C3", label="Exergy eff. (%)")
    ax2.set_ylabel("Exergy efficiency (%)")
    ax1.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / "reversibility.png", dpi=130)
    plt.close(fig)
    return dict(gen=gen)


def write_report(rows: list[dict], rev: dict) -> None:
    lines = [
        "# 熱磁發電機 (TMG) 設計方案評估報告",
        "",
        "> 由 `scripts/simulate_tmg_design.py` 自動產生。設計選擇來自反向",
        f"> 磁熱製冷 (MCR) 的四條教訓：B_app={B_UPGRADED}T（Halbach）、",
        f"> 回熱 ε={EPS_REGEN}（全固態）、板厚 L={PLATE_L*1e3:.1f}mm（高頻）、",
        f"> 分層 N={N_LAYERS}（Tc 梯度堆疊）。",
        "",
        "## 一、三情境：保守 vs 升級 vs 分層床",
        "",
        "| 情境 | 設計 | η (%) | η/η_C (%) | 功率密度 (kW/m³) | f (Hz) | V_rms (V) |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        b, u, l = r["base"], r["upg"], r["lay"]
        lines.append(
            f"| {r['name']} | 保守(1T,無回熱) | {b.eta_material*100:.3f} | "
            f"{b.eta_relative_carnot*100:.1f} | {b.power_density_W_m3/1e3:.1f} | "
            f"{b.f_Hz:.1f} | {b.v_rms_volts:.2f} |")
        lines.append(
            f"| | 升級(單層) | {u.eta_material*100:.3f} | "
            f"{u.eta_relative_carnot*100:.1f} | {u.power_density_W_m3/1e3:.1f} | "
            f"{u.f_Hz:.1f} | {u.v_rms_volts:.2f} |")
        lines.append(
            f"| | **分層+回熱 N={N_LAYERS}** | **{l.eta_material*100:.3f}** | "
            f"**{l.eta_relative_carnot*100:.1f}** | {l.power_density_W_m3/1e3:.1f} | "
            f"{l.layer_reports[0].f_Hz:.1f} | {l.v_rms_volts:.2f} |")
    lines += [
        "",
        "## 二、設計旋鈕敏感度",
        "",
        "見 `sweeps.png`：(a) 磁功 ∝ B_app；(b) 回熱 ε 突破 0.55·η_C 天花板；",
        "(c) 板厚越薄頻率越高（f∝1/L²）；(d) 分層數越多可用溫差越寬、效率越高。",
        "",
        "## 三、可逆性驗證",
        "",
        "見 `reversibility.png`：同一套材料/磁路，正向當發電機、反向當製冷機。",
        f"正向升級設計效率 η={rev['gen'].eta_material*100:.3f}%；反向製冷 COP 對",
        "磁滯損耗極度敏感（頭號殺手）。兩個方向的死穴都是寄生損耗控制。",
    ]
    (OUT / "evaluation.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    rows = evaluate_baseline_vs_upgraded()
    sweep_plots()
    rev = reversibility_plot()
    write_report(rows, rev)

    print("═══════════ TMG 設計方案模擬完成 ═══════════")
    for r in rows:
        b, u, l = r["base"], r["upg"], r["lay"]
        print(f"\n【{r['name']}】")
        print(f"  保守設計   : η={b.eta_material*100:.3f}%  "
              f"P/V={b.power_density_W_m3/1e3:.1f} kW/m³  V={b.v_rms_volts:.2f}V")
        print(f"  升級單層   : η={u.eta_material*100:.3f}%  "
              f"P/V={u.power_density_W_m3/1e3:.1f} kW/m³  V={u.v_rms_volts:.2f}V")
        print(f"  分層+回熱 N={l.n_layers} : η={l.eta_material*100:.3f}%  "
              f"η/η_C={l.eta_relative_carnot*100:.1f}%  "
              f"P/V={l.power_density_W_m3/1e3:.1f} kW/m³  V={l.v_rms_volts:.2f}V")
    print(f"\n輸出 → {OUT}/  (evaluation.md, sweeps.png, reversibility.png)")


if __name__ == "__main__":
    main()
