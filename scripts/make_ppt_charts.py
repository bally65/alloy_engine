"""
為簡報產生圖表（中文字型 = WenQuanYi Zen Hei）。輸出到 docs/ppt_assets/。
這些圖表的數字皆引自本專案文件（README / DATA_SOURCING_ASSESSMENT / KNOWN_DEFECTS）。
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np

FONT = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
fm.fontManager.addfont(FONT)
plt.rcParams["font.family"] = fm.FontProperties(fname=FONT).get_name()
plt.rcParams["axes.unicode_minus"] = False

OUT = Path("docs/ppt_assets")
OUT.mkdir(parents=True, exist_ok=True)

NAVY = "#1f3a5f"
TEAL = "#2a9d8f"
ORANGE = "#e76f51"
GOLD = "#e9c46a"
GREY = "#8d99ae"


def _save(fig, name):
    fig.savefig(OUT / name, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", OUT / name)


def sim_to_real():
    """合成 vs 真實 NEMAD Tc 的 R² / MAE 對比。"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, 3.6))
    labels = ["合成代理\n(評於真實)", "真實 NEMAD\n訓練"]
    r2 = [-0.17, 0.88]
    colors = [ORANGE, TEAL]
    ax1.bar(labels, r2, color=colors)
    ax1.axhline(0, color="k", lw=0.8)
    ax1.set_title("測試 R²（越高越好）")
    ax1.set_ylim(-0.4, 1.0)
    for i, v in enumerate(r2):
        ax1.text(i, v + (0.04 if v > 0 else -0.08), f"{v:+.2f}",
                 ha="center", fontsize=12, fontweight="bold")
    mae = [274, 81]
    ax2.bar(labels, mae, color=colors)
    ax2.set_title("MAE（°C，越低越好）")
    for i, v in enumerate(mae):
        ax2.text(i, v + 6, f"{v}", ha="center", fontsize=12, fontweight="bold")
    fig.suptitle("Tc Sim-to-Real：真實資料把 R² 從 -0.17 救回 0.88", fontsize=13, fontweight="bold")
    _save(fig, "sim_to_real.png")


def bottleneck_chain():
    """瓶頸演進鏈。"""
    fig, ax = plt.subplots(figsize=(9.5, 2.4))
    steps = ["顯熱", "磁滯", "熱導率 κ", "元素空間", "真實資料"]
    x = np.arange(len(steps))
    for i, s in enumerate(steps):
        ax.add_patch(plt.Rectangle((i - 0.42, -0.35), 0.84, 0.7,
                     color=[NAVY, TEAL, ORANGE, GOLD, "#6a4c93"][i], alpha=0.9))
        ax.text(i, 0, s, ha="center", va="center", color="white",
                fontsize=12, fontweight="bold")
        if i < len(steps) - 1:
            ax.annotate("", xy=(i + 0.55, 0), xytext=(i + 0.42, 0),
                        arrowprops=dict(arrowstyle="->", lw=2, color="#333"))
    ax.set_xlim(-0.7, len(steps) - 0.3)
    ax.set_ylim(-0.8, 0.8)
    ax.axis("off")
    ax.set_title("瓶頸演進：逐一被識別並處理", fontsize=13, fontweight="bold")
    _save(fig, "bottleneck.png")


def architecture_gains():
    """架構優化增益。"""
    fig, ax = plt.subplots(figsize=(8, 3.6))
    cats = ["效率 η", "功率密度 P/V", "電壓 V"]
    base = [0.022, 0.73, 0.14]
    opt = [1.56, 4.1, 4.37]
    factor = [71, 5.6, 31]
    x = np.arange(len(cats))
    w = 0.35
    ax.bar(x - w / 2, [1] * 3, w, label="基準", color=GREY)
    ax.bar(x + w / 2, factor, w, label="架構優化後（×倍數）", color=TEAL)
    for i, f in enumerate(factor):
        ax.text(i + w / 2, f + 1.5, f"×{f:g}", ha="center", fontweight="bold", fontsize=11)
    ax.set_xticks(x)
    ax.set_xticklabels(cats)
    ax.set_ylabel("相對基準的倍數")
    ax.set_title("整機架構優化（低溫廢熱情境）", fontsize=13, fontweight="bold")
    ax.legend()
    _save(fig, "architecture.png")


