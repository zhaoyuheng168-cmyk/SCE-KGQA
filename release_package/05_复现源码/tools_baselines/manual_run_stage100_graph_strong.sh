#!/usr/bin/env bash
set -euo pipefail

ROOT="/root/work/GansuTechFinance_KGQA_RELEASE_RUNTIME/deliverables/paper_submission_system_20260522_114215"
cd "$ROOT"
source /root/work/GansuTechFinance_KGQA_RELEASE_RUNTIME/scripts/加载运行环境变量.sh

if [[ -z "${DASHSCOPE_API_KEY:-}" ]]; then
  echo "ERROR: export DASHSCOPE_API_KEY before running."
  exit 1
fi
export DASHSCOPE_BASE_URL="${DASHSCOPE_BASE_URL:-https://dashscope.aliyuncs.com/compatible-mode/v1}"
export DASHSCOPE_MODEL="${DASHSCOPE_MODEL:-qwen-plus}"

RUN_ID="${RUN_ID:-$(date +%Y%m%d_%H%M%S)}"
OUT_DIR="experiments/baselines/results/strong_stage100_graph_${RUN_ID}"
DATASET="experiments/baselines/datasets/gtf_kgqa_300_stratified_seed20260605.csv"
mkdir -p "$OUT_DIR"

for spec in "kg_context_rag:30" "entity_linked_graphrag:35" "graph_only_kgqa:20"; do
  method="${spec%%:*}"
  topk="${spec##*:}"
  python tools/run_baseline_experiment.py --method "$method" --dataset "$DATASET" --output "$OUT_DIR/${method}_limit100.jsonl" --limit 100 --top-k "$topk"
  python tools/baselines/export_strong_baseline_csv.py "$OUT_DIR/${method}_limit100.jsonl" "$OUT_DIR/${method}_limit100.csv"
done

python tools/baselines/check_strong_baseline_outputs.py "$OUT_DIR"/*.jsonl "$OUT_DIR"/*.csv
echo "RESULT_DIR=$OUT_DIR"
