#!/usr/bin/env bash
set -euo pipefail
ROOT="/root/work/GansuTechFinance_KGQA_RELEASE_RUNTIME/deliverables/paper_submission_system_20260522_114215"; cd "$ROOT"
export DASHSCOPE_MODEL="qwen3.5-plus"
export LIGHTRAG_ENABLE_LLM_CACHE="0"
: "${DASHSCOPE_API_KEY:?export DASHSCOPE_API_KEY first}"; : "${DASHSCOPE_MODEL:?export DASHSCOPE_MODEL first}"; : "${LIGHTRAG_EMBED_MODEL:?export LIGHTRAG_EMBED_MODEL first}"; : "${LIGHTRAG_EMBED_DIM:?export LIGHTRAG_EMBED_DIM first}"; export LIGHTRAG_CORPUS_VARIANT="${LIGHTRAG_CORPUS_VARIANT:-compact}"
export DASHSCOPE_BASE_URL="${DASHSCOPE_BASE_URL:-https://dashscope.aliyuncs.com/compatible-mode/v1}"
source experiments/external_baselines/.venvs/lightrag/bin/activate
OUTPUT="experiments/external_baselines/results/protocol_v2/lightrag_compact_unified_qwen35_nothinking_nocache_smoke5.jsonl"
mkdir -p "$(dirname "$OUTPUT")"
python experiments/external_baselines/lightrag/lightrag_adapter.py query \
  --mode full \
  --dataset experiments/baselines/datasets/smoke_30.csv \
  --output "$OUTPUT" \
  --limit 5 --answer-policy unified

source /home/vipuser/miniconda3/etc/profile.d/conda.sh
conda activate base
python tools/baselines/check_strong_baseline_outputs.py --expected-rows 5 \
  --expected-protocol comparison_protocol_v2_20260607 --expected-model "$DASHSCOPE_MODEL" "$OUTPUT"
python tools/baselines/evaluate_baseline_results.py \
  --gold experiments/baselines/datasets/smoke_30.csv \
  --pred "$OUTPUT" \
  --output experiments/external_baselines/results/protocol_v2/lightrag_compact_unified_qwen35_nothinking_nocache_smoke5_metrics.json
