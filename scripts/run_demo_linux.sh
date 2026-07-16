#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PATH="${REPO_ROOT}/.venv"

if [[ ! -x "${VENV_PATH}/bin/python" ]]; then
  python3 -m venv "${VENV_PATH}"
fi

"${VENV_PATH}/bin/python" -m pip install -r "${REPO_ROOT}/requirements.txt"
"${VENV_PATH}/bin/python" -m streamlit run "${REPO_ROOT}/app/streamlit/app.py"
