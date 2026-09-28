#!/usr/bin/env bash
set -euo pipefail

ROOT="/root/work/GansuTechFinance_KGQA_RELEASE_RUNTIME/deliverables/paper_submission_system_20260522_114215"
cd "$ROOT"
source /home/vipuser/miniconda3/etc/profile.d/conda.sh
conda activate base

LOCK_FILE="experiments/baselines/logs/formal1300_protocol_v2.lock"
mkdir -p "$(dirname "$LOCK_FILE")"
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "ERROR: another protocol-v2 formal run is active."
  exit 1
fi

source /root/work/GansuTechFinance_KGQA_RELEASE_RUNTIME/scripts/加载运行环境变量.sh
: "${DASHSCOPE_API_KEY:?export DASHSCOPE_API_KEY first}"
export DASHSCOPE_BASE_URL="${DASHSCOPE_BASE_URL:-https://dashscope.aliyuncs.com/compatible-mode/v1}"
export DASHSCOPE_MODEL="qwen3.5-plus"
export GTF_ENABLE_V7_FALLBACK=0

python tools/baselines/audit_comparison_protocol.py

PROTOCOL="comparison_protocol_v2_20260607"
DATASET="experiments/baselines/datasets/gtf_kgqa_1300_formal_expanded_gold.csv"
MERGED="experiments/baselines/corpus/merged_rag_corpus.jsonl"
RESULT_DIR="experiments/baselines/results/formal1300_protocol_v2"
LOG_DIR="experiments/baselines/logs/formal1300_protocol_v2"
mkdir -p "$RESULT_DIR" "$LOG_DIR"

run_one() {
  local method="$1"
  local top_k="$2"
  local corpus="${3:-}"
  local workers="${4:-4}"
  local output="$RESULT_DIR/${method}_formal1300.jsonl"
  local log="$LOG_DIR/${method}.log"
  echo "[START] ${method} protocol=${PROTOCOL} workers=${workers}"
  if [[ -n "$corpus" ]]; then
    python tools/run_baseline_experiment.py --method "$method" --dataset "$DATASET" \
      --corpus "$corpus" --output "$output" --top-k "$top_k" \
      --workers "$workers" --error-retries 2 --resume --retry-errors >"$log" 2>&1
  else
    python tools/run_baseline_experiment.py --method "$method" --dataset "$DATASET" \
      --output "$output" --top-k "$top_k" \
      --workers "$workers" --error-retries 2 --resume --retry-errors >"$log" 2>&1
  fi
  python tools/baselines/check_strong_baseline_outputs.py --expected-rows 1300 \
    --expected-protocol "$PROTOCOL" --expected-model "$DASHSCOPE_MODEL" "$output"
  python tools/baselines/evaluate_baseline_results.py --gold "$DATASET" --pred "$output" \
    --output "$RESULT_DIR/${method}_formal1300_metrics.json"
  python tools/baselines/summarize_token_usage.py "$output"
  echo "[DONE] ${method}"
}

# Knowledge-free lower bound.
run_one llm_only 0 "" 4

# Same frozen Text+KG corpus, different retrieval/framework mechanisms.
run_one naive_bm25_rag 20 "$MERGED" 4
run_one naive_vector_rag 20 "$MERGED" 4
run_one hybrid_rag 30 "$MERGED" 4
run_one text_kg_rag 30 "$MERGED" 4
run_one langchain_rag 20 "$MERGED" 4
run_one llamaindex_rag 20 "$MERGED" 2

# Independent graph and traditional rule controls.
run_one kg_context_rag 80 "" 4
run_one entity_linked_graphrag 80 "" 4
run_one rule_based_kgqa 80 "" 4
run_one graph_only_kgqa 80 "" 4

# Proposed system. LightRAG is run separately after its reusable full index succeeds.
run_one sce_kgqa_full 50 "" 1

python tools/baselines/evaluate_unified_results.py --gold "$DATASET" \
  --output-dir "experiments/baselines/reports/formal1300_protocol_v2" \
  "$RESULT_DIR"/*_formal1300.jsonl

echo "[DONE] ${PROTOCOL}; run official LightRAG separately and append it to unified evaluation."
