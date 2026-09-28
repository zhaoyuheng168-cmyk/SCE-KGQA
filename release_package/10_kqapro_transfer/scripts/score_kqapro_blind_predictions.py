#!/usr/bin/env python3
"""Isolated evaluator for blind KQA Pro predictions.

Only this script reads validation answers. Do not import it from generation,
reranking, or execution code.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def normalize(value: object) -> str:
    text = "" if value is None else str(value)
    text = re.sub(r"(?<=\d)\.0(?=\s|$)", "", text)
    text = re.sub(r"\s+", "", text.lower())
    return re.sub(r"""["'`.,;:!?\[\]{}()]""", "", text)


def matches(answers: list[str], gold: object) -> bool:
    gold_norm = normalize(gold)
    return any(normalize(answer) == gold_norm for answer in answers)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--val", type=Path, default=ROOT / "data" / "kqapro" / "val.json")
    parser.add_argument(
        "--predictions",
        type=Path,
        default=ROOT / "work" / "kqapro_val_sce_blind_predictions.jsonl",
    )
    parser.add_argument(
        "--details",
        type=Path,
        default=ROOT / "work" / "kqapro_nonoracle_details.csv",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=ROOT / "work" / "kqapro_nonoracle_summary.csv",
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    for path in (args.details, args.summary):
        if path.exists() and not args.overwrite:
            raise FileExistsError(f"Refusing to overwrite: {path}")

    validation = json.loads(args.val.read_text(encoding="utf-8"))
    predictions = [
        json.loads(line)
        for line in args.predictions.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    methods = ("bart_top1", "schema_selected", "sce_full_selected")
    counts = {method: {"correct": 0, "executable": 0, "nonempty": 0} for method in methods}
    detail_rows: list[dict[str, Any]] = []

    for prediction in predictions:
        index = int(prediction["source_index"])
        gold = validation[index]["answer"]
        detail = {
            "question_id": prediction["question_id"],
            "source_index": index,
            "question": prediction["question"],
            "gold_answer": gold,
        }
        for method in methods:
            selected = prediction[method]
            execution = selected["execution"]
            answers = execution["answers"]
            correct = matches(answers, gold)
            counts[method]["correct"] += int(correct)
            counts[method]["executable"] += int(execution["status"] == "ok")
            counts[method]["nonempty"] += int(bool(answers))
            detail[f"{method}_answer"] = "||".join(answers)
            detail[f"{method}_correct"] = str(correct).lower()
            detail[f"{method}_program"] = selected["serialized_program"]
            detail[f"{method}_status"] = execution["status"]
        detail_rows.append(detail)

    args.details.parent.mkdir(parents=True, exist_ok=True)
    with args.details.open("w", encoding="utf-8-sig", newline="") as handle:
        fields = list(detail_rows[0]) if detail_rows else ["question_id"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(detail_rows)

    total = len(predictions)
    summary_rows = []
    for method in methods:
        summary_rows.append(
            {
                "method": method,
                "questions": total,
                "correct": counts[method]["correct"],
                "exact_match_pct": f"{100 * counts[method]['correct'] / total:.3f}" if total else "0.000",
                "executable_pct": f"{100 * counts[method]['executable'] / total:.3f}" if total else "0.000",
                "nonempty_pct": f"{100 * counts[method]['nonempty'] / total:.3f}" if total else "0.000",
                "protocol": "question_only_nonoracle",
            }
        )
    with args.summary.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary_rows[0]))
        writer.writeheader()
        writer.writerows(summary_rows)

    print(json.dumps({"details": str(args.details), "summary": str(args.summary), "rows": total}, ensure_ascii=False))


if __name__ == "__main__":
    main()
