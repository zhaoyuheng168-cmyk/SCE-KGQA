#!/usr/bin/env python3
"""Train a natural-language MetaQA route classifier and evaluate end to end."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from joblib import dump
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

from tools.generic_kgqa_framework.adapters.metaqa_real import MetaQARealAdapter
from tools.generic_kgqa_framework.datasets import load_triples
from tools.generic_kgqa_framework.graph import InMemoryKG
from tools.generic_kgqa_framework.validation import assert_valid_schema


SUBJECT_PATTERN = re.compile(r"\[([^\]]+)\]")
CONFIRMATION = "RUN_PREDICTED_ROUTE_METAQA"


def normalize_question(question: str) -> str:
    """Remove topic-entity identity while preserving the natural-language template."""

    masked = SUBJECT_PATTERN.sub(" TOPIC_ENTITY ", str(question or "").lower())
    return " ".join(masked.split())


def read_split(
    raw_dir: Path,
    split: str,
    *,
    max_per_qtype: int = 0,
) -> list[dict]:
    rows = []
    selected = Counter()
    for hop in (1, 2, 3):
        qa_path = raw_dir / f"{hop}-hop/vanilla/qa_{split}.txt"
        qtype_path = raw_dir / f"{hop}-hop/qa_{split}_qtype.txt"
        with qa_path.open(encoding="utf-8", errors="replace") as qa_handle, qtype_path.open(
            encoding="utf-8", errors="replace"
        ) as qtype_handle:
            for source_index, (qa_line, qtype_line) in enumerate(zip(qa_handle, qtype_handle)):
                qtype = qtype_line.strip()
                if max_per_qtype and selected[qtype] >= max_per_qtype:
                    continue
                raw_qa = qa_line.rstrip("\r\n")
                if "\t" not in raw_qa:
                    continue
                question, gold_text = raw_qa.split("\t", 1)
                subject_match = SUBJECT_PATTERN.search(question)
                rows.append(
                    {
                        "qid": f"metaqa_{hop}hop_{split}_{source_index:06d}",
                        "hop": hop,
                        "split": split,
                        "source_index": source_index,
                        "question": question,
                        "normalized_question": normalize_question(question),
                        "subject": subject_match.group(1) if subject_match else "",
                        "gold_qtype": qtype,
                        "gold_answers": [
                            item.strip() for item in gold_text.split("|") if item.strip()
                        ],
                    }
                )
                selected[qtype] += 1
    return rows


def build_classifier() -> Pipeline:
    return Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    analyzer="word",
                    ngram_range=(1, 3),
                    min_df=2,
                    sublinear_tf=True,
                    max_features=100000,
                ),
            ),
            ("classifier", LinearSVC(C=1.0, random_state=42)),
        ]
    )


def unique_template_rows(rows: list[dict]) -> list[dict]:
    """Keep one deterministic training example for each normalized template."""

    selected = {}
    for row in rows:
        selected.setdefault(row["normalized_question"], row)
    return [selected[key] for key in sorted(selected)]


def classify_answer_failure(predicted: list[str], gold: list[str], error: str = "") -> str:
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


def answer_scores(predicted: list[str], gold: list[str]) -> tuple[float, float, float]:
    pred_set, gold_set = set(predicted), set(gold)
    overlap = len(pred_set & gold_set)
    precision = overlap / len(pred_set) if pred_set else 0.0
    recall = overlap / len(gold_set) if gold_set else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


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
                "route_correct": sum(row["route_correct"] for row in selected),
                "route_accuracy": sum(row["route_correct"] for row in selected) / len(selected),
                "answer_exact": sum(row["answer_exact"] for row in selected),
                "answer_accuracy": sum(row["answer_exact"] for row in selected) / len(selected),
                "macro_f1": sum(row["f1"] for row in selected) / len(selected),
                "failures": dict(Counter(row["failure"] or "none" for row in selected)),
            }
        )
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--eval-split", choices=("dev", "test"), default="dev")
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
    if args.train_max_per_qtype < 0 or args.eval_max_per_qtype < 0 or args.max_answers <= 0:
        parser.error("limits must be non-negative and --max-answers must be positive")

    raw_dir = Path(args.raw_dir).resolve()
    out_dir = Path(args.out_dir).resolve()
    train_rows = read_split(raw_dir, "train", max_per_qtype=args.train_max_per_qtype)
    eval_rows = read_split(raw_dir, args.eval_split, max_per_qtype=args.eval_max_per_qtype)
    train_questions_before_template_dedup = len(train_rows)
    if args.train_unit == "template":
        train_rows = unique_template_rows(train_rows)
    manifest = {
        "dataset": "MetaQA",
        "setting": "predicted_route_end_to_end",
        "test_qtype_used_as_input": False,
        "topic_entity_masked_for_classifier": True,
        "classifier": "word_1_3gram_tfidf_linear_svc",
        "train_questions": len(train_rows),
        "train_questions_before_template_dedup": train_questions_before_template_dedup,
        "train_unit": args.train_unit,
        "eval_split": args.eval_split,
        "eval_questions": len(eval_rows),
        "train_max_per_qtype": args.train_max_per_qtype,
        "eval_max_per_qtype": args.eval_max_per_qtype,
        "raw_dir": str(raw_dir),
        "out_dir": str(out_dir),
    }
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
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

    adapter = MetaQARealAdapter()
    schema = adapter.schema()
    assert_valid_schema(schema)
    graph_started = time.monotonic()
    graph = InMemoryKG(load_triples(str(raw_dir / "kb.txt")), schema)
    graph_load_seconds = time.monotonic() - graph_started

    execution_started = time.monotonic()
    results = []
    for item, predicted_qtype in zip(eval_rows, predicted_qtypes):
        predicted_qtype = str(predicted_qtype)
        route = schema.routes[predicted_qtype]
        predicted_answers, error = [], ""
        try:
            predicted_answers = graph.execute_route(
                route, subject=item["subject"], limit=args.max_answers
            ).answers
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        failure = classify_answer_failure(predicted_answers, item["gold_answers"], error)
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
                "error": error,
            }
        )
    execution_seconds = time.monotonic() - execution_started

    with (out_dir / "results.jsonl").open("w", encoding="utf-8") as handle:
        for row in results:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    dump(classifier, out_dir / "route_classifier.joblib")

    overall = aggregate([{**row, "scope": "overall"} for row in results], "scope")[0]
    summary = {
        "overall": overall,
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
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
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

    print(json.dumps(overall, ensure_ascii=False, indent=2))
    print(json.dumps(summary["timing"], ensure_ascii=False, indent=2))
    print(f"results={out_dir / 'results.jsonl'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
