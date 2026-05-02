"""
收斂曲線與配方熱圖
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
import seaborn as sns

from alloy_engine.data.elements import ELEMENTS

for font_name in ['Microsoft JhengHei', 'Microsoft YaHei', 'PMingLiU', 'SimHei', 'Noto Sans CJK TC']:
    if any(font_name in f.name for f in fm.fontManager.ttflist):
        plt.rcParams['font.sans-serif'] = [font_name]
        break
plt.rcParams['axes.unicode_minus'] = False


def plot_data_distribution(
    tc: np.ndarray,
    hc: np.ndarray,
    br: np.ndarray,
    sigma_y: np.ndarray,
    save_path: Path | str | None = None,
) -> None:
    """訓練資料的四格分佈直方圖。"""
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    axes[0, 0].hist(tc - 273.15, bins=60, color="red",    alpha=0.7)
    axes[0, 0].set_xlabel("Tc (°C)"); axes[0, 0].set_ylabel("Count")
    axes[0, 0].axvline(150, color="k", ls="--", lw=1)
    axes[0, 0].axvline(500, color="k", ls="--", lw=1)
    axes[0, 0].set_title("Curie Temperature")

    axes[0, 1].hist(hc,      bins=60, color="blue",   alpha=0.7)
    axes[0, 1].set_xlabel("Hc (A/m)"); axes[0, 1].set_title("Coercivity")

    axes[1, 0].hist(br,      bins=60, color="green",  alpha=0.7)
    axes[1, 0].set_xlabel("Br (T)"); axes[1, 0].set_title("Remanence")

    axes[1, 1].hist(sigma_y, bins=60, color="purple", alpha=0.7)
    axes[1, 1].set_xlabel("σy (MPa)"); axes[1, 1].set_title("Yield Strength")

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=120, bbox_inches="tight")
    plt.show()


def plot_convergence(
    results: dict,
    save_path: Path | str | None = None,
) -> None:
    """
    GA 收斂曲線（N 情境 × 4 欄）。

    results 格式：{scenario_name: {"history": {...}, "config": {...}}}
    """
    n_rows = len(results)
    fig, axes = plt.subplots(n_rows, 4, figsize=(20, 4 * n_rows))
    if n_rows == 1:
        axes = axes.reshape(1, -1)

    for r, (name, res) in enumerate(results.items()):
        h   = res["history"]
        cfg = res["config"]

        axes[r, 0].plot(h["best_fitness"], "r-", lw=2, label="best")
        axes[r, 0].plot(h["mean_fitness"], "b-", lw=1, alpha=0.6, label="mean")
        axes[r, 0].set_xlabel("Generation"); axes[r, 0].set_ylabel("Fitness")
        axes[r, 0].set_title(f"{name} | Convergence")
        axes[r, 0].legend(); axes[r, 0].grid(alpha=0.3)

        axes[r, 1].plot(h["best_tc_C"], "orange", lw=2)
        axes[r, 1].axhline(cfg["target_tc_celsius"], color="k", ls="--", label="target")
        axes[r, 1].fill_between(
            range(len(h["best_tc_C"])),
            cfg["target_tc_celsius"] - cfg["tc_tolerance"],
            cfg["target_tc_celsius"] + cfg["tc_tolerance"],
            alpha=0.2, color="green",
        )
        axes[r, 1].set_xlabel("Generation"); axes[r, 1].set_ylabel("Tc (°C)")
        axes[r, 1].set_title("Curie Temperature"); axes[r, 1].legend(); axes[r, 1].grid(alpha=0.3)

        axes[r, 2].plot(h["best_strength"], "purple", lw=2)
        axes[r, 2].axhline(cfg["min_strength_mpa"], color="k", ls="--", label="lower bound")
        axes[r, 2].set_xlabel("Generation"); axes[r, 2].set_ylabel("σy (MPa)")
        axes[r, 2].set_title("Yield Strength"); axes[r, 2].legend(); axes[r, 2].grid(alpha=0.3)

        ax2  = axes[r, 3]
        ax2b = ax2.twinx()
        ax2.plot(h["best_hc"], "b-", lw=2, label="Hc")
        ax2b.plot(h["best_br"], "g-", lw=2, label="Br")
        ax2.set_xlabel("Generation"); ax2.set_ylabel("Hc (A/m)", color="b")
        ax2b.set_ylabel("Br (T)", color="g"); ax2.set_title("Coercivity & Remanence")
        ax2.grid(alpha=0.3)

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=120, bbox_inches="tight")
    plt.show()


def plot_composition_heatmap(
    results: dict,
    top_n: int = 5,
    save_path: Path | str | None = None,
) -> None:
    """
    各情境 Top-N 配方熱圖。

    results 格式：{scenario_name: {"top_comps": np.ndarray (K, NUM_ELEMENTS), ...}}
    """
    n_cols = len(results)
    fig, axes = plt.subplots(1, n_cols, figsize=(7 * n_cols, 5))
    if n_cols == 1:
        axes = [axes]

    for c, (name, res) in enumerate(results.items()):
        top = res["top_comps"][:top_n] * 100
        sns.heatmap(
            top, annot=True, fmt=".1f", cmap="YlOrRd", ax=axes[c],
            xticklabels=ELEMENTS,
            yticklabels=[f"#{i+1}" for i in range(top_n)],
            cbar_kws={"label": "at%"},
        )
        axes[c].set_title(f"{name}\nTop-{top_n} compositions (at%)")

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=120, bbox_inches="tight")
    plt.show()
