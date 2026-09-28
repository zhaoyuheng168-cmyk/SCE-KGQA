#!/usr/bin/env bash
set -euo pipefail

ROOT="/root/work/GansuTechFinance_KGQA_RELEASE_RUNTIME/deliverables/paper_submission_system_20260522_114215"
cd "$ROOT"
source /root/work/GansuTechFinance_KGQA_RELEASE_RUNTIME/scripts/加载运行环境变量.sh
export GTF_ENABLE_V7_FALLBACK=0

LOCK_FILE="experiments/baselines/logs/stage100_protocol_v2_nonllm.lock"
mkdir -p "$(dirname "$LOCK_FILE")"
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "ERROR: another protocol-v2 stage100 non-LLM run is active."
  exit 1
fi

PROTOCOL="comparison_protocol_v2_20260607"
DATASET="experiments/baselines/datasets/gtf_kgqa_100_stratified_seed20260607.csv"
RESULT_DIR="experiments/baselines/results/stage100_protocol_v2"
mkdir -p "$RESULT_DIR"

python tools/baselines/audit_comparison_protocol.py

run_one() {
  local method="$1"
  local top_k="$2"
  local output="$RESULT_DIR/${method}_stage100.jsonl"
  python tools/run_baseline_experiment.py --method "$method" --dataset "$DATASET" \
    --output "$output" --top-k "$top_k" --resume
  python tools/baselines/check_strong_baseline_outputs.py --expected-rows 100 \
    --expected-protocol "$PROTOCOL" "$output"
  python tools/baselines/evaluate_baseline_results.py --gold "$DATASET" --pred "$output" \
    --output "$RESULT_DIR/${method}_stage100_metrics.json"
}

run_one rule_based_kgqa 80
run_one graph_only_kgqa 80

echo "[DONE] protocol-v2 stage100 non-LLM methods."
