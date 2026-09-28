#!/usr/bin/env python3
"""Evaluate natural-language route prediction on unseen MetaQA templates."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from joblib import dump

from experiments.public_datasets.metaqa.scripts.run_metaqa_predicted_route_evaluation import (
    aggregate,
    answer_scores,
    build_classifier,
    classify_answer_failure,
    read_split,
)
from tools.generic_kgqa_framework.adapters.metaqa_real import MetaQARealAdapter
from tools.generic_kgqa_framework.datasets import load_triples
from tools.generic_kgqa_framework.graph import InMemoryKG


CONFIRMATION = "RUN_TEMPLATE_HOLDOUT_METAQA"


def template_hash(template: str) -> str:
    return hashlib.sha256(template.encode("utf-8")).hexdigest()


def split_by_template(
    rows: list[dict],
    holdout_fraction: float,
    fold_count: int = 0,
    fold_index: int = 0,
) -> tuple[list[dict], list[dict], dict]:
    templates_by_qtype = defaultdict(set)
    for row in rows:
        templates_by_qtype[row["gold_qtype"]].add(row["normalized_question"])

    heldout_templates = {}
    for qtype, templates in templates_by_qtype.items():
        ordered = sorted(templates, key=template_hash)
        if fold_count:
            heldout_templates[qtype] = {
                template
                for position, template in enumerate(ordered)
                if position % fold_count == fold_index
            }
        else:
            heldout_count = max(1, round(len(ordered) * holdout_fraction))
            if heldout_count >= len(ordered):
                heldout_count = len(ordered) - 1
            heldout_templates[qtype] = set(ordered[:heldout_count])

    train_rows, eval_rows = [], []
    for row in rows:
        if row["normalized_question"] in heldout_templates[row["gold_qtype"]]:
            eval_rows.append(row)
        else:
            train_rows.append(row)
    manifest = {
        qtype: {
            "total_templates": len(templates_by_qtype[qtype]),
            "heldout_templates": len(heldout_templates[qtype]),
        }
        for qtype in sorted(templates_by_qtype)
    }
    return train_rows, eval_rows, manifest


def cap_by_qtype(rows: list[dict], limit: int) -> list[dict]:
    if not limit:
        return rows
    selected, counts = [], Counter()
    for row in rows:
        if counts[row["gold_qtype"]] >= limit:
            continue
        selected.append(row)
        counts[row["gold_qtype"]] += 1
    return selected


def unique_template_rows(rows: list[dict]) -> list[dict]:
    """Keep one deterministic training example for each normalized template."""

    selected = {}
    for row in rows:
        selected.setdefault(row["normalized_question"], row)
    return [selected[key] for key in sorted(selected)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--holdout-fraction", type=float, default=0.2)
    parser.add_argument("--fold-count", type=int, default=0)
    parser.add_argument("--fold-index", type=int, default=0)
    parser.add_argument("--train-max-per-qtype", type=int, default=0)
    parser.add_argument("--eval-max-per-qtype", type=int, default=0)
    parser.add_argument(
        "--train-unit",
        choices=("question", "template"),
        default="question",
        help="Train on every question or one representative per normalized template.",
    )
    parser.add_argument("--max-answers", type=int, default=10000)
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()
    if not 0.0 < args.holdout_fraction < 1.0:
        parser.error("--holdout-fraction must be between 0 and 1")
    if args.fold_count < 0:
        parser.error("--fold-count must be non-negative")
    if args.fold_count and args.fold_count < 2:
        parser.error("--fold-count must be at least 2 when enabled")
    if args.fold_index < 0 or (args.fold_count and args.fold_index >= args.fold_count):
        parser.error("--fold-index must be between 0 and fold-count - 1")
    if not args.fold_count and args.fold_index:
        parser.error("--fold-index requires --fold-count")

    raw_dir = Path(args.raw_dir).resolve()
    out_dir = Path(args.out_dir).resolve()
    all_rows = read_split(raw_dir, "train")
    train_rows, eval_rows, template_manifest = split_by_template(
        all_rows,
        args.holdout_fraction,
        args.fold_count,
        args.fold_index,
    )
    train_rows = cap_by_qtype(train_rows, args.train_max_per_qtype)
    eval_rows = cap_by_qtype(eval_rows, args.eval_max_per_qtype)
    train_questions_before_template_dedup = len(train_rows)
    if args.train_unit == "template":
        train_rows = unique_template_rows(train_rows)
    train_templates = {row["normalized_question"] for row in train_rows}
    eval_templates = {row["normalized_question"] for row in eval_rows}
    overlap = train_templates & eval_templates
    if overlap:
        raise RuntimeError(f"template leakage detected: {len(overlap)} overlapping templates")

    manifest = {
        "dataset": "MetaQA",
        "setting": "template_heldout_predicted_route_end_to_end",
        "source_split": "train",
        "holdout_fraction": args.holdout_fraction,
        "fold_count": args.fold_count,
        "fold_index": args.fold_index,
        "topic_entity_masked_for_classifier": True,
        "train_questions": len(train_rows),
        "train_questions_before_template_dedup": train_questions_before_template_dedup,
        "train_unit": args.train_unit,
        "eval_questions": len(eval_rows),
        "train_unique_templates": len(train_templates),
        "eval_unique_templates": len(eval_templates),
        "template_overlap": len(overlap),
        "train_max_per_qtype": args.train_max_per_qtype,
        "eval_max_per_qtype": args.eval_max_per_qtype,
        "templates_by_qtype": template_manifest,
        "raw_dir": str(raw_dir),
        "out_dir": str(out_dir),
    }
    print(json.dumps({k: v for k, v in manifest.items() if k != "templates_by_qtype"}, indent=2))
    if args.confirm != CONFIRMATION:
        print(f"DRY RUN ONLY: pass --confirm {CONFIRMATION} to execute")
        return 0

    out_dir.mkdir(parents=True, exist_ok=False)
    run_started = time.monotonic()
    classifier = build_classifier()
    classifier.fit(
        [row["normalized_question"] for row in train_rows],
        [row["gold_qtype"] for row in train_rows],
    )
    training_seconds = time.monotonic() - run_started
    predicted_qtypes = classifier.predict([row["normalized_question"] for row in eval_rows])
    prediction_seconds = time.monotonic() - run_started - training_seconds

    schema = MetaQARealAdapter().schema()
    graph_started = time.monotonic()
    graph = InMemoryKG(load_triples(str(raw_dir / "kb.txt")), schema)
    graph_load_seconds = time.monotonic() - graph_started
    execution_started = time.monotonic()
    results = []
    for item, predicted_qtype in zip(eval_rows, predicted_qtypes):
        predicted_qtype = str(predicted_qtype)
        predicted_answers = graph.execute_route(
            schema.routes[predicted_qtype], subject=item["subject"], limit=args.max_answers
        ).answers
        failure = classify_answer_failure(predicted_answers, item["gold_answers"])
        precision, recall, f1 = answer_scores(predicted_answers, item["gold_answers"])
        results.append(
            {
                **item,
                "predicted_qtype": predicted_qtype,
                "route_correct": predicted_qtype == item["gold_qtype"],
                "predicted_answers": predicted_answers,
                "answer_exact": not failure,
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "failure": failure,
                "error": "",
            }
        )
    execution_seconds = time.monotonic() - execution_started

    with (out_dir / "results.jsonl").open("w", encoding="utf-8") as handle:
        for row in results:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    dump(classifier, out_dir / "route_classifier.joblib")

    summary = {
        "overall": aggregate([{**row, "scope": "overall"} for row in results], "scope")[0],
        "by_hop": aggregate(results, "hop"),
        "by_gold_qtype": aggregate(results, "gold_qtype"),
        "timing": {
            "training_seconds": training_seconds,
            "route_prediction_seconds": prediction_seconds,
            "graph_load_seconds": graph_load_seconds,
            "answer_execution_seconds": execution_seconds,
            "total_seconds": time.monotonic() - run_started,
        },
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with (out_dir / "by_qtype.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = [
            "gold_qtype",
            "questions",
            "route_correct",
            "route_accuracy",
            "answer_exact",
            "answer_accuracy",
            "macro_f1",
            "failures",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summary["by_gold_qtype"])

    print(json.dumps(summary["overall"], ensure_ascii=False, indent=2))
    print(json.dumps(summary["timing"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
