#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Convert unified baseline JSONL outputs to paper-audit CSV."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


FIELDS = ["question_id", "question", "method", "prediction", "raw_answer", "returncode", "latency_ms"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.input.open("r", encoding="utf-8") as src, args.output.open("w", encoding="utf-8-sig", newline="") as dst:
        writer = csv.DictWriter(dst, fieldnames=FIELDS)
        writer.writeheader()
        for line in src:
            if not line.strip():
                continue
            row = json.loads(line)
            prediction = row.get("answer") or []
            writer.writerow(
                {
                    "question_id": row.get("qid", ""),
                    "question": row.get("question", ""),
                    "method": row.get("method", ""),
                    "prediction": "||".join(str(x) for x in prediction),
                    "raw_answer": row.get("answer_text", ""),
                    "returncode": 0 if row.get("status") in {"ok", "refuse"} else 1,
                    "latency_ms": row.get("latency_ms", 0),
                }
            )
    print(json.dumps({"input": str(args.input), "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
