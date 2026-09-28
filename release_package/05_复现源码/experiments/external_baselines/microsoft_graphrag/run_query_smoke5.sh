#!/usr/bin/env bash
set -euo pipefail
ROOT="/root/work/GansuTechFinance_KGQA_RELEASE_RUNTIME/deliverables/paper_submission_system_20260522_114215"; cd "$ROOT"
: "${DASHSCOPE_API_KEY:?export DASHSCOPE_API_KEY first}"
source experiments/external_baselines/.venvs/graphrag/bin/activate
python experiments/external_baselines/microsoft_graphrag/query_smoke5.py
