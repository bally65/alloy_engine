"""
v5.1 Pareto Knee Analysis — Publication-Quality Figures
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from pathlib import Path

OUT = Path(__file__).parent / "figures"
OUT.mkdir(exist_ok=True)

# ── Shared style ──────────────────────────────────────────────────────────────
plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "grid.linestyle": "--",
})

# ══════════════════════════════════════════════════════════════════════════════
# Figure 1: Pareto Shift — v5.0 vs v5.1 (Fitness vs Actual delta_M)
# ══════════════════════════════════════════════════════════════════════════════

# v5.0 data (from analysis/delta_m_boundary/trade_off_table.md)
v50_thr    = np.array([0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40])
v50_dm     = np.array([0.1772, 0.1776, 0.1402, 0.2012, 0.2254, 0.2318, 0.2270])
v50_fit    = np.array([0.6981, 0.6986, 0.6994, 0.6952, 0.5100, 0.3605, 0.1995])

# v5.1 data (from sweep_summary.csv)
v51_thr    = np.array([0.25, 0.30, 0.35, 0.40, 0.45, 0.50])
v51_dm     = np.array([0.4861, 0.4900, 0.5074, 0.4863, 0.4846, 0.4998])
v51_fit    = np.array([0.7798, 0.7798, 0.7796, 0.7794, 0.7789, 0.7707])

fig, ax = plt.subplots(figsize=(9, 5.5))

# v5.0 line
ax.plot(v50_dm, v50_fit, "o--", color="#9E9E9E", linewidth=2, markersize=7,
        label="v5.0 (Br ceiling 1.09 T)", zorder=3)

# v5.1 line
ax.plot(v51_dm, v51_fit, "s-", color="#1976D2", linewidth=2.5, markersize=8,
        label="v5.1 (Br ceiling 2.46 T, Slater-Pauling)", zorder=4)

# v5.0 knee annotation
ax.annotate("v5.0 Knee\n(0.20 T, fit=0.695)",
            xy=(0.2012, 0.6952), xytext=(0.24, 0.62),
            arrowprops=dict(arrowstyle="->", color="#757575"),
            fontsize=9, color="#616161",
            bbox=dict(boxstyle="round,pad=0.2", fc="white", alpha=0.8))

# v5.0 ceiling
ax.axvline(0.2318, color="#9E9E9E", linestyle=":", linewidth=1.2, alpha=0.7)
ax.text(0.235, 0.72, "v5.0 ceiling\n0.232 T", color="#9E9E9E", fontsize=8, va="top")

# v5.1 knee annotation
ax.annotate("v5.1 Knee\n(0.45 T, fit=0.779)",
            xy=(0.4846, 0.7789), xytext=(0.38, 0.74),
            arrowprops=dict(arrowstyle="->", color="#1565C0"),
            fontsize=9, color="#1565C0",
            bbox=dict(boxstyle="round,pad=0.2", fc="white", alpha=0.8))

# v5.1 fitness cliff shading
ax.axvspan(0.499, 0.52, alpha=0.08, color="#F44336", label="Fitness cliff zone")
ax.text(0.505, 0.755, "Cliff\n(0.50 T)", color="#C62828", fontsize=8, ha="center")

# v5.1 plateau shading
ax.axvspan(0.484, 0.510, alpha=0.06, color="#1976D2")
ax.text(0.497, 0.785, "Plateau\n0.25-0.45 T\n(-0.12% fitness)", color="#1565C0",
        fontsize=8, ha="center", va="bottom")

# Improvement arrow
ax.annotate("", xy=(0.4846, 0.7789), xytext=(0.2012, 0.6952),
            arrowprops=dict(arrowstyle="->", color="#43A047",
                           connectionstyle="arc3,rad=-0.2",
                           lw=1.8))
ax.text(0.33, 0.755, "+125% delta_M\n+12% fitness", color="#2E7D32",
        fontsize=9, ha="center",
        bbox=dict(boxstyle="round,pad=0.2", fc="#E8F5E9", alpha=0.85))

ax.set_xlabel("Actual delta_M Top-1 (T)", fontsize=12)
ax.set_ylabel("Top-1 Fitness", fontsize=12)
ax.set_title("Pareto Shift: v5.0 vs v5.1 Br Calibration\n"
             "Scenario: Mid-temp 350 C | 50K pop x 100 gen", fontsize=12)
ax.legend(fontsize=9, loc="upper left")
ax.set_xlim(0.10, 0.55)
ax.set_ylim(0.15, 0.85)
fig.tight_layout()
fig.savefig(OUT / "fig_pareto_shift.png", dpi=150)
plt.close()
print("Saved: fig_pareto_shift.png")

# ══════════════════════════════════════════════════════════════════════════════
# Figure 2: Co Emergence — GA discovers Slater-Pauling basin
# ══════════════════════════════════════════════════════════════════════════════

v51_co  = np.array([24.3, 27.4, 30.2, 29.4, 29.7, 30.8])   # at%
v51_fe  = np.array([39.1, 45.1, 43.1, 42.5, 44.7, 40.8])
v51_cr  = np.array([12.3, 18.1, 18.9, 18.6, 20.2, 14.1])

fig, ax1 = plt.subplots(figsize=(9, 5.5))

color_co = "#E53935"
color_fe = "#1E88E5"
color_cr = "#43A047"

ax1.plot(v51_thr, v51_co, "o-", color=color_co, linewidth=2.5, markersize=9,
         label="Co (at%)", zorder=4)
ax1.plot(v51_thr, v51_fe, "s--", color=color_fe, linewidth=2, markersize=7,
         label="Fe (at%)", zorder=3)
ax1.plot(v51_thr, v51_cr, "^--", color=color_cr, linewidth=2, markersize=7,
         label="Cr (at%)", zorder=3)

# Slater-Pauling peak reference band
# Peak magnetic moment at Fe50Co50 (Fe=50%, Co=50%), Br peak near Co=30-35% in Fe-Co-Cr
ax1.axhspan(28, 36, alpha=0.10, color=color_co,
            label="Slater-Pauling Br peak zone (~28-36% Co in Fe-Co base)")
ax1.axhline(30, color=color_co, linestyle=":", linewidth=1.5, alpha=0.7)
ax1.text(0.255, 31.2, "S-P peak (Fe50Co50 basis)", color="#B71C1C",
         fontsize=8.5, va="bottom")

# Zero-Co reference for v5.0 comparison
ax1.axhline(3, color="#9E9E9E", linestyle=":", linewidth=1.2, alpha=0.8)
ax1.text(0.255, 3.5, "v5.0 plateau Co ~3% (near-binary Fe-Cr)", color="#757575",
         fontsize=8.5, va="bottom")

# Pareto knee marker
knee_idx = 4  # thr=0.45
ax1.axvline(v51_thr[knee_idx], color="#FB8C00", linestyle="--", linewidth=1.8,
            label="New Pareto Knee (0.45 T)", alpha=0.85)
ax1.text(0.455, 22, "Knee\n0.45 T", color="#E65100", fontsize=9, ha="left", va="top")

ax1.set_xlabel("delta_M Threshold (T)", fontsize=12)
ax1.set_ylabel("Composition (at%)", fontsize=12)
ax1.set_title("Co Emergence: GA Discovers Slater-Pauling Basin\n"
              "v5.1 | Scenario: Mid-temp 350 C | 50K x 100 gen", fontsize=12)
ax1.set_xlim(0.23, 0.52)
ax1.set_ylim(0, 58)
ax1.legend(fontsize=8.5, loc="center right")

# right axis: fitness
ax2 = ax1.twinx()
ax2.plot(v51_thr, v51_fit, "D:", color="#7B1FA2", linewidth=1.5, markersize=6,
         alpha=0.7, label="Fitness (right axis)")
ax2.set_ylabel("Top-1 Fitness", fontsize=11, color="#7B1FA2")
ax2.tick_params(axis="y", labelcolor="#7B1FA2")
ax2.set_ylim(0.750, 0.800)
ax2.spines["right"].set_visible(True)

lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(
    ax1.get_legend_handles_labels()[0] + lines2,
    ax1.get_legend_handles_labels()[1] + labels2,
    fontsize=8.5, loc="lower left",
    ncol=2,
)

fig.tight_layout()
fig.savefig(OUT / "fig_co_emergence.png", dpi=150)
plt.close()
print("Saved: fig_co_emergence.png")

print("\nAll figures saved to:", OUT)
