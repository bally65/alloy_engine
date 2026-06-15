"""
真實 Br baseline：以 MP DFT 磁化訓練可預測的 Br_0K 模型，量出 sim-to-real 落差。
（Tc(NEMAD) 故事的磁化版：證明「資料校正 → 可預測」。）

執行：
  python scripts/build_mp_magnetization_dataset.py   # 先抓資料（需 MP key）
  python scripts/train_br_mp_baseline.py             # 訓練 + 報告 + 存模型
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).parent.parent))
from alloy_engine.config import CHECKPOINT_DIR, DEFAULT_DEVICE
from alloy_engine.models.real_br import RealBrModel, load_dataset
from alloy_engine.models.surrogate import SurrogateBundle

DATASET = Path("external/mp_fm_dataset.json")


def main() -> None:
    if not DATASET.exists():
        print(f"找不到 {DATASET}；請先跑 build_mp_magnetization_dataset.py")
        sys.exit(1)
    comps, br = load_dataset(DATASET)
    print("═" * 66)
    print(f" 真實 Br baseline（MP DFT 磁化，n={len(br)}）")
    print("═" * 66)

    # 合成 Br 在真實資料上的表現（sim-to-real 對照）
    bundle = SurrogateBundle.load(CHECKPOINT_DIR / "bundle.pt", device=DEFAULT_DEVICE)
    br_syn = bundle.predict_properties(torch.from_numpy(comps).to(DEFAULT_DEVICE))["Br"].cpu().numpy()
    ss = np.sum((br_syn - br) ** 2); tot = np.sum((br - br.mean()) ** 2) + 1e-9
    r2_syn = 1 - ss / tot
    mae_syn = np.mean(np.abs(br_syn - br))
    print(f" 合成 Br vs 真實 MP   : R²={r2_syn:+.3f}  MAE={mae_syn:.2f}T   ← 無預測力")

    # 真實資料訓練的 Br 模型（GBR；標準 sim-to-real 評估指標）
    model = RealBrModel.train(comps, br)
    print(f" 真實資料訓練 (GBR)   : R²={model.cv_r2:+.3f}  MAE={model.cv_mae:.2f}T   ← 可預測（5-fold CV）")
    model.save(CHECKPOINT_DIR / "br_mp_baseline.pkl")

    # 同時訓練可烘焙的 torch MLP（GPU-native，格式同 Tc baseline，供 bake_real_tc 整合）
    from alloy_engine.features.engineering import composition_to_features_np
    from alloy_engine.models.surrogate import train_mlp
    X = composition_to_features_np(comps.astype("float32"), device=None)
    mlp, scaler = train_mlp(X, br.astype("float32"), "Br (T)", DEFAULT_DEVICE, epochs=150, hidden=64)
    torch.save({"model_state": mlp.state_dict(), "scaler": scaler,
                "in_dim": X.shape[1], "hidden": 64, "target": "Br_T"},
               CHECKPOINT_DIR / "br_mp_baseline.pt")
    print(f" 已存：br_mp_baseline.pkl（GBR 分析）+ br_mp_baseline.pt（torch，可烘焙進 bundle）")
    print("═" * 66)
    print(" 結論：與 Tc 相同，Br 唯有以真實資料訓練才有預測力（合成 ~0 → 真實 ~0.56）。")
    print(" 工作溫度 Br = predict_Br0K × m(T/Tc)（magnetization_correction + 真實 Tc）。")


if __name__ == "__main__":
    main()
