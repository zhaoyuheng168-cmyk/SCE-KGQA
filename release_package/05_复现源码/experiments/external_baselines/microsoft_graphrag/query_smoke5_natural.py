#!/usr/bin/env python3
"""Query Microsoft GraphRAG natural-corpus smoke workspace for five questions."""

from __future__ import annotations

import csv
import json
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "experiments/external_baselines"
QUESTIONS = BASE / "common/smoke_questions.csv"
WORKSPACE = BASE / "microsoft_graphrag/workspace/smoke_natural"


def main() -> None:
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output = BASE / "results" / f"microsoft_graphrag_natural_smoke5_{timestamp}.jsonl"
    output.parent.mkdir(parents=True, exist_ok=True)

    with QUESTIONS.open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))[:5]
    with output.open("w", encoding="utf-8") as destination:
        for index, row in enumerate(rows, 1):
            print(f"[{index}/{len(rows)}] querying ...", flush=True)
            started = time.perf_counter()
            try:
                process = subprocess.run(
                    [
                        "graphrag",
                        "query",
                        "--root",
                        str(WORKSPACE),
                        "--method",
                        "local",
                        "--response-type",
                        "Single Sentence",
                        "--query",
                        row["question"],
                    ],
                    capture_output=True,
                    text=True,
                    timeout=180,
                )
                raw_answer = process.stdout.strip()
                returncode = process.returncode
                stderr = process.stderr[-500:]
            except subprocess.TimeoutExpired as exc:
                raw_answer = (exc.stdout or "").strip() if isinstance(exc.stdout, str) else ""
                returncode = 124
                stderr = "query timeout after 180 seconds"
            latency_ms = int((time.perf_counter() - started) * 1000)
            print(f"[{index}/{len(rows)}] returncode={returncode} latency_ms={latency_ms}", flush=True)
            destination.write(
                json.dumps(
                    {
                        "question_id": row["question_id"],
                        "question": row["question"],
                        "method": "microsoft_graphrag_natural",
                        "raw_answer": raw_answer,
                        "prediction": raw_answer,
                        "returncode": returncode,
                        "latency_ms": latency_ms,
                        "stderr": stderr,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            destination.flush()
    print(output)


if __name__ == "__main__":
    main()
