"""
訓練 MLP 代理模型並儲存 checkpoint。

使用範例：
  python scripts/train_surrogate.py
  python scripts/train_surrogate.py --n-samples 16000 --epochs 500 --seed 0
  python scripts/train_surrogate.py --output models/checkpoints/my_bundle.pt
"""
import argparse
import logging
import sys
import time
from pathlib import Path

import numpy as np
import torch

# 確保從專案根目錄執行時能 import alloy_engine
sys.path.insert(0, str(Path(__file__).parent.parent))

from alloy_engine.config import (
    CHECKPOINT_DIR,
    DEFAULT_BATCH_SIZE,
    DEFAULT_DEVICE,
    DEFAULT_EPOCHS,
    DEFAULT_HIDDEN,
    DEFAULT_LR,
    DEFAULT_N_SAMPLES,
    DEFAULT_SEED,
)
from alloy_engine.data.synthetic import generate_training_data
from alloy_engine.features.engineering import composition_to_features_np
from alloy_engine.models.surrogate import SurrogateBundle

logger = logging.getLogger("train_surrogate")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="訓練合金代理模型")
    p.add_argument("--n-samples",  type=int,   default=DEFAULT_N_SAMPLES,  help="訓練樣本數")
    p.add_argument("--epochs",     type=int,   default=DEFAULT_EPOCHS,     help="訓練週期數")
    p.add_argument("--batch-size", type=int,   default=DEFAULT_BATCH_SIZE, help="批次大小")
    p.add_argument("--hidden",     type=int,   default=DEFAULT_HIDDEN,     help="隱藏層寬度")
    p.add_argument("--lr",         type=float, default=DEFAULT_LR,         help="學習率")
    p.add_argument("--seed",       type=int,   default=DEFAULT_SEED,       help="隨機種子")
    p.add_argument("--device",     type=str,   default=None,
                   help="運算裝置（cuda / cpu），預設自動偵測")
    p.add_argument("--output",     type=Path,
                   default=CHECKPOINT_DIR / "bundle.pt",
                   help="checkpoint 輸出路徑")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    device = torch.device(args.device) if args.device else DEFAULT_DEVICE
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    logger.info("運算裝置: %s", device)
    if device.type == "cuda":
        logger.info("GPU: %s  VRAM: %.2f GB",
                    torch.cuda.get_device_name(0),
                    torch.cuda.get_device_properties(0).total_memory / 1e9)

    # 1. 生成訓練資料
    compositions, tc, hc, br, sigma_y = generate_training_data(
        n_samples=args.n_samples, seed=args.seed
    )

    # 2. 特徵工程
    logger.info("計算特徵向量…")
    X_features = composition_to_features_np(compositions, device=device)
    logger.info("特徵 shape: %s", X_features.shape)

    # 3. 訓練
    t0 = time.time()
    bundle = SurrogateBundle.from_trained(
        X_features=X_features,
        tc_data=tc, hc_data=hc, br_data=br, strength_data=sigma_y,
        device=device,
        epochs=args.epochs,
        batch_size=args.batch_size,
        hidden=args.hidden,
        lr=args.lr,
    )
    logger.info("訓練完成，耗時 %.1f 秒", time.time() - t0)

    # 4. 儲存
    args.output.parent.mkdir(parents=True, exist_ok=True)
    bundle.save(args.output)


if __name__ == "__main__":
    main()
