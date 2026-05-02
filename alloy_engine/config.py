from pathlib import Path
import torch

# ── 路徑 ──────────────────────────────────────────────────────────────────────
PACKAGE_DIR   = Path(__file__).parent
CHECKPOINT_DIR = PACKAGE_DIR / "models" / "checkpoints"
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

# ── 運算裝置 ──────────────────────────────────────────────────────────────────
DEFAULT_DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

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
