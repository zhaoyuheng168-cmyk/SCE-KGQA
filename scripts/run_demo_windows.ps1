$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$VenvPath = Join-Path $RepoRoot ".venv"
$PythonPath = Join-Path $VenvPath "Scripts\python.exe"

if (-not (Test-Path -LiteralPath $PythonPath)) {
    python -m venv $VenvPath
}

& $PythonPath -m pip install -r (Join-Path $RepoRoot "requirements.txt")
& $PythonPath -m streamlit run (Join-Path $RepoRoot "app\streamlit\app.py")
