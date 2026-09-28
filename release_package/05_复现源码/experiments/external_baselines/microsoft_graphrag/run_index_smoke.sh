#!/usr/bin/env bash
set -euo pipefail
ROOT="/root/work/GansuTechFinance_KGQA_RELEASE_RUNTIME/deliverables/paper_submission_system_20260522_114215"
cd "$ROOT"
: "${DASHSCOPE_API_KEY:?export DASHSCOPE_API_KEY first}"
source experiments/external_baselines/.venvs/graphrag/bin/activate
WS="experiments/external_baselines/microsoft_graphrag/workspace/smoke"
STAMP="$(date +%Y%m%d_%H%M%S)"
LOG="experiments/external_baselines/logs/microsoft_graphrag_index_smoke_${STAMP}.log"
[[ -f "$WS/settings.yaml" ]] || { echo "Run graphrag init and configure settings.yaml in $WS first"; exit 1; }
graphrag index --root "$WS" --method fast --verbose >"$LOG" 2>&1
echo "$LOG"
