# -*- coding: utf-8 -*-
"""Evaluate a small KGQA dataset with a domain adapter and in-memory triples."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from .adapters import adapter_names, get_adapter
from .datasets import load_triples
from .graph import InMemoryKG


@dataclass(frozen=True)
class EvalItem:
    qid: str
    question: str
    subject: str
    subject_type: str
    gold_answers: List[str]


def _split_answers(value: str) -> List[str]:
    return [item.strip() for item in str(value or "").replace(";", "||").split("||") if item.strip()]


def load_eval_items(path: str) -> List[EvalItem]:
    source = Path(path)
    with source.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        required = {"question", "subject", "subject_type", "gold_answers"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{source} missing columns: {sorted(missing)}")
        items = []
        for idx, row in enumerate(reader, start=1):
            items.append(
                EvalItem(
                    qid=str(row.get("qid") or idx),
                    question=str(row.get("question") or ""),
                    subject=str(row.get("subject") or ""),
                    subject_type=str(row.get("subject_type") or ""),
                    gold_answers=_split_answers(str(row.get("gold_answers") or "")),
                )
            )
    return items


def score_answers(predicted: List[str], gold: List[str]) -> Dict[str, float]:
    pred_set = set(predicted)
    gold_set = set(gold)
    if not pred_set and not gold_set:
        return {"exact": 1.0, "precision": 1.0, "recall": 1.0, "f1": 1.0}
    if not pred_set or not gold_set:
        return {"exact": 0.0, "precision": 0.0, "recall": 0.0, "f1": 0.0}
    hit = len(pred_set & gold_set)
    precision = hit / len(pred_set)
    recall = hit / len(gold_set)
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return {
        "exact": 1.0 if pred_set == gold_set else 0.0,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter", choices=adapter_names(), default="metaqa")
    parser.add_argument("--triples", required=True)
    parser.add_argument("--eval", required=True)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    adapter = get_adapter(args.adapter)
    schema = adapter.schema()
    triples = load_triples(args.triples)
    graph = InMemoryKG(triples, schema)
    items = load_eval_items(args.eval)

    totals = {"exact": 0.0, "precision": 0.0, "recall": 0.0, "f1": 0.0}
    rows = []
    for item in items:
        routes = adapter.route_candidates(question=item.question, subject_type=item.subject_type)
        route = routes[0] if routes else None
        if route is None:
            predicted: List[str] = []
            route_name = ""
        else:
            result = graph.execute_route(route, subject=item.subject, limit=args.limit)
            predicted = result.answers
            route_name = route.qtype
        scores = score_answers(predicted, item.gold_answers)
        for key in totals:
            totals[key] += scores[key]
        rows.append((item, route_name, predicted, scores))

    n = max(len(items), 1)
    print(f"adapter={adapter.name}")
    print(f"triples={len(triples)}")
    print(f"items={len(items)}")
    for key in ["exact", "precision", "recall", "f1"]:
        print(f"{key}={totals[key] / n:.4f}")

    print("details:")
    for item, route_name, predicted, scores in rows:
        print(
            f"{item.qid}\t{route_name}\t"
            f"pred={'||'.join(predicted)}\tgold={'||'.join(item.gold_answers)}\t"
            f"f1={scores['f1']:.4f}"
        )
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow([
                "qid",
                "question",
                "subject",
                "subject_type",
                "route",
                "predicted",
                "gold",
                "exact",
                "precision",
                "recall",
                "f1",
            ])
            for item, route_name, predicted, scores in rows:
                writer.writerow([
                    item.qid,
                    item.question,
                    item.subject,
                    item.subject_type,
                    route_name,
                    "||".join(predicted),
                    "||".join(item.gold_answers),
                    f"{scores['exact']:.6f}",
                    f"{scores['precision']:.6f}",
                    f"{scores['recall']:.6f}",
                    f"{scores['f1']:.6f}",
                ])
        print(f"output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
