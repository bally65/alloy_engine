import sys
from pathlib import Path

# 確保 pytest 能找到 alloy_engine 套件
sys.path.insert(0, str(Path(__file__).parent))
