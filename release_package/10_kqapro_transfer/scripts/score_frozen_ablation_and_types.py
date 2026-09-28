#!/usr/bin/env python3
"""Score frozen ablations and produce type/error analyses."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
VARIANT_LABELS = {
    "bart_top1": "BART top-1",
    "schema_only": "BART top-5 + Schema",
    "execution_only": "BART top-5 + execution feedback",
    "sce_full": "SCE full",
    "sce_wo_schema": "SCE w/o Schema",
    "sce_wo_execution": "SCE w/o execution feedback",
    "sce_wo_nonempty": "SCE w/o non-empty constraint",
    "sce_wo_relevance": "SCE w/o question relevance",
    "sce_wo_evidence": "SCE w/o fact-evidence bonus",
}


def normalize(value: object) -> str:
    text = "" if value is None else str(value)
    text = re.sub(r"(?<=\d)\.0(?=\s|$)", "", text)
    text = re.sub(r"\s+", "", text.lower())
    return re.sub(r"""["'`.,;:!?\[\]{}()]""", "", text)


def correct(candidate: dict[str, Any], gold: object) -> bool:
    target = normalize(gold)
    return any(normalize(answer) == target for answer in candidate["execution"]["answers"])


def classify(program: list[dict[str, Any]]) -> str:
    functions = {str(step.get("function") or "") for step in program}
    if any(function.startswith("Verify") for function in functions):
        return "verification"
    if any(function.startswith("QFilter") for function in functions) or {
        "QueryAttrQualifier", "QueryRelationQualifier", "QueryAttrUnderCondition"
    } & functions:
        return "qualifier_or_evidence"
    has_multihop = "Relate" in functions
    has_composition = bool({"And", "Or", "SelectBetween", "SelectAmong"} & functions)
    if has_multihop and has_composition:
        return "multihop_compositional"
    if has_multihop:
        return "multihop"
    if has_composition:
        return "compositional"
    return "simple_or_attribute"


def error_type(candidate: dict[str, Any], gold_program: list[dict[str, Any]]) -> str:
    execution = candidate["execution"]
    if execution["status"] != "ok":
        message = str(execution.get("error") or "")
        if "unknown" in message.lower() or "attribute" in message.lower():
            return "invalid_schema_or_operation"
        return "execution_error"
    if not execution["answers"]:
        return "empty_execution_result"

    predicted_functions = [step.get("function") for step in candidate["program"]]
    gold_functions = [step.get("function") for step in gold_program]
    if predicted_functions != gold_functions:
        return "program_structure_error"

    predicted_inputs = [step.get("inputs", []) for step in candidate["program"]]
    gold_inputs = [step.get("inputs", []) for step in gold_program]
    if predicted_inputs != gold_inputs:
        flat_pred = json.dumps(predicted_inputs, ensure_ascii=False).lower()
        flat_gold = json.dumps(gold_inputs, ensure_ascii=False).lower()
        if "forward" in flat_pred or "backward" in flat_pred:
            if flat_pred.replace("forward", "x").replace("backward", "x") == flat_gold.replace("forward", "x").replace("backward", "x"):
                return "relation_direction_error"
        return "program_argument_error"
    return "answer_rendering_or_kb_ambiguity"


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--val", type=Path, default=ROOT / "data/kqapro/val.json")
    parser.add_argument(
        "--predictions",
        type=Path,
        default=ROOT / "frozen"
        / "kqapro_holdout_11697_ablation_predictions.jsonl",
    )
    parser.add_argument("--output-dir", type=Path, default=ROOT / "work/recomputed_tables")
    args = parser.parse_args()

    validation = json.loads(args.val.read_text(encoding="utf-8"))
    predictions = [
        json.loads(line) for line in args.predictions.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    totals: dict[str, Counter[str]] = defaultdict(Counter)
    by_type: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    errors: Counter[str] = Counter()
    error_examples: list[dict[str, Any]] = []

    for row in predictions:
        source = validation[int(row["source_index"])]
        bucket = classify(source["program"])
        for variant, candidate in row["variants"].items():
            is_correct = correct(candidate, source["answer"])
            totals[variant]["total"] += 1
            totals[variant]["correct"] += int(is_correct)
            totals[variant]["executable"] += int(candidate["execution"]["status"] == "ok")
            totals[variant]["nonempty"] += int(bool(candidate["execution"]["answers"]))
            by_type[(variant, bucket)]["total"] += 1
            by_type[(variant, bucket)]["correct"] += int(is_correct)

        full = row["variants"]["sce_full"]
        if not correct(full, source["answer"]):
            kind = error_type(full, source["program"])
            errors[kind] += 1
            if len([item for item in error_examples if item["error_type"] == kind]) < 5:
                error_examples.append(
                    {
                        "question_id": row["question_id"],
                        "question": row["question"],
                        "gold_answer": source["answer"],
                        "predicted_answer": "||".join(full["execution"]["answers"]),
                        "error_type": kind,
                        "predicted_program": full["serialized_program"],
                        "gold_functions": "||".join(step["function"] for step in source["program"]),
                    }
                )

    comparison_rows = []
    for variant, counts in totals.items():
        total = counts["total"]
        comparison_rows.append(
            {
                "variant": variant,
                "label": VARIANT_LABELS[variant],
                "questions": total,
                "correct": counts["correct"],
                "exact_match_pct": f"{100 * counts['correct'] / total:.3f}",
                "executable_pct": f"{100 * counts['executable'] / total:.3f}",
                "nonempty_pct": f"{100 * counts['nonempty'] / total:.3f}",
                "candidate_policy": "same_frozen_top5",
            }
        )

    type_rows = []
    for (variant, bucket), counts in sorted(by_type.items()):
        type_rows.append(
            {
                "variant": variant,
                "label": VARIANT_LABELS[variant],
                "complexity_bucket": bucket,
                "questions": counts["total"],
                "correct": counts["correct"],
                "exact_match_pct": f"{100 * counts['correct'] / counts['total']:.3f}",
            }
        )

    error_rows = [
        {"error_type": kind, "count": count, "share_pct": f"{100 * count / sum(errors.values()):.3f}"}
        for kind, count in errors.most_common()
    ]
    write_csv(args.output_dir / "kqapro_frozen_comparison_ablation.csv", comparison_rows)
    write_csv(args.output_dir / "kqapro_frozen_results_by_type.csv", type_rows)
    write_csv(args.output_dir / "kqapro_sce_error_taxonomy.csv", error_rows)
    write_csv(args.output_dir / "kqapro_sce_error_examples.csv", error_examples)

    print(
        json.dumps(
            {
                "rows": len(predictions),
                "comparison": str(args.output_dir / "kqapro_frozen_comparison_ablation.csv"),
                "by_type": str(args.output_dir / "kqapro_frozen_results_by_type.csv"),
                "errors": str(args.output_dir / "kqapro_sce_error_taxonomy.csv"),
                "error_examples": str(args.output_dir / "kqapro_sce_error_examples.csv"),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
