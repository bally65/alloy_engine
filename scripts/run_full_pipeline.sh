#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# 一鍵生產級管線（turnkey）：合成代理 → 真實 NEMAD Tc baseline → 烘焙統一 bundle
#   → 真實 Br 溫度修正對標 → 發電側原型對標。
#
# 自動選最快裝置：CUDA → MPS（Apple Silicon, M1–M5）→ CPU。
#   Mac M5 直接可跑；如遇 MPS 算子不支援，前面加 ALLOY_DEVICE=cpu 即回退。
# 產物：checkpoint 存 alloy_engine/models/checkpoints/（你本機保留）；
#       量化報告存 results/pipeline_report.md（可 commit，純文字可復現）。
#
# 用法：
#   bash scripts/run_full_pipeline.sh                 # 生產級（8000/300）
#   N_SAMPLES=4000 EPOCHS=80 bash scripts/run_full_pipeline.sh   # 快速版
#   ALLOY_DEVICE=cpu bash scripts/run_full_pipeline.sh           # 強制 CPU
# ─────────────────────────────────────────────────────────────────────────────
set -uo pipefail
cd "$(dirname "$0")/.."

mkdir -p results
REPORT=results/pipeline_report.md
N_SAMPLES=${N_SAMPLES:-8000}
EPOCHS=${EPOCHS:-300}
DEV=$(python -c "from alloy_engine.config import DEFAULT_DEVICE; print(DEFAULT_DEVICE)")
STARTED=$(date -u +"%Y-%m-%d %H:%M:%SZ")

log() { echo "[pipeline] $*"; }

{
  echo "# 生產級管線報告（pipeline_report）"
  echo
  echo "- 開始：\`$STARTED\`  · 裝置：\`$DEV\`  · n_samples=\`$N_SAMPLES\`  · epochs=\`$EPOCHS\`"
  echo "- 元素空間：14（Fe-Ni-Co-Cr-Mn-Cu-Mo-Si-Al-V-Gd-La-P-Ge）"
  echo
} > "$REPORT"

# 1. 合成代理（生產級）
log "1/5 訓練合成代理（$N_SAMPLES 樣本 / $EPOCHS epochs）…"
python scripts/train_surrogate.py --n-samples "$N_SAMPLES" --epochs "$EPOCHS" \
  2>&1 | tee results/_train_surrogate.log
{
  echo "## 1. 合成代理（4 property heads）"
  echo '```'
  grep -E "best R²|Br|Hc|σy|Tc" results/_train_surrogate.log | grep "R²" || true
  echo '```'
} >> "$REPORT"

# 2. 真實 NEMAD Tc baseline（含 P/Ge 解鎖的 +366 化合物）
log "2/5 真實 NEMAD Tc baseline…"
if python scripts/train_surrogate_nemad_baseline.py 2>&1 | tee results/_nemad_baseline.log; then
  {
    echo "## 2. 真實 NEMAD Tc baseline"
    echo '```'
    grep -E "rows|Overall test R²|R²|MAE" results/_nemad_baseline.log | tail -8 || true
    echo '```'
  } >> "$REPORT"
else
  echo "## 2. 真實 NEMAD Tc baseline — 略過（缺 external/NEMAD CSV）" >> "$REPORT"
fi

# 3. 烘焙真實 Tc 進統一 bundle（D2）
log "3/5 烘焙統一 bundle（真實 Tc + 合成 Hc/Br/σy）…"
if python scripts/bake_real_tc.py 2>&1 | tee results/_bake.log; then
  {
    echo "## 3. 烘焙統一 bundle（D2）"
    echo '```'
    grep -E "Tc 平均變動|統一 bundle|R²" results/_bake.log || true
    echo '```'
  } >> "$REPORT"
else
  echo "## 3. 烘焙 — 略過（缺前置 checkpoint）" >> "$REPORT"
fi

# 4. 真實 Br MP 溫度修正對標（D3；需 MP key）
log "4/5 真實 Br MP 溫度修正對標…"
if python scripts/mp_magnetization_eval.py 2>&1 | tee results/_mp_eval.log; then
  {
    echo "## 4. 真實 Br vs MP（溫度修正，D3）"
    echo '```'
    grep -E "對 MP|bias|MAE|材料" results/_mp_eval.log | tail -14 || true
    echo '```'
  } >> "$REPORT"
else
  echo "## 4. MP 對標 — 略過（缺 MP key / 無網路）" >> "$REPORT"
fi

# 5. 發電側原型對標（D12）
log "5/5 發電側原型對標…"
python scripts/evaluate_reference_devices.py 2>&1 | tee results/_devices.log
{
  echo "## 5. 發電側對標真實 TMG 原型（D12）"
  echo '```'
  grep -E "同頻對標|高估|原型|Nat" results/_devices.log | tail -10 || true
  echo '```'
  echo
  echo "_完成：$(date -u +"%Y-%m-%d %H:%M:%SZ")_"
} >> "$REPORT"

log "完成 → $REPORT"
