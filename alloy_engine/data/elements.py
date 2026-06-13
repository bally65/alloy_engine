"""
元素物理性質資料庫
值取自 NIST / Materials Project 公開資料
使用屬性：Z, M, r, EN, Vel, IE, mu, rho, E（共 9 個）

已移除的屬性：
  Tc（純元素居禮溫度）：對合金 Tc 是 circular feature（data leakage）。
  Fe/Ni/Co 是唯一 Tc>0 的元素，max/min_Tc 幾乎直接告訴模型「答案」。

特徵維度：9 props × 4 stats (wmean, wvar, max, min) = 36 維
注意：mu 的 max/min 在全 Dirichlet 訓練下也有退化問題，
      但稀疏 Dirichlet 採樣會讓 min_mu 有真實方差，故保留 mu。
"""
import numpy as np

ELEMENT_PROPERTIES: dict[str, dict[str, float]] = {
    # Symbol: {Z, M (g/mol), r (pm), EN (Pauling), Vel, IE1 (eV),
    #          mu (μB), rho (g/cm³), E (GPa)}
    "Fe": {"Z": 26, "M": 55.85, "r": 126, "EN": 1.83, "Vel": 8,  "IE": 7.90, "mu": 2.22, "rho": 7.87,  "E": 211},
    "Ni": {"Z": 28, "M": 58.69, "r": 124, "EN": 1.91, "Vel": 10, "IE": 7.64, "mu": 0.61, "rho": 8.91,  "E": 200},
    "Co": {"Z": 27, "M": 58.93, "r": 125, "EN": 1.88, "Vel": 9,  "IE": 7.88, "mu": 1.72, "rho": 8.90,  "E": 209},
    "Cr": {"Z": 24, "M": 52.00, "r": 128, "EN": 1.66, "Vel": 6,  "IE": 6.77, "mu": 0.0,  "rho": 7.19,  "E": 279},
    "Mn": {"Z": 25, "M": 54.94, "r": 127, "EN": 1.55, "Vel": 7,  "IE": 7.43, "mu": 0.0,  "rho": 7.21,  "E": 198},
    "Cu": {"Z": 29, "M": 63.55, "r": 128, "EN": 1.90, "Vel": 11, "IE": 7.73, "mu": 0.0,  "rho": 8.96,  "E": 130},
    "Mo": {"Z": 42, "M": 95.95, "r": 139, "EN": 2.16, "Vel": 6,  "IE": 7.09, "mu": 0.0,  "rho": 10.28, "E": 329},
    "Si": {"Z": 14, "M": 28.09, "r": 111, "EN": 1.90, "Vel": 4,  "IE": 8.15, "mu": 0.0,  "rho": 2.33,  "E": 130},
    "Al": {"Z": 13, "M": 26.98, "r": 143, "EN": 1.61, "Vel": 3,  "IE": 5.99, "mu": 0.0,  "rho": 2.70,  "E": 70},
    "V":  {"Z": 23, "M": 50.94, "r": 134, "EN": 1.63, "Vel": 5,  "IE": 6.75, "mu": 0.0,  "rho": 6.11,  "E": 128},
    # ── 稀土元素（室溫磁熱）：解鎖高 mu / 高 ΔS_M 的近室溫 MCE 材料 ──────────────
    # Gd: 室溫鐵磁基準 (Tc≈293K, mu=7.55μB)；La: 非磁性，啟用 La-Fe-Si 1:13 相
    "Gd": {"Z": 64, "M": 157.25, "r": 180, "EN": 1.20, "Vel": 3, "IE": 6.15, "mu": 7.55, "rho": 7.90, "E": 55},
    "La": {"Z": 57, "M": 138.91, "r": 187, "EN": 1.10, "Vel": 3, "IE": 5.58, "mu": 0.0,  "rho": 6.16, "E": 37},
}

ELEMENTS:     list[str] = list(ELEMENT_PROPERTIES.keys())
NUM_ELEMENTS: int       = len(ELEMENTS)
PROP_NAMES:   list[str] = ["Z", "M", "r", "EN", "Vel", "IE", "mu", "rho", "E"]  # 9 props; Tc removed
NUM_PROPS:    int       = len(PROP_NAMES)


def get_element_matrix() -> np.ndarray:
    """回傳屬性矩陣 (NUM_ELEMENTS × NUM_PROPS)，dtype=float32。"""
    return np.array(
        [[ELEMENT_PROPERTIES[e][p] for p in PROP_NAMES] for e in ELEMENTS],
        dtype=np.float32,
    )
