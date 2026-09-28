#!/usr/bin/env bash
set -euo pipefail

ROOT="/root/work/GansuTechFinance_KGQA_RELEASE_RUNTIME/deliverables/paper_submission_system_20260522_114215"
cd "$ROOT"

source /root/work/GansuTechFinance_KGQA_RELEASE_RUNTIME/scripts/加载运行环境变量.sh
export GTF_ENABLE_V7_FALLBACK=0

if [[ -z "${DASHSCOPE_API_KEY:-}" ]]; then
  echo "ERROR: DASHSCOPE_API_KEY is empty. Export it before running this script."
  exit 1
fi
export DASHSCOPE_BASE_URL="${DASHSCOPE_BASE_URL:-https://dashscope.aliyuncs.com/compatible-mode/v1}"
export DASHSCOPE_MODEL="${DASHSCOPE_MODEL:-qwen-plus}"

mkdir -p experiments/baselines/results/stage300 experiments/baselines/logs

DATASET="experiments/baselines/datasets/gtf_kgqa_300_stratified_seed20260605.csv"
GOLD="$DATASET"

run_one_stage300() {
  local method="$1"
  local topk="$2"
  local out="experiments/baselines/results/stage300/${method}_stage300.jsonl"
  local metrics="experiments/baselines/results/stage300/${method}_stage300_metrics.json"
  local log="experiments/baselines/logs/${method}_stage300.log"

  echo "============================================================"
  echo "[START] ${method} top_k=${topk}"
  echo "output=${out}"
  echo "log=${log}"
  echo "============================================================"

  python tools/run_baseline_experiment.py \
    --method "${method}" \
    --dataset "${DATASET}" \
    --output "${out}" \
    --top-k "${topk}" \
    --resume \
    > "${log}" 2>&1

  echo "[EVAL] ${method}"
  python tools/baselines/evaluate_baseline_results.py \
    --gold "${GOLD}" \
    --pred "${out}" \
    --output "${metrics}"

  echo "[TOKEN] ${method}"
  python tools/baselines/summarize_token_usage.py "${out}"
  echo "[DONE] ${method}"
}

run_one_stage300 llm_only 20
run_one_stage300 naive_bm25_rag 20
run_one_stage300 langchain_rag 20
run_one_stage300 llamaindex_rag 20

echo "============================================================"
echo "[ALL TOKEN SUMMARY]"
echo "============================================================"
python tools/baselines/summarize_token_usage.py \
  experiments/baselines/results/stage300/llm_only_stage300.jsonl \
  experiments/baselines/results/stage300/naive_bm25_rag_stage300.jsonl \
  experiments/baselines/results/stage300/langchain_rag_stage300.jsonl \
  experiments/baselines/results/stage300/llamaindex_rag_stage300.jsonl

echo "[DONE] Stage-300 remaining baselines completed"
