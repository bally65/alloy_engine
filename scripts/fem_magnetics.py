"""2D 有限元 (FEM) 磁靜學求解器（scikit-fem）— v2：非線性 B–H 鐵飽和 + 軸對稱選項。

磁標位 φ：H=-∇φ，B=μ0(μr·H + M_pm)，∇·B=0 → ∫ μr ∇φ·∇v (·r 若軸對稱) = ∫ M_pm·∇v。
- 線性：iron μr 常數。
- 非線性（--nonlinear）：iron μr=μr(|B|) 由飽和曲線，Picard 迭代（鬆弛）至 B_gap 收斂。
- 軸對稱（--axisymmetric）：弱式加 r 權重，模擬圓形/罐形（pot-core）磁路。

solve_field() 可被 fem_studies.py 重用（per-scenario / Halbach 幾何掃描）。
輸出 docs/fem_field.png + docs/fem_magnetics.json。
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
# 鐵 B–H 飽和模型：μr(B)=1+(μr0-1)/(1+(B/Bs)^p)
MUR0, BSAT, PEXP = 5000.0, 1.6, 7.0


def mur_iron_of_B(Bmag: np.ndarray) -> np.ndarray:
    return 1.0 + (MUR0 - 1.0) / (1.0 + (np.maximum(Bmag, 0.0) / BSAT) ** PEXP)


def solve_field(br: float, gap_mm: float = 4.0, magnet_len_mm: float = 12.0, *,
                nonlinear: bool = False, axisymmetric: bool = False,
                mu_rec: float = 1.05, nx: int = 141, ny: int = 113,
                max_iter: int = 40, tol: float = 2e-3, relax: float = 0.35) -> dict:
    gap_m = gap_mm * 1e-3
    Lm = magnet_len_mm * 1e-3
    OUT = dict(x0=4e-3, x1=66e-3, y0=6e-3, y1=44e-3)
    HOLE = dict(x0=16e-3, x1=54e-3, y0=16e-3, y1=34e-3)
    PM = dict(x0=4e-3, x1=16e-3, y0=25e-3 - Lm / 2, y1=25e-3 + Lm / 2)
    GAP = dict(x0=54e-3, x1=66e-3, y0=25e-3 - gap_m / 2, y1=25e-3 + gap_m / 2)
    M0 = br / MU_0

    m = MeshTri.init_tensor(np.linspace(0, 70e-3, nx), np.linspace(0, 50e-3, ny))
    basis = Basis(m, ElementTriP1())
    gc = basis.global_coordinates().value          # (2, nelems, nqp)
    Xq, Yq = gc[0], gc[1]
    rw = np.maximum(Xq, 1e-6) if axisymmetric else np.ones_like(Xq)

    def inr(r):
        return (Xq >= r["x0"]) & (Xq <= r["x1"]) & (Yq >= r["y0"]) & (Yq <= r["y1"])
    frame = inr(OUT) & ~inr(HOLE)
    pm = inr(PM); gap = inr(GAP)
    iron = frame & ~pm & ~gap
    My = np.where(pm, M0, 0.0)

    @BilinearForm
    def a(u, v, w):
        return w["mur"] * dot(grad(u), grad(v)) * w["rw"]

    @LinearForm
    def Lf(v, w):
        return (w["My"] * grad(v)[1]) * w["rw"]

    node = int(np.argmin(m.p[0] ** 2 + m.p[1] ** 2))
    Dnode = np.array([node])
    mur_q = np.where(iron, MUR0, mu_rec)
    b = asm(Lf, basis, My=My, rw=rw)

    history = []
    converged, used_iter = True, 1
    iters = max_iter if nonlinear else 1
    for it in range(iters):
        A = asm(a, basis, mur=mur_q, rw=rw)
        phi = solve(*condense(A, b, D=Dnode))
        gphi = basis.interpolate(phi).grad
        Hmag = np.sqrt(gphi[0] ** 2 + gphi[1] ** 2)
        B_gap = float(np.average((MU_0 * Hmag)[gap]))
        history.append(B_gap)
        if not nonlinear:
            used_iter = 1
            break
        B_iron = MU_0 * mur_q * Hmag                       # 以現 μr 估鐵中 B
        mur_new = np.where(iron, mur_iron_of_B(B_iron), mu_rec)
        mur_q = (1 - relax) * mur_q + relax * mur_new       # 鬆弛更新
        used_iter = it + 1
        if it > 0 and abs(history[-1] - history[-2]) < tol:
            break
    else:
        converged = not nonlinear

    L_pm = PM["y1"] - PM["y0"]
    B_ideal = br * L_pm / (L_pm + mu_rec * gap_m)
    leak = B_gap / B_ideal if B_ideal else float("nan")
    return dict(B_gap_T=round(B_gap, 4), B_ideal_T=round(B_ideal, 4), leakage=round(leak, 3),
                n_nodes=int(m.p.shape[1]), n_elements=int(m.t.shape[1]),
                nonlinear=nonlinear, axisymmetric=axisymmetric, n_iter=used_iter,
                converged=bool(converged), br=br, gap_mm=gap_mm, magnet_len_mm=magnet_len_mm,
                _mesh=m, _basis=basis, _phi=phi,
                _iron=iron, _pm=pm, _gap=gap, _mur=mur_q, _Hmag=Hmag,
                _rects=dict(OUT=OUT, PM=PM, GAP=GAP))


def make_field_plot(res: dict, path: str) -> None:
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.tri as mtri
    m = res["_mesh"]
    Belem = (MU_0 * res["_mur"] * res["_Hmag"]).mean(axis=1)
    tri = mtri.Triangulation(m.p[0] * 1e3, m.p[1] * 1e3, m.t.T)
    fig, ax = plt.subplots(figsize=(8.2, 6))
    tpc = ax.tripcolor(tri, facecolors=np.clip(Belem, 0, np.percentile(Belem, 99)),
                       cmap="inferno", shading="flat")
    for key, c in [("OUT", "w"), ("PM", "cyan"), ("GAP", "lime")]:
        r = res["_rects"][key]
        ax.add_patch(plt.Rectangle((r["x0"] * 1e3, r["y0"] * 1e3), (r["x1"] - r["x0"]) * 1e3,
                                   (r["y1"] - r["y0"]) * 1e3, fill=False, ec=c, lw=1.2, ls="--"))
    mode = ("非線性" if res["nonlinear"] else "線性") + ("·軸對稱" if res["axisymmetric"] else "·平面")
    ax.set_aspect("equal"); ax.set_xlabel("x / r (mm)"); ax.set_ylabel("y / z (mm)")
    ax.set_title(f"2D FEM |B| — {mode}  (iter={res['n_iter']})\n"
                 f"B_gap={res['B_gap_T']:.3f}T · ideal={res['B_ideal_T']:.3f}T · leak×{res['leakage']:.2f}")
    plt.colorbar(tpc, label="|B| (T)"); plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches="tight")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--br", type=float, default=0.96)
    ap.add_argument("--gap", type=float, default=4.0)
    ap.add_argument("--magnet-len", type=float, default=12.0)
    ap.add_argument("--nonlinear", action="store_true")
    ap.add_argument("--axisymmetric", action="store_true")
    args = ap.parse_args()
    res = solve_field(args.br, args.gap, args.magnet_len,
                      nonlinear=args.nonlinear, axisymmetric=args.axisymmetric)
    make_field_plot(res, "docs/fem_field.png")
    out = {k: v for k, v in res.items() if not k.startswith("_")}
    Path("docs/fem_magnetics.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"FEM: {out['n_nodes']} nodes / {out['n_elements']} elems · "
          f"{'nonlinear' if out['nonlinear'] else 'linear'}"
          f"{'/axisym' if out['axisymmetric'] else ''} · iters={out['n_iter']}")
    print(f"  B_gap={out['B_gap_T']}T  ideal={out['B_ideal_T']}T  leakage×{out['leakage']}")


if __name__ == "__main__":
    main()