def mt_curves():
    """二階 vs 一階 M(T)（D5）。"""
    fig, ax = plt.subplots(figsize=(8, 3.6))
    Tc = 300.0
    T = np.linspace(240, 360, 400)
    Ms = 1.0
    second = np.where(T < Tc, Ms * np.sqrt(np.clip(1 - T / Tc, 0, None)), 0)
    w = 6.0
    first = Ms / (1 + np.exp((T - Tc) / w))
    ax.plot(T, second, label="二階（平均場 √）", color=NAVY, lw=2.2)
    ax.plot(T, first, label="一階（logistic 銳變，D5）", color=ORANGE, lw=2.2)
    ax.axvline(Tc, ls="--", color=GREY, lw=1)
    ax.text(Tc + 1, 0.9, "Tc", color=GREY)
    ax.set_xlabel("溫度 T (K)")
    ax.set_ylabel("磁化 M / Ms")
    ax.set_title("D5：一階相變的銳變被平均場低估", fontsize=13, fontweight="bold")
    ax.legend()
    _save(fig, "mt_curves.png")


def rare_earth_penalty():
    """D9 稀土可製造性懲罰曲線。"""
    fig, ax = plt.subplots(figsize=(8, 3.6))
    re = np.linspace(0, 1, 100)
    oxid = 1 - 0.25 * np.clip(re, 0, 1)
    ax.plot(re * 100, oxid, color=NAVY, lw=2.4, label="氧化/處理懲罰（純稀土→0.75）")
    ax.scatter([7], [1 - 0.25 * 0.07], color=TEAL, zorder=5, s=80)
    ax.annotate("La-Fe-Si\n(~0.96，保留競爭力)", (7, 1 - 0.25 * 0.07),
                xytext=(22, 0.90), fontsize=10,
                arrowprops=dict(arrowstyle="->", color=TEAL))
    ax.scatter([100], [0.75], color=ORANGE, zorder=5, s=80)
    ax.annotate("純 Gd\n(0.75，可行但須處理)", (100, 0.75),
                xytext=(60, 0.80), fontsize=10,
                arrowprops=dict(arrowstyle="->", color=ORANGE))
    ax.set_xlabel("稀土含量 (Gd+La) %")
    ax.set_ylabel("可製造性係數")
    ax.set_ylim(0.6, 1.02)
    ax.set_title("D9：稀土漸進懲罰（down-rank 但不排除 MCE）", fontsize=13, fontweight="bold")
    ax.legend(loc="lower left")
    _save(fig, "rare_earth_penalty.png")


def defect_status():
    """缺陷處理狀態總覽。"""
    fig, ax = plt.subplots(figsize=(9, 4.2))
    defects = ["D7 CI", "D4 頻率封頂", "D5 一階相變", "D1 真實Tc",
               "D9 稀土可製造性", "D2 主代理併入", "D3 Br校準", "D6 微結構參數",
               "D8 P/Ge元素", "D12 原型對標"]
    status = [2, 2, 2, 2, 2, 1, 1, 1, 1, 1]  # 2=done,1=partial/roadmap
    colors = [TEAL if s == 2 else GOLD for s in status]
    y = np.arange(len(defects))[::-1]
    ax.barh(y, [1] * len(defects), color=colors)
    for i, (d, s) in enumerate(zip(defects, status)):
        ax.text(0.02, y[i], d, va="center", fontsize=11, fontweight="bold",
                color="white")
        ax.text(0.98, y[i], "已修 ●" if s == 2 else "路線圖 ○", va="center",
                ha="right", fontsize=10, color="white")
    ax.axis("off")
    ax.set_title("缺陷登錄：5 項已修，其餘為路線圖", fontsize=13, fontweight="bold")
    _save(fig, "defect_status.png")


if __name__ == "__main__":
    sim_to_real()
    bottleneck_chain()
    architecture_gains()
    mt_curves()
    rare_earth_penalty()
    defect_status()
    print("done")
