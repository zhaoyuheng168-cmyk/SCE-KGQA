#!/usr/bin/env python3
"""Create a question-only KQA Pro input file for non-oracle evaluation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--val",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "kqapro" / "val.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "work" / "kqapro_val_questions_only.jsonl",
    )
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    if args.output.exists() and not args.overwrite:
        raise FileExistsError(f"Refusing to overwrite: {args.output}")

    rows = json.loads(args.val.read_text(encoding="utf-8"))
    if args.limit > 0:
        rows = rows[: args.limit]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for index, row in enumerate(rows):
            blind_row = {
                "question_id": f"KQAPRO_VAL_{index:05d}",
                "source_index": index,
                "question": str(row["question"]),
            }
            handle.write(json.dumps(blind_row, ensure_ascii=False) + "\n")

    print(json.dumps({"output": str(args.output), "rows": len(rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
