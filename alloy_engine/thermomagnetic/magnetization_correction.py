"""
磁化的溫度修正（D3）：把 0K 飽和磁化換算到工作溫度，反之亦然。

動機
----
Materials Project 的 DFT 磁化是 **0K 飽和值**；本引擎的合成 Br 是 **工作/室溫**
值。直接相比會把兩個不同溫度的量混為一談——這正是 `mp_magnetization_eval`
量到 bias = -0.50T 的主因之一。要誠實對標，必須先把兩者拉到同一溫度。

正確方向是把 MP 的 0K 值「降」到工作溫度（而非把合成 Br 往上推），否則會把
delta_M 推高到不對的方向（見 docs/DATA_SOURCING_ASSESSMENT.md 的警語）。

物理
----
自發磁化的約化曲線 m(T) = M(T)/M(0)：
- 平均場（Weiss/Brillouin，預設、無自由擬合參數）：
  m = B_J( (3J/(J+1)) · (Tc/T) · m ) 的自洽解；T ≥ Tc 時 m = 0。
- Kuz'min 閉式（選用，3d 鐵磁體經驗式）：
  m(t) = [1 - s·t^(3/2) - (1-s)·t^p]^(1/3),  t = T/Tc。

兩者皆滿足 m(0)=1、m(Tc)=0、在 [0,Tc] 單調遞減。
"""
from __future__ import annotations

import numpy as np

_EPS = 1e-9


def _brillouin(J: float, x: np.ndarray) -> np.ndarray:
    """Brillouin 函數 B_J(x)，數值穩定處理 x→0（→0）。"""
    x = np.asarray(x, dtype=float)
    a = (2.0 * J + 1.0) / (2.0 * J)
    b = 1.0 / (2.0 * J)
    out = np.empty_like(x)
    small = np.abs(x) < 1e-6
    # 小 x 泰勒：B_J(x) ≈ (J+1)/(3J) · x
    out[small] = (J + 1.0) / (3.0 * J) * x[small]
    xl = x[~small]
    out[~small] = a / np.tanh(a * xl) - b / np.tanh(b * xl)
    return out


def reduced_magnetization_meanfield(
    T_K, Tc_K: float, J: float = 0.5, n_iter: int = 200
) -> np.ndarray:
    """
    平均場約化磁化 m(T)/m(0) ∈ [0,1]，以自洽迭代求解。

    參數
        T_K : 溫度（K），scalar 或 array。
        Tc_K: 居禮溫度（K）。
        J   : 總角動量量子數（預設 0.5；J→∞ 趨近 Langevin）。
    """
    T = np.atleast_1d(np.asarray(T_K, dtype=float))
    m = np.where(T >= Tc_K, 0.0, 1.0)  # 初值；T≥Tc 直接 0
    active = T < Tc_K
    if np.any(active):
        Ta = T[active]
        coeff = (3.0 * J / (J + 1.0)) * (Tc_K / np.maximum(Ta, _EPS))
        ma = np.full(Ta.shape, 0.99)
        for _ in range(n_iter):
            ma_new = _brillouin(J, coeff * ma)
            ma_new = np.clip(ma_new, 0.0, 1.0)
            if np.max(np.abs(ma_new - ma)) < 1e-8:
                ma = ma_new
                break
            ma = ma_new
        m = m.astype(float)
        m[active] = ma
    return m if m.size > 1 else float(m[0])


def kuzmin_reduced_magnetization(
    T_K, Tc_K: float, s: float = 0.35, p: float = 2.5
) -> np.ndarray:
    """Kuz'min 閉式約化磁化（3d 鐵磁體經驗式）。"""
    T = np.atleast_1d(np.asarray(T_K, dtype=float))
    t = np.clip(T / Tc_K, 0.0, 1.0)
    inner = 1.0 - s * t ** 1.5 - (1.0 - s) * t ** p
    inner = np.clip(inner, 0.0, 1.0)
    m = inner ** (1.0 / 3.0)
    m = np.where(T >= Tc_K, 0.0, m)
    return m if m.size > 1 else float(m[0])


def saturation_to_working(
    Br_0K, T_work_K: float, Tc_K: float, J: float = 0.5
) -> float:
    """0K 飽和磁化 → 工作溫度磁化：Br(T) = Br(0) · m(T/Tc)。"""
    m = reduced_magnetization_meanfield(T_work_K, Tc_K, J)
    return float(np.asarray(Br_0K) * m)


def working_to_saturation(
    Br_work, T_work_K: float, Tc_K: float, J: float = 0.5
) -> float:
    """工作溫度磁化 → 0K 飽和磁化（上述之逆）。Tc 以下才有意義。"""
    m = reduced_magnetization_meanfield(T_work_K, Tc_K, J)
    return float(np.asarray(Br_work) / max(float(np.asarray(m)), _EPS))
