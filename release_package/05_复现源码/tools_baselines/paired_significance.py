#!/usr/bin/env python3
"""Paired McNemar test and bootstrap confidence intervals for strict accuracy."""

from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path
from typing import Any

from common_io import normalize_text, read_csv_rows, read_jsonl, split_items
from evaluate_baseline_results import looks_like_refusal


def passed(gold: dict[str, str], pred: dict[str, Any]) -> bool:
    should_refuse = str(gold.get("should_refuse", "")).strip().lower() in {"yes", "true", "1", "是"}
    if should_refuse:
        return looks_like_refusal(str(pred.get("status", "")), str(pred.get("answer_text", "")))
    gold_items = split_items(gold.get("gold_items", ""))
    pool = normalize_text(str(pred.get("answer_text") or "") + "||" + "||".join(str(x) for x in pred.get("answer") or []))
    return bool(gold_items) and all(normalize_text(item) in pool for item in gold_items)


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, int(q * (len(ordered) - 1))))]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--ours", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bootstrap", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=20260607)
    args = parser.parse_args()

    gold = {row["question_id"]: row for row in read_csv_rows(args.gold)}
    ours = {str(row.get("qid")): row for row in read_jsonl(args.ours)}
    baseline = {str(row.get("qid")): row for row in read_jsonl(args.baseline)}
    qids = [qid for qid in gold if qid in ours and qid in baseline]
    ours_pass = [passed(gold[qid], ours[qid]) for qid in qids]
    base_pass = [passed(gold[qid], baseline[qid]) for qid in qids]
    b = sum(1 for o, x in zip(ours_pass, base_pass) if o and not x)
    c = sum(1 for o, x in zip(ours_pass, base_pass) if not o and x)
    # Exact two-sided binomial McNemar p-value.
    discordant = b + c
    tail = (
        sum(
            math.exp(
                math.lgamma(discordant + 1)
                - math.lgamma(k + 1)
                - math.lgamma(discordant - k + 1)
                - discordant * math.log(2)
            )
            for k in range(0, min(b, c) + 1)
        )
        if discordant
        else 1.0
    )
    p_value = min(1.0, 2 * tail)

    rng = random.Random(args.seed)
    differences = []
    for _ in range(args.bootstrap):
        sample = [rng.randrange(len(qids)) for _ in qids]
        differences.append(
            sum((1.0 if ours_pass[i] else 0.0) - (1.0 if base_pass[i] else 0.0) for i in sample)
            / len(sample)
        )
    result = {
        "rows": len(qids),
        "ours_accuracy": sum(ours_pass) / len(qids),
        "baseline_accuracy": sum(base_pass) / len(qids),
        "paired_difference": sum(ours_pass) / len(qids) - sum(base_pass) / len(qids),
        "difference_ci95": [percentile(differences, 0.025), percentile(differences, 0.975)],
        "mcnemar_ours_only_correct": b,
        "mcnemar_baseline_only_correct": c,
        "mcnemar_exact_p_value": p_value,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
