#!/usr/bin/env bash
set -euo pipefail

ROOT="/root/work/GansuTechFinance_KGQA_RELEASE_RUNTIME/deliverables/paper_submission_system_20260522_114215"
cd "$ROOT"

LOCK_FILE="experiments/baselines/logs/two_priority_text_formal1300.lock"
mkdir -p "$(dirname "$LOCK_FILE")"
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "ERROR: another priority text-baseline run is already active."
  exit 1
fi

source /root/work/GansuTechFinance_KGQA_RELEASE_RUNTIME/scripts/加载运行环境变量.sh
: "${DASHSCOPE_API_KEY:?export DASHSCOPE_API_KEY first}"
export DASHSCOPE_BASE_URL="${DASHSCOPE_BASE_URL:-https://dashscope.aliyuncs.com/compatible-mode/v1}"
export DASHSCOPE_MODEL="${DASHSCOPE_MODEL:-qwen-plus}"

DATASET="experiments/baselines/datasets/gtf_kgqa_1300_formal_expanded_gold.csv"
CORPUS="experiments/baselines/corpus/merged_rag_corpus.jsonl"
RESULT_DIR="experiments/baselines/results/priority_text_formal1300"
mkdir -p "$RESULT_DIR" experiments/baselines/logs

run_one() {
  local method="$1"
  local output="$RESULT_DIR/${method}_formal1300.jsonl"
  local log="experiments/baselines/logs/${method}_priority_formal1300.log"

  python tools/run_baseline_experiment.py \
    --method "$method" --dataset "$DATASET" --corpus "$CORPUS" \
    --output "$output" --top-k 30 --resume >"$log" 2>&1
  python tools/baselines/evaluate_baseline_results.py \
    --gold "$DATASET" --pred "$output" \
    --output "$RESULT_DIR/${method}_formal1300_metrics.json"
  python tools/baselines/summarize_token_usage.py "$output"
}

run_one hybrid_rag
run_one text_kg_rag
echo "RESULT_DIR=$RESULT_DIR"
