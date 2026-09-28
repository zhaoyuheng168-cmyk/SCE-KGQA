#!/usr/bin/env bash
set -euo pipefail

ROOT="/root/work/GansuTechFinance_KGQA_RELEASE_RUNTIME/deliverables/paper_submission_system_20260522_114215"
cd "$ROOT"
source /root/work/GansuTechFinance_KGQA_RELEASE_RUNTIME/scripts/加载运行环境变量.sh

: "${DASHSCOPE_API_KEY:?export DASHSCOPE_API_KEY first}"
export DASHSCOPE_BASE_URL="${DASHSCOPE_BASE_URL:-https://dashscope.aliyuncs.com/compatible-mode/v1}"
export DASHSCOPE_MODEL="${DASHSCOPE_MODEL:-qwen-plus}"
export LIGHTRAG_EMBED_MODEL="${LIGHTRAG_EMBED_MODEL:-text-embedding-v3}"
export LIGHTRAG_EMBED_DIM="${LIGHTRAG_EMBED_DIM:-1024}"

RUN_ID="${RUN_ID:-$(date +%Y%m%d_%H%M%S)}"
OUT_DIR="experiments/baselines/results/priority_three_smoke_${RUN_ID}"
DATASET="experiments/baselines/datasets/smoke_30.csv"
CORPUS="experiments/baselines/corpus/merged_rag_corpus.jsonl"
mkdir -p "$OUT_DIR" experiments/external_baselines/logs

for spec in "hybrid_rag:30" "text_kg_rag:30"; do
  method="${spec%%:*}"
  topk="${spec##*:}"
  output="$OUT_DIR/${method}_smoke5.jsonl"
  python tools/run_baseline_experiment.py \
    --method "$method" --dataset "$DATASET" --corpus "$CORPUS" \
    --output "$output" --limit 5 --top-k "$topk"
  python tools/baselines/evaluate_baseline_results.py \
    --gold "$DATASET" --pred "$output" --output "$OUT_DIR/${method}_smoke5_metrics.json"
done

python experiments/external_baselines/common/build_external_corpus.py --mode smoke --variant natural --smoke-docs 200
python experiments/external_baselines/lightrag/prepare_workspace.py --mode smoke --variant natural
bash experiments/external_baselines/lightrag/run_index_smoke.sh
bash experiments/external_baselines/lightrag/run_query_smoke5.sh
python tools/baselines/evaluate_baseline_results.py \
  --gold "$DATASET" \
  --pred experiments/external_baselines/results/lightrag_smoke5.jsonl \
  --output "$OUT_DIR/lightrag_smoke5_metrics.json"

echo "RESULT_DIR=$OUT_DIR"
