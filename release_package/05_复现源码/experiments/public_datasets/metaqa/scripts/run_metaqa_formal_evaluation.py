#!/usr/bin/env python3
"""Controlled formal MetaQA evaluation and unified-core ablation runner."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from collections import Counter, defaultdict
from dataclasses import replace
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.generic_kgqa_framework.adapters.metaqa_real import MetaQARealAdapter
from tools.generic_kgqa_framework.datasets import load_triples
from tools.generic_kgqa_framework.graph import InMemoryKG
from tools.generic_kgqa_framework.validation import assert_valid_schema


SUBJECT_PATTERN = re.compile(r"\[([^\]]+)\]")
VARIANTS = ("full", "no_revisit_constraint", "fuzzy_linking", "no_both")
CONFIRMATION = "RUN_FORMAL_METAQA"


def configure_schema(variant: str):
    schema = MetaQARealAdapter().schema()
    if variant in {"fuzzy_linking", "no_both"}:
        schema = replace(schema, entity_linking_policy="fuzzy_typed")
    if variant in {"no_revisit_constraint", "no_both"}:
        routes = {
            qtype: replace(
                route,
                path_constraints=replace(
                    route.path_constraints,
                    exclude_start_at_steps=(),
                ),
            )
            for qtype, route in schema.routes.items()
        }
        schema = replace(schema, routes=routes)
    assert_valid_schema(schema)
    return schema


def classify_failure(predicted: list[str], gold: list[str], error: str = "") -> str:
    if error:
        return "execution_error"
    pred_set, gold_set = set(predicted), set(gold)
    if pred_set == gold_set:
        return ""
    if not pred_set:
        return "empty_prediction"
    if pred_set - gold_set and not gold_set - pred_set:
        return "over_return"
    if gold_set - pred_set and not pred_set - gold_set:
        return "missing_answers"
    return "mixed_answer_mismatch"


def score(predicted: list[str], gold: list[str]) -> tuple[float, float, float]:
    pred_set, gold_set = set(predicted), set(gold)
    overlap = len(pred_set & gold_set)
    precision = overlap / len(pred_set) if pred_set else 0.0
    recall = overlap / len(gold_set) if gold_set else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def load_questions(
    raw_dir: Path,
    split: str,
    hops: list[int],
    max_questions: int,
    max_per_hop: int,
    max_per_qtype: int,
) -> list[dict]:
    questions = []
    selected_by_qtype = Counter()
    for hop in hops:
        selected_for_hop = 0
        qa_path = raw_dir / f"{hop}-hop/vanilla/qa_{split}.txt"
        qtype_path = raw_dir / f"{hop}-hop/qa_{split}_qtype.txt"
        with qa_path.open(encoding="utf-8", errors="replace") as qa_handle, qtype_path.open(
            encoding="utf-8", errors="replace"
        ) as qtype_handle:
            for source_index, (qa_line, qtype_line) in enumerate(zip(qa_handle, qtype_handle)):
                qtype = qtype_line.strip()
                if max_per_qtype and selected_by_qtype[qtype] >= max_per_qtype:
                    continue
                question, gold_text = qa_line.rstrip("\r\n").split("\t", 1)
                match = SUBJECT_PATTERN.search(question)
                questions.append(
                    {
                        "qid": f"metaqa_{hop}hop_{split}_{source_index:06d}",
                        "hop": hop,
                        "split": split,
                        "source_index": source_index,
                        "qtype": qtype,
                        "question": question,
                        "subject": match.group(1) if match else "",
                        "gold_answers": [item.strip() for item in gold_text.split("|") if item.strip()],
                    }
                )
                selected_for_hop += 1
                selected_by_qtype[qtype] += 1
                if max_questions and len(questions) >= max_questions:
                    return questions
                if max_per_hop and selected_for_hop >= max_per_hop:
                    break
    return questions


def aggregate(rows: list[dict], key: str) -> list[dict]:
    grouped = defaultdict(list)
    for row in rows:
        grouped[row[key]].append(row)
    output = []
    for value, selected in sorted(grouped.items(), key=lambda item: str(item[0])):
        output.append(
            {
                key: value,
                "questions": len(selected),
                "exact": sum(row["exact_match"] for row in selected),
                "accuracy": sum(row["exact_match"] for row in selected) / len(selected),
                "macro_precision": sum(row["precision"] for row in selected) / len(selected),
                "macro_recall": sum(row["recall"] for row in selected) / len(selected),
                "macro_f1": sum(row["f1"] for row in selected) / len(selected),
                "failures": dict(Counter(row["failure"] or "none" for row in selected)),
            }
        )
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--variant", choices=VARIANTS, default="full")
    parser.add_argument("--split", choices=("dev", "test"), default="test")
    parser.add_argument("--hops", nargs="+", type=int, choices=(1, 2, 3), default=[1, 2, 3])
    parser.add_argument("--max-questions", type=int, default=0)
    parser.add_argument("--max-per-hop", type=int, default=0)
    parser.add_argument("--max-per-qtype", type=int, default=0)
    parser.add_argument("--max-answers", type=int, default=10000)
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()
    if (
        args.max_questions < 0
        or args.max_per_hop < 0
        or args.max_per_qtype < 0
        or args.max_answers <= 0
    ):
        parser.error("question limits must be non-negative and --max-answers must be positive")

    raw_dir = Path(args.raw_dir).resolve()
    out_dir = Path(args.out_dir).resolve()
    schema = configure_schema(args.variant)
    questions = load_questions(
        raw_dir,
        args.split,
        args.hops,
        args.max_questions,
        args.max_per_hop,
        args.max_per_qtype,
    )
    constrained_routes = sum(
        bool(route.path_constraints.exclude_start_at_steps) for route in schema.routes.values()
    )
    manifest = {
        "dataset": "MetaQA",
        "split": args.split,
        "hops": args.hops,
        "variant": args.variant,
        "entity_linking_policy": schema.entity_linking_policy,
        "constrained_routes": constrained_routes,
        "questions_planned": len(questions),
        "max_questions": args.max_questions,
        "max_per_hop": args.max_per_hop,
        "max_per_qtype": args.max_per_qtype,
        "max_answers": args.max_answers,
        "raw_dir": str(raw_dir),
        "out_dir": str(out_dir),
    }
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    if args.confirm != CONFIRMATION:
        print(f"DRY RUN ONLY: pass --confirm {CONFIRMATION} to execute")
        return 0

    out_dir.mkdir(parents=True, exist_ok=False)
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    run_started = time.monotonic()
    graph = InMemoryKG(load_triples(str(raw_dir / "kb.txt")), schema)
    graph_load_seconds = time.monotonic() - run_started
    rows = []
    execution_started = time.monotonic()
    for index, item in enumerate(questions, start=1):
        route = schema.routes.get(item["qtype"])
        predicted, error = [], ""
        if route is None:
            error = f"unknown_qtype:{item['qtype']}"
        elif not item["subject"]:
            error = "subject_not_found_in_question"
        else:
            try:
                predicted = graph.execute_route(
                    route, subject=item["subject"], limit=args.max_answers
                ).answers
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
        failure = classify_failure(predicted, item["gold_answers"], error)
        precision, recall, f1 = score(predicted, item["gold_answers"])
        rows.append(
            {
                **item,
                "variant": args.variant,
                "predicted_answers": predicted,
                "exact_match": not failure,
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "failure": failure,
                "error": error,
            }
        )
        if index % 1000 == 0:
            print(
                f"progress={index}/{len(questions)} "
                f"execution_seconds={time.monotonic() - execution_started:.1f}"
            )

    results_path = out_dir / "results.jsonl"
    with results_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    summaries = {"overall": aggregate([{**row, "scope": "overall"} for row in rows], "scope")[0]}
    summaries["by_hop"] = aggregate(rows, "hop")
    summaries["by_qtype"] = aggregate(rows, "qtype")
    summaries["graph_load_seconds"] = graph_load_seconds
    summaries["execution_seconds"] = time.monotonic() - execution_started
    summaries["total_seconds"] = time.monotonic() - run_started
    (out_dir / "summary.json").write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    with (out_dir / "by_qtype.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = ["qtype", "questions", "exact", "accuracy", "macro_precision", "macro_recall", "macro_f1", "failures"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summaries["by_qtype"])

    print(json.dumps(summaries["overall"], ensure_ascii=False, indent=2))
    print(f"results={results_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
