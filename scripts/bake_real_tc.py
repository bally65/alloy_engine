"""
D2：把真實 NEMAD Tc 模型「烘焙」進主代理，產出單一統一 checkpoint。

動機
----
HybridBundle 在「推論期」用兩個 checkpoint（合成 bundle + 真實 Tc baseline）
組合，需要 --hybrid-tc 旗標；忘了帶就會用回合成 Tc（R²=-0.17）的隱患。
本腳本把真實 Tc 頭直接換進 SurrogateBundle 並存成一個檔，下游用標準
SurrogateBundle.load 即得「真實 Tc + 合成 Hc/Br/σy」，消除這個隱患。

前提：兩者特徵管線一致（36 維 Oliynyk）、PropertyMLP 架構一致。

執行：
  python scripts/bake_real_tc.py \
      --bundle  alloy_engine/models/checkpoints/bundle.pt \
      --tc      alloy_engine/models/checkpoints/surrogate_nemad_baseline.pt \
      --output  alloy_engine/models/checkpoints/bundle_real_tc.pt
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).parent.parent))

from alloy_engine.config import CHECKPOINT_DIR, DEFAULT_DEVICE
from alloy_engine.data.elements import NUM_ELEMENTS
from alloy_engine.models.surrogate import SurrogateBundle, PropertyMLP

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    datefmt="%H:%M:%S")
logger = logging.getLogger("bake_real_tc")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="把真實 Tc 烘焙進主代理")
    p.add_argument("--bundle", type=Path, default=CHECKPOINT_DIR / "bundle.pt")
    p.add_argument("--tc",     type=Path, default=CHECKPOINT_DIR / "surrogate_nemad_baseline.pt")
    p.add_argument("--output", type=Path, default=CHECKPOINT_DIR / "bundle_real_tc.pt")
    p.add_argument("--device", type=str,  default=None)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    device = torch.device(args.device) if args.device else DEFAULT_DEVICE

    for path in (args.bundle, args.tc):
        if not path.exists():
            logger.error("找不到 checkpoint：%s", path)
            sys.exit(1)

    bundle = SurrogateBundle.load(args.bundle, device=device)
    payload = torch.load(args.tc, map_location=device, weights_only=False)
    tc_model = PropertyMLP(payload["in_dim"], payload["hidden"]).to(device)
    tc_model.load_state_dict(payload["model_state"])

    # 一致性檢查：特徵維度須相符
    bundle_in_dim = next(iter(bundle.mlp_tc.parameters())).shape[1]
    if bundle_in_dim != payload["in_dim"]:
        logger.error("特徵維度不符：bundle=%d vs tc=%d", bundle_in_dim, payload["in_dim"])
        sys.exit(1)

    # 烘焙前後對照（同一批隨機成分的 Tc 應改變、其餘三頭不變）
    comp = torch.distributions.Dirichlet(torch.ones(NUM_ELEMENTS)).sample((256,)).to(device)
    before = bundle.predict_properties(comp)

    bundle.replace_tc_head(tc_model, payload["scaler"])
    after = bundle.predict_properties(comp)

    tc_shift = (after["Tc"] - before["Tc"]).abs().mean().item()
    others_same = all(torch.allclose(before[k], after[k]) for k in ("Hc", "Br", "strength"))
    logger.info("Tc 平均變動 = %.1f K；Hc/Br/σy 不變 = %s", tc_shift, others_same)
    if not others_same:
        logger.error("非 Tc 頭被意外改動，中止")
        sys.exit(1)

    bundle.save(args.output)
    real_r2 = payload.get("test_r2_degC")
    logger.info("已存統一 bundle（真實 Tc%s + 合成 Hc/Br/σy）→ %s",
                f" R²={real_r2:.3f}" if real_r2 is not None else "", args.output)
    logger.info("下游用 run_search.py --checkpoint %s（免 --hybrid-tc）", args.output)


if __name__ == "__main__":
    main()
