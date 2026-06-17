"""真正的 2D 有限元 (FEM) 磁靜學求解（取代解析磁路估算）。

磁標位 φ 公式（無自由電流）：H=-∇φ，B=μ0(μr_eff·H + M_pm)，∇·B=0
  → ∇·(μr_eff ∇φ) = ∇·M_pm    （弱式：∫μr_eff ∇φ·∇v = ∫ M_pm·∇v）
以 scikit-fem 組裝剛度、線性求解，取氣隙平均 |B|，並算 2D 漏磁/邊緣因子
（FEM 氣隙場 / 一維無漏理想）。輸出場圖 docs/fem_field.png + docs/fem_magnetics.json。

幾何（mm，平面）：鐵框迴路 + 左腿嵌永磁(+y) + 右腿氣隙（工作板）。
用法：python scripts/fem_magnetics.py --br 0.96 --gap 4
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from skfem import MeshTri, Basis, ElementTriP1, BilinearForm, LinearForm, asm, condense, solve
from skfem.helpers import dot, grad

MU_0 = 4.0e-7 * math.pi
MU_IRON = 3000.0

# 幾何 (m)
OUT = dict(x0=4e-3, x1=66e-3, y0=6e-3, y1=44e-3)
HOLE = dict(x0=16e-3, x1=54e-3, y0=16e-3, y1=34e-3)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--br", type=float, default=0.96, help="磁體剩磁(溫度後) T")
    ap.add_argument("--gap", type=float, default=4.0, help="氣隙 mm")
    ap.add_argument("--mu-rec", type=float, default=1.05)
    ap.add_argument("--nx", type=int, default=141)
    ap.add_argument("--ny", type=int, default=113)
    args = ap.parse_args()

    gap_m = args.gap * 1e-3
    gy0, gy1 = 25e-3 - gap_m / 2, 25e-3 + gap_m / 2          # 氣隙在右腿中段
    GAP = dict(x0=54e-3, x1=66e-3, y0=gy0, y1=gy1)
    PM = dict(x0=4e-3, x1=16e-3, y0=19e-3, y1=31e-3)         # 左腿永磁
    M0 = args.br / MU_0                                       # 等效磁化 A/m (+y)

    xs = np.linspace(0, 70e-3, args.nx)
    ys = np.linspace(0, 50e-3, args.ny)
    m = MeshTri.init_tensor(xs, ys)
    basis = Basis(m, ElementTriP1())

    def inrect(X, Y, r):
        return (X >= r["x0"]) & (X <= r["x1"]) & (Y >= r["y0"]) & (Y <= r["y1"])

    def is_frame(X, Y):
        return inrect(X, Y, OUT) & ~inrect(X, Y, HOLE)

    def is_pm(X, Y):
        return inrect(X, Y, PM)

    def is_gap(X, Y):
        return inrect(X, Y, GAP)

    def is_iron(X, Y):
        return is_frame(X, Y) & ~is_pm(X, Y) & ~is_gap(X, Y)

    def mur(x):
        X, Y = x[0], x[1]
        return np.where(is_iron(X, Y), MU_IRON, args.mu_rec)

    def Mfield(x):
        X, Y = x[0], x[1]
        My = np.where(is_pm(X, Y), M0, 0.0)
        return np.stack([np.zeros_like(My), My])

    @BilinearForm
    def a(u, v, w):
        return mur(w.x) * dot(grad(u), grad(v))

    @LinearForm
    def Lf(v, w):
        return dot(Mfield(w.x), grad(v))

    A = asm(a, basis)
    b = asm(Lf, basis)
    node = int(np.argmin(m.p[0] ** 2 + m.p[1] ** 2))         # 釘一角點 φ=0 去除零空間
    phi = solve(*condense(A, b, D=np.array([node])))

    # 後處理：∇φ 於積分點 → |B|
    gphi = basis.interpolate(phi).grad                       # (2, nelems, nqp)
    gc = basis.global_coordinates().value                    # (2, nelems, nqp)
    Xq, Yq = gc[0], gc[1]
    mur_q = np.where(is_iron(Xq, Yq), MU_IRON, args.mu_rec)
    Bmag = MU_0 * mur_q * np.sqrt(gphi[0] ** 2 + gphi[1] ** 2)

    gapmask = is_gap(Xq, Yq)
    B_gap_fem = float(np.average(np.sqrt(gphi[0] ** 2 + gphi[1] ** 2)[gapmask]) * MU_0)  # 氣隙 μr=1

    # 一維無漏理想（磁體+氣隙串聯, A_m=A_gap）：B = Br·L_pm/(L_pm+μrec·gap)
    L_pm = PM["y1"] - PM["y0"]
    B_ideal = args.br * L_pm / (L_pm + args.mu_rec * gap_m)
    leak = B_gap_fem / B_ideal if B_ideal else float("nan")

    # 場圖（每元素平均 |B|）
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.tri as mtri
    Belem = Bmag.mean(axis=1)
    tri = mtri.Triangulation(m.p[0] * 1e3, m.p[1] * 1e3, m.t.T)
    fig, ax = plt.subplots(figsize=(8.2, 6))
    tpc = ax.tripcolor(tri, facecolors=np.clip(Belem, 0, np.percentile(Belem, 99)),
                       cmap="inferno", shading="flat")
    for r, c in [(OUT, "w"), (PM, "cyan"), (GAP, "lime")]:
        ax.add_patch(plt.Rectangle((r["x0"] * 1e3, r["y0"] * 1e3),
                                   (r["x1"] - r["x0"]) * 1e3, (r["y1"] - r["y0"]) * 1e3,
                                   fill=False, ec=c, lw=1.2, ls="--"))
    ax.set_aspect("equal"); ax.set_xlabel("x (mm)"); ax.set_ylabel("y (mm)")
    ax.set_title(f"2D FEM magnetostatics — |B| map\n"
                 f"B_gap(FEM)={B_gap_fem:.3f} T  ·  ideal(1D,no-leak)={B_ideal:.3f} T  ·  leakage×{leak:.2f}")
    plt.colorbar(tpc, label="|B| (T)")
    plt.tight_layout(); plt.savefig("docs/fem_field.png", dpi=150, bbox_inches="tight")

    res = dict(solver="scikit-fem P1 magnetostatic scalar-potential",
               n_nodes=int(m.p.shape[1]), n_elements=int(m.t.shape[1]),
               Br_T=args.br, gap_mm=args.gap, mu_iron=MU_IRON,
               B_gap_FEM_T=round(B_gap_fem, 4), B_ideal_1D_T=round(B_ideal, 4),
               leakage_fringe_factor=round(leak, 3))
    Path("docs/fem_magnetics.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))

    print(f"FEM solved: {res['n_nodes']} nodes, {res['n_elements']} elements")
    print(f"  B_gap (FEM)        = {B_gap_fem:.3f} T")
    print(f"  B_ideal (1D no-leak)= {B_ideal:.3f} T")
    print(f"  leakage/fringe factor = {leak:.2f}  (FEM/ideal)")
    print(f"  → 設計應對解析 B 乘此因子做漏磁derating。圖 docs/fem_field.png")


if __name__ == "__main__":
    main()
