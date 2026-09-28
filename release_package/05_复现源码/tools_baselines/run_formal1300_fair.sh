#!/usr/bin/env bash
set -euo pipefail

ROOT="/root/work/GansuTechFinance_KGQA_RELEASE_RUNTIME/deliverables/paper_submission_system_20260522_114215"
cd "$ROOT"

LOCK_FILE="experiments/baselines/logs/formal1300_fair.lock"
mkdir -p "$(dirname "$LOCK_FILE")"
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "ERROR: another formal1300 fair baseline run is already active."
  echo "Check it with: ps -ef | grep -E 'run_formal1300_fair|run_baseline_experiment' | grep -v grep"
  exit 1
fi

source /root/work/GansuTechFinance_KGQA_RELEASE_RUNTIME/scripts/加载运行环境变量.sh
export GTF_ENABLE_V7_FALLBACK=0

if [[ -z "${DASHSCOPE_API_KEY:-}" ]]; then
  echo "ERROR: DASHSCOPE_API_KEY is empty. Export it before running this script."
  exit 1
fi
export DASHSCOPE_BASE_URL="${DASHSCOPE_BASE_URL:-https://dashscope.aliyuncs.com/compatible-mode/v1}"
export DASHSCOPE_MODEL="${DASHSCOPE_MODEL:-qwen-plus}"

mkdir -p experiments/baselines/results/formal1300 experiments/baselines/logs

DATASET="experiments/baselines/datasets/gtf_kgqa_1300_formal_expanded_gold.csv"
MERGED_CORPUS="experiments/baselines/corpus/merged_rag_corpus.jsonl"

run_one() {
  local method="$1"
  local topk="$2"
  local corpus="${3:-}"
  local out="experiments/baselines/results/formal1300/${method}_formal1300.jsonl"
  local metrics="experiments/baselines/results/formal1300/${method}_formal1300_metrics.json"
  local log="experiments/baselines/logs/${method}_formal1300.log"

  echo "============================================================"
  echo "[START] ${method} top_k=${topk}"
  echo "dataset=${DATASET}"
  echo "output=${out}"
  echo "log=${log}"
  echo "============================================================"

  if [[ -n "${corpus}" ]]; then
    python tools/run_baseline_experiment.py \
      --method "${method}" \
      --dataset "${DATASET}" \
      --corpus "${corpus}" \
      --output "${out}" \
      --top-k "${topk}" \
      --resume \
      > "${log}" 2>&1
  else
    python tools/run_baseline_experiment.py \
      --method "${method}" \
      --dataset "${DATASET}" \
      --output "${out}" \
      --top-k "${topk}" \
      --resume \
      > "${log}" 2>&1
  fi

  echo "[EVAL] ${method}"
  python tools/baselines/evaluate_baseline_results.py \
    --gold "${DATASET}" \
    --pred "${out}" \
    --output "${metrics}"

  echo "[TOKEN] ${method}"
  python tools/baselines/summarize_token_usage.py "${out}"
  echo "[DONE] ${method}"
}

# Lower bound.
run_one llm_only 20

# Classic RAG over merged KG triples + evidence.
run_one naive_bm25_rag 20
run_one naive_vector_rag 20

# External framework RAG over the same merged KG triples + evidence.
run_one langchain_rag 20 "${MERGED_CORPUS}"
run_one llamaindex_rag 20 "${MERGED_CORPUS}"

# Graph/KG baselines.
run_one external_graphrag_style 80
run_one rule_based_kgqa 80

# Proposed full system.
run_one sce_kgqa_full 50

echo "============================================================"
echo "[ALL TOKEN SUMMARY]"
echo "============================================================"
python tools/baselines/summarize_token_usage.py \
  experiments/baselines/results/formal1300/llm_only_formal1300.jsonl \
  experiments/baselines/results/formal1300/naive_bm25_rag_formal1300.jsonl \
  experiments/baselines/results/formal1300/naive_vector_rag_formal1300.jsonl \
  experiments/baselines/results/formal1300/langchain_rag_formal1300.jsonl \
  experiments/baselines/results/formal1300/llamaindex_rag_formal1300.jsonl \
  experiments/baselines/results/formal1300/external_graphrag_style_formal1300.jsonl \
  experiments/baselines/results/formal1300/rule_based_kgqa_formal1300.jsonl \
  experiments/baselines/results/formal1300/sce_kgqa_full_formal1300.jsonl

echo "[DONE] Formal-1300 fair baselines completed"
