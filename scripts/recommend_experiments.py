"""
主動學習：推薦「先合成哪些合金」最值得做（最大化驗證/改進模型）。
橋接計算 → 實體實驗（MEASUREMENT_PROTOCOL.md）。

用已校準的統一 bundle（真實 Tc + 真實 Br）對候選池算實驗價值（MC-Dropout 不確定度
+ 距訓練資料的新穎度），選出多樣化的一批。

執行：
  python scripts/recommend_experiments.py                 # 預設 k=5
  python scripts/recommend_experiments.py --target-tc 150 --k 5
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).parent.parent))
from alloy_engine.config import CHECKPOINT_DIR, DEFAULT_DEVICE
from alloy_engine.data.elements import ELEMENTS, NUM_ELEMENTS
from alloy_engine.data.synthetic import generate_sparse_composition, alpha_vector
from alloy_engine.features.engineering import composition_to_features_torch
from alloy_engine.models.surrogate import SurrogateBundle


def _load_bundle(device):
    for name in ("bundle_real_tc.pt", "bundle.pt"):
        p = CHECKPOINT_DIR / name
        if p.exists():
            print(f"載入 bundle：{name}")
            return SurrogateBundle.load(p, device=device)
    raise FileNotFoundError("找不到 checkpoint，請先 train_surrogate.py / bake_real_tc.py")


def _reference_feats(bundle, device):
    """以 MP Br 訓練集為新穎度參考（若存在）。"""
    p = Path("external/mp_fm_dataset.json")
    if not p.exists():
        return None
    import re
    comps = []
    for row in json.loads(p.read_text()):
        v = np.zeros(NUM_ELEMENTS, dtype=np.float32)
        ok = True
        for el, n in re.findall(r"([A-Z][a-z]?)(\d*)", row[0]):
            if not el:
                continue
            if el not in ELEMENTS:
                ok = False; break
            v[ELEMENTS.index(el)] += float(n) if n else 1.0
        if ok and v.sum() > 0:
            comps.append(v / v.sum())
    if not comps:
        return None
    ct = torch.from_numpy(np.array(comps)).to(device)
    return composition_to_features_torch(ct, bundle.element_matrix_t)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=5, help="推薦樣品數")
    ap.add_argument("--pool", type=int, default=3000, help="候選池大小")
    ap.add_argument("--target-tc", type=float, default=None, help="只考慮 Tc 接近此值(°C)的候選")
    ap.add_argument("--tc-tol", type=float, default=40.0, help="目標 Tc 容差(°C)")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    device = DEFAULT_DEVICE

    from alloy_engine.ga.active_learning import recommend_experiments

    bundle = _load_bundle(device)
    rng = np.random.default_rng(args.seed)
    comps_np, _ = generate_sparse_composition(args.pool, alpha_vector(), rng)
    comps = torch.from_numpy(comps_np).to(device)

    # 先濾掉化學上不可製造/非磁性的垃圾候選——否則純不確定度採樣會挑出模型外推
    # 最離譜（但無意義）的成分（如 La-Mo、P-Mn）。用 GA 化學懲罰當可製造性分數。
    from alloy_engine.ga.gpu_ga import GPUGeneticAlgorithm
    _ga = GPUGeneticAlgorithm(predict_fn=bundle.predict_properties, device=device,
                              population_size=1, target_tc_celsius=(args.target_tc or 150.0),
                              mode="thermomagnetic", enable_chemistry_constraints=True)
    manuf = _ga._chemistry_penalty(comps)
    comps = comps[manuf > 0.5]
    print(f"可製造性過濾（化學懲罰>0.5）→ 候選 {comps.shape[0]} 個")

    if args.target_tc is not None:
        tc_c = bundle.predict_properties(comps)["Tc"].cpu().numpy() - 273.15
        mask = np.abs(tc_c - args.target_tc) <= args.tc_tol
        comps = comps[torch.from_numpy(mask).to(device)]
        print(f"目標 Tc={args.target_tc}±{args.tc_tol}°C → 候選縮到 {comps.shape[0]} 個")
        if comps.shape[0] < args.k:
            print("符合目標 Tc 的候選太少，放寬 --tc-tol"); sys.exit(1)

    ref = _reference_feats(bundle, device)
    w_nov = 0.5 if ref is not None else 0.0
    recs = recommend_experiments(bundle, comps, k=args.k, reference_feats=ref, w_novelty=w_nov)

    print("═" * 78)
    print(f" 建議優先合成的 {args.k} 個樣品（最大化模型驗證/不確定度降低）"
          f"{'｜新穎度啟用' if ref is not None else '｜僅不確定度'}")
    print("═" * 78)
    print(f"{'#':<3}{'預測Tc°C':>9}{'±K':>6}{'預測Br':>8}{'±T':>7}{'價值':>7}  理由｜主要成分(at%)")
    print("-" * 78)
    for r in recs:
        c = comps[r["index"]].cpu().numpy()
        top = sorted([(ELEMENTS[j], c[j]*100) for j in range(NUM_ELEMENTS) if c[j] > 0.03],
                     key=lambda x: -x[1])
        comp_s = " ".join(f"{e}{v:.0f}" for e, v in top)
        print(f"{r['index']:<3}{r['Tc_C']:>9.0f}{r['Tc_std_K']:>6.0f}{r['Br_T']:>8.2f}"
              f"{r['Br_std_T']:>7.3f}{r['acquisition']:>7.2f}  {r['rationale']}｜{comp_s}")
    print("-" * 78)
    print(" 用法：依此清單鑄樣 → VSM/DSC 量 Tc/Br → 比對預測（協定見 MEASUREMENT_PROTOCOL.md）。")
    print(" 定位：找出模型『最沒把握 / 最在外推』的成分作壓力測試/驗證目標。")
    print(" ⚠ 注意：回顧基準顯示，在當前小資料規模下這不會比隨機更快提升平均精度")
    print("    （見 active_learning_benchmark.py / docs/ACTIVE_LEARNING.md §6）。")


if __name__ == "__main__":
    main()
