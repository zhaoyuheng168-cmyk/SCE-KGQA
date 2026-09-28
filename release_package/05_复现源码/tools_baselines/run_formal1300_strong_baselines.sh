#!/usr/bin/env bash
set -euo pipefail

ROOT="/root/work/GansuTechFinance_KGQA_RELEASE_RUNTIME/deliverables/paper_submission_system_20260522_114215"
cd "$ROOT"

LOCK_FILE="experiments/baselines/logs/formal1300_strong.lock"
mkdir -p "$(dirname "$LOCK_FILE")"
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "ERROR: another formal1300 strong-baseline run is already active."
  echo "Check it with: ps -ef | grep -E 'run_formal1300_strong|run_baseline_experiment' | grep -v grep"
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

RUN_ID="${RUN_ID:-$(date +%Y%m%d_%H%M%S)}"
RESULT_DIR="experiments/baselines/results/strong_formal1300_${RUN_ID}"
mkdir -p "${RESULT_DIR}" experiments/baselines/logs

DATASET="experiments/baselines/datasets/gtf_kgqa_1300_formal_expanded_gold.csv"
MERGED_CORPUS="experiments/baselines/corpus/merged_rag_corpus.jsonl"

run_one() {
  local method="$1"
  local topk="$2"
  local corpus="${3:-}"
  local out="${RESULT_DIR}/${method}_formal1300.jsonl"
  local metrics="${RESULT_DIR}/${method}_formal1300_metrics.json"
  local csv="${RESULT_DIR}/${method}_formal1300.csv"
  local log="experiments/baselines/logs/${method}_formal1300_${RUN_ID}.log"

  echo "============================================================"
  echo "[START] ${method} top_k=${topk}"
  echo "dataset=${DATASET}"
  echo "output=${out}"
  echo "log=${log}"
  echo "============================================================"

  if [[ -n "${corpus}" ]]; then
    python tools/run_baseline_experiment.py --method "${method}" --dataset "${DATASET}" --corpus "${corpus}" --output "${out}" --top-k "${topk}" --resume > "${log}" 2>&1
  else
    python tools/run_baseline_experiment.py --method "${method}" --dataset "${DATASET}" --output "${out}" --top-k "${topk}" --resume > "${log}" 2>&1
  fi

  echo "[EVAL] ${method}"
  python tools/baselines/evaluate_baseline_results.py --gold "${DATASET}" --pred "${out}" --output "${metrics}"
  python tools/baselines/export_strong_baseline_csv.py "${out}" "${csv}"
  echo "[TOKEN] ${method}"
  python tools/baselines/summarize_token_usage.py "${out}"
  echo "[DONE] ${method}"
}

run_one hybrid_rag 30 "${MERGED_CORPUS}"
run_one text_kg_rag 30 "${MERGED_CORPUS}"
run_one kg_context_rag 80
run_one entity_linked_graphrag 80
run_one graph_only_kgqa 80

echo "============================================================"
echo "[STRONG TOKEN SUMMARY]"
echo "============================================================"
python tools/baselines/summarize_token_usage.py \
  "${RESULT_DIR}/hybrid_rag_formal1300.jsonl" \
  "${RESULT_DIR}/text_kg_rag_formal1300.jsonl" \
  "${RESULT_DIR}/kg_context_rag_formal1300.jsonl" \
  "${RESULT_DIR}/entity_linked_graphrag_formal1300.jsonl" \
  "${RESULT_DIR}/graph_only_kgqa_formal1300.jsonl"

echo "[DONE] Formal-1300 strong baselines completed"
echo "RESULT_DIR=${RESULT_DIR}"
