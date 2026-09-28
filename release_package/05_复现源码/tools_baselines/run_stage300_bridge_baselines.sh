#!/usr/bin/env bash
set -euo pipefail

ROOT="/root/work/GansuTechFinance_KGQA_RELEASE_RUNTIME/deliverables/paper_submission_system_20260522_114215"
cd "$ROOT"

LOCK_FILE="experiments/baselines/logs/stage300_bridge.lock"
mkdir -p "$(dirname "$LOCK_FILE")"
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "ERROR: another stage300 bridge-baseline run is already active."
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

mkdir -p experiments/baselines/results/stage300 experiments/baselines/logs

DATASET="experiments/baselines/datasets/gtf_kgqa_300_stratified_seed20260605.csv"
KG_TRIPLES_CORPUS="experiments/baselines/corpus/kg_triples_corpus.jsonl"
EVIDENCE_CORPUS="experiments/baselines/corpus/evidence_corpus.jsonl"

run_one() {
  local method="$1"
  local topk="$2"
  local corpus="${3:-}"
  local out="experiments/baselines/results/stage300/${method}_stage300.jsonl"
  local metrics="experiments/baselines/results/stage300/${method}_stage300_metrics.json"
  local log="experiments/baselines/logs/${method}_stage300.log"

  echo "============================================================"
  echo "[START] ${method} top_k=${topk}"
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
  echo "[TOKEN] ${method}"
  python tools/baselines/summarize_token_usage.py "${out}"
  echo "[DONE] ${method}"
}

run_one llm_kg_triples 40 "${KG_TRIPLES_CORPUS}"
run_one llm_retrieved_evidence 20 "${EVIDENCE_CORPUS}"
run_one schema_router_no_evidence 50

echo "[DONE] Stage-300 bridge baselines completed"
