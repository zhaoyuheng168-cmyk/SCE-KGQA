#!/usr/bin/env bash
set -euo pipefail

ROOT="/root/work/GansuTechFinance_KGQA_RELEASE_RUNTIME/deliverables/paper_submission_system_20260522_114215"
cd "$ROOT"

: "${DASHSCOPE_API_KEY:?export DASHSCOPE_API_KEY first}"
: "${DASHSCOPE_BASE_URL:?export DASHSCOPE_BASE_URL first}"
export NLTK_DATA="${NLTK_DATA:-/root/nltk_data}"

source experiments/external_baselines/.venvs/graphrag/bin/activate

WS="experiments/external_baselines/microsoft_graphrag/workspace/smoke_natural"
[[ -d "$WS" ]] || { echo "Workspace does not exist: $WS"; exit 1; }
[[ -f "$WS/settings.yaml" ]] || { echo "settings.yaml does not exist: $WS/settings.yaml"; exit 1; }

STAMP="$(date +%Y%m%d_%H%M%S)"
LOG="experiments/external_baselines/logs/microsoft_graphrag_index_smoke_natural_${STAMP}.log"
mkdir -p "$(dirname "$LOG")"
METHOD="${GRAPHRAG_INDEX_METHOD:-standard}"
echo "Indexing natural Chinese corpus with method=${METHOD}"
# Do not use --verbose: GraphRAG debug logs may expose resolved API credentials.
graphrag index --root "$WS" --method "$METHOD" >"$LOG" 2>&1

for artifact in entities.parquet relationships.parquet communities.parquet text_units.parquet; do
  [[ -s "$WS/output/$artifact" ]] || {
    echo "ERROR: GraphRAG index is incomplete; missing $WS/output/$artifact"
    echo "Inspect log: $LOG"
    exit 1
  }
done
echo "$LOG"
