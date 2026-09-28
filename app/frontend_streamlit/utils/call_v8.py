from __future__ import annotations

import os
import re
import sys
import subprocess
from pathlib import Path
from typing import Dict, Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
V8_SCRIPT = PROJECT_ROOT / "retrieval_only" / "scripts" / "answer_hybrid_v8_graph_kag_fallback.py"


def _extract_section(raw: str, title: str) -> str:
    """
    从 V8 输出中提取类似：
    ===== ANSWER =====
    ...
    ===== CYPHER =====
    ...
    """
    pattern = rf"===== {re.escape(title)} =====\s*(.*?)(?=\n===== |\Z)"
    m = re.search(pattern, raw, flags=re.S)
    if not m:
        return ""
    return m.group(1).strip()


def parse_v8_output(raw: str) -> Dict[str, Any]:
    meta: Dict[str, str] = {}

    # 解析 key = value 形式
    for line in raw.splitlines():
        m = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$", line)
        if m:
            meta[m.group(1)] = m.group(2)

    answer = _extract_section(raw, "ANSWER")
    cypher = _extract_section(raw, "CYPHER")
    kag_evidence_answer = _extract_section(raw, "KAG EVIDENCE ANSWER")
    kag_evidence_answer = _extract_section(raw, "KAG EVIDENCE ANSWER")
    kag_evidence = _extract_section(raw, "KAG EVIDENCE")
    evidence = _extract_section(raw, "EVIDENCE")

    return {
        "meta": meta,
        "answer": answer,
        "cypher": cypher,
        "kag_evidence": kag_evidence_answer or kag_evidence or evidence,
        "raw": raw,
    }


def ask_v8(question: str, timeout: int = 180) -> Dict[str, Any]:
    if not V8_SCRIPT.exists():
        return {
            "ok": False,
            "error": f"V8 script not found: {V8_SCRIPT}",
            "meta": {},
            "answer": "",
            "cypher": "",
            "kag_evidence": "",
            "raw": "",
        }

    env = os.environ.copy()
    old_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{PROJECT_ROOT}:{old_pythonpath}" if old_pythonpath else str(PROJECT_ROOT)

    cmd = [sys.executable, str(V8_SCRIPT), question]

    try:
        p = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "error": f"V8 timeout after {timeout}s",
            "meta": {},
            "answer": "",
            "cypher": "",
            "kag_evidence": "",
            "raw": "",
        }

    raw = ""
    if p.stdout:
        raw += p.stdout
    if p.stderr:
        raw += "\n\n[STDERR]\n" + p.stderr

    parsed = parse_v8_output(raw)
    parsed["ok"] = p.returncode == 0
    parsed["returncode"] = p.returncode
    parsed["error"] = "" if p.returncode == 0 else f"V8 exited with code {p.returncode}"
    return parsed

