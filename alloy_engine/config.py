from pathlib import Path
import os
import torch

# ── 路徑 ──────────────────────────────────────────────────────────────────────
PACKAGE_DIR   = Path(__file__).parent
CHECKPOINT_DIR = PACKAGE_DIR / "models" / "checkpoints"
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

# ── 運算裝置 ──────────────────────────────────────────────────────────────────
# 自動偵測：CUDA → MPS（Apple Silicon, 如 M1–M5）→ CPU。
# 以環境變數 ALLOY_DEVICE 強制覆寫（如 MPS 某些算子不支援時 ALLOY_DEVICE=cpu）。
def _auto_device() -> torch.device:
    forced = os.environ.get("ALLOY_DEVICE")
    if forced:
        return torch.device(forced)
    if torch.cuda.is_available():
        return torch.device("cuda")
    mps = getattr(torch.backends, "mps", None)
    if mps is not None and mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


DEFAULT_DEVICE = _auto_device()

# ── 隨機種子 ──────────────────────────────────────────────────────────────────
DEFAULT_SEED = 42

# ── 訓練超參數預設值 ──────────────────────────────────────────────────────────
DEFAULT_N_SAMPLES  = 8_000
DEFAULT_EPOCHS     = 300
DEFAULT_BATCH_SIZE = 256
DEFAULT_HIDDEN     = 128
DEFAULT_LR         = 1.5e-3

# ── GA 超參數預設值 ───────────────────────────────────────────────────────────
DEFAULT_POPULATION_SIZE = 200_000
DEFAULT_N_GENERATIONS   = 150
