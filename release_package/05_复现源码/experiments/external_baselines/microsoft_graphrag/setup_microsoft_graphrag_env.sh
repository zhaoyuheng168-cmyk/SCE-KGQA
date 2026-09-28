#!/usr/bin/env bash
set -euo pipefail
ROOT="/root/work/GansuTechFinance_KGQA_RELEASE_RUNTIME/deliverables/paper_submission_system_20260522_114215"
cd "$ROOT"
ENV_DIR="experiments/external_baselines/.venvs/graphrag"
LOG_DIR="experiments/external_baselines/logs"
mkdir -p "$LOG_DIR" "$(dirname "$ENV_DIR")"
python3 -c 'import sys; assert (3,10) <= sys.version_info[:2] <= (3,12), sys.version'
python3 -m venv "$ENV_DIR"
source "$ENV_DIR/bin/activate"
python -m ensurepip --upgrade
python -m pip install --upgrade pip 2>&1 | tee "$LOG_DIR/microsoft_graphrag_setup.log"
python -m pip install graphrag 2>&1 | tee -a "$LOG_DIR/microsoft_graphrag_setup.log"
python -c "import graphrag; print('graphrag import ok')"
