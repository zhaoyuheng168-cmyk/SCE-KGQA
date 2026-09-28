#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a deterministic expert-review sheet from predictions."""

from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pred", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sample-size", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20260607)
    args = parser.parse_args()

    rows = read_jsonl(args.pred)
    rng = random.Random(args.seed)
    sample = rng.sample(rows, min(args.sample_size, len(rows)))
    fields = [
        "review_id", "question_id", "question", "system_answer", "evidence",
        "factual_correctness_1_5", "completeness_1_5", "usefulness_1_5",
        "should_refuse_yes_no", "system_refusal_correct_yes_no",
        "reviewer_confidence_1_5", "reviewer_comment",
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for idx, row in enumerate(sample, 1):
            writer.writerow(
                {
                    "review_id": f"R{idx:03d}",
                    "question_id": row.get("qid", ""),
                    "question": row.get("question", ""),
                    "system_answer": row.get("answer_text", ""),
                    "evidence": json.dumps(row.get("evidence", ""), ensure_ascii=False),
                }
            )
    print(args.output)


if __name__ == "__main__":
    main()
