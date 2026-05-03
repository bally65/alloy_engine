"""
Delta_M threshold sweep — trade-off visualization
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

OUT = Path(__file__).parent / "figures"
OUT.mkdir(exist_ok=True)

thresholds = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40]
actual_dM  = [0.1772, 0.1776, 0.1402, 0.2012, 0.2254, 0.2318, 0.2270]
fitness    = [0.6981, 0.6986, 0.6994, 0.6952, 0.5100, 0.3605, 0.1995]
tc_offset  = [+11.9, +10.1, -3.4, +15.4, +26.1, +28.8, +27.0]

thr = np.array(thresholds)
dM  = np.array(actual_dM)
fit = np.array(fitness)

# ── Figure 1: delta_M vs Threshold ─────────────────────────────────────────
fig, ax = plt.subplots(figsize=(8, 5))

ax.plot(thr, dM, "o-", color="#2196F3", linewidth=2, markersize=8, label="Actual delta_M (Top-1)")
ax.plot(thr, thr, "--", color="#9E9E9E", linewidth=1.2, label="y = x (threshold line)")

# physical ceiling
ceiling = max(dM)
ax.axhline(ceiling, color="#F44336", linestyle=":", linewidth=1.5,
           label=f"Physical ceiling ≈ {ceiling:.3f} T")

# unreachable zone
ax.axvspan(0.30, 0.42, alpha=0.08, color="red", label="Unreachable zone (thr > ceiling)")

# annotate pareto knee
ax.annotate("Pareto knee\n(−27% fitness for +12% delta_M)",
            xy=(0.25, 0.2254), xytext=(0.26, 0.19),
            arrowprops=dict(arrowstyle="->", color="#E53935"),
            fontsize=9, color="#E53935")

ax.annotate("v5.0 baseline\n(0.20 T, fit=0.695)",
            xy=(0.20, 0.2012), xytext=(0.10, 0.215),
            arrowprops=dict(arrowstyle="->", color="#388E3C"),
            fontsize=9, color="#388E3C")

ax.set_xlabel("delta_M Threshold (T)", fontsize=12)
ax.set_ylabel("Actual delta_M Top-1 (T)", fontsize=12)
ax.set_title("Delta_M: Threshold vs. Achievable Value\n(中溫廢熱_350C, 50K×100gen)", fontsize=12)
ax.legend(fontsize=9)
ax.set_xlim(0.03, 0.43)
ax.set_ylim(0.10, 0.27)
ax.grid(True, alpha=0.3)
fig.tight_layout()
fig.savefig(OUT / "fig1_delta_m_vs_threshold.png", dpi=150)
plt.close()

# ── Figure 2: Fitness vs Threshold ─────────────────────────────────────────
fig, ax1 = plt.subplots(figsize=(8, 5))

color_fit = "#2196F3"
color_tc  = "#FF9800"

ax1.plot(thr, fit, "o-", color=color_fit, linewidth=2.5, markersize=9, label="Top-1 Fitness")
ax1.set_xlabel("delta_M Threshold (T)", fontsize=12)
ax1.set_ylabel("Top-1 Fitness", fontsize=12, color=color_fit)
ax1.tick_params(axis="y", labelcolor=color_fit)
ax1.set_ylim(0.0, 0.85)

ax2 = ax1.twinx()
ax2.bar(thr, np.abs(tc_offset), width=0.025, alpha=0.35, color=color_tc, label="|Tc offset| (°C)")
ax2.set_ylabel("|Tc offset from 350°C| (°C)", fontsize=12, color=color_tc)
ax2.tick_params(axis="y", labelcolor=color_tc)
ax2.set_ylim(0, 60)

# mark sweet spot
ax1.axvline(0.20, color="#388E3C", linestyle="--", linewidth=1.5, alpha=0.7)
ax1.text(0.205, 0.72, "v5.0 baseline", color="#388E3C", fontsize=9, va="top")

# shade fitness cliff
ax1.axvspan(0.22, 0.42, alpha=0.06, color="red")
ax1.text(0.31, 0.55, "Fitness cliff\n(high threshold cost)", color="#E53935",
         fontsize=9, ha="center")

lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, labels1 + labels2, fontsize=9, loc="upper right")

ax1.set_title("Fitness & Tc Accuracy vs. delta_M Threshold\n(中溫廢熱_350C, 50K×100gen)", fontsize=12)
ax1.set_xlim(0.03, 0.43)
ax1.grid(True, alpha=0.3)
fig.tight_layout()
fig.savefig(OUT / "fig2_fitness_vs_threshold.png", dpi=150)
plt.close()

print("Figures saved:")
for f in sorted(OUT.iterdir()):
    print(f"  {f.name}")
