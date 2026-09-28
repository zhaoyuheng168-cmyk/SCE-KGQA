#!/usr/bin/env bash
set -euo pipefail
ROOT="/root/work/GansuTechFinance_KGQA_RELEASE_RUNTIME/deliverables/paper_submission_system_20260522_114215"; cd "$ROOT"
: "${DASHSCOPE_API_KEY:?export DASHSCOPE_API_KEY first}"; : "${DASHSCOPE_MODEL:?export DASHSCOPE_MODEL first}"; : "${LIGHTRAG_EMBED_MODEL:?export LIGHTRAG_EMBED_MODEL first}"; : "${LIGHTRAG_EMBED_DIM:?export LIGHTRAG_EMBED_DIM first}"; export LIGHTRAG_CORPUS_VARIANT="${LIGHTRAG_CORPUS_VARIANT:-compact}"
export DASHSCOPE_BASE_URL="${DASHSCOPE_BASE_URL:-https://dashscope.aliyuncs.com/compatible-mode/v1}"
source experiments/external_baselines/.venvs/lightrag/bin/activate
STAMP="$(date +%Y%m%d_%H%M%S)"; LOG="experiments/external_baselines/logs/lightrag_index_smoke_${STAMP}.log"
python experiments/external_baselines/lightrag/lightrag_adapter.py index --mode smoke >"$LOG" 2>&1
echo "$LOG"
