#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lightweight evaluator for comparison baseline JSONL outputs."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from common_io import normalize_text, read_csv_rows, read_jsonl, split_items


def looks_like_refusal(status: str, answer_text: str) -> bool:
    text = normalize_text(answer_text)
    if status == "refuse":
        return True
    markers = [
        "无法",
        "不能",
        "拒绝回答",
        "拒答",
        "超出甘肃科技金融知识图谱的可回答范围",
        "超出可回答范围",
        "非公开",
        "内部清册",
        "内部排名",
        "医疗记录",
        "病历诊断",
    ]
    return any(marker in text for marker in markers)


def score_row(gold: dict[str, str], pred: dict[str, Any]) -> dict[str, Any]:
    should_refuse = str(gold.get("should_refuse", "")).strip().lower() in {"yes", "true", "1", "是"}
    status = str(pred.get("status", ""))
    answer_text = str(pred.get("answer_text") or "")
    pred_items = [str(x) for x in pred.get("answer") or []]
    if should_refuse:
        ok = looks_like_refusal(status, answer_text)
        return {"accuracy": 1.0 if ok else 0.0, "precision": 1.0 if ok else 0.0, "recall": 1.0 if ok else 0.0, "f1": 1.0 if ok else 0.0, "refusal_correct": ok}
    gold_items = split_items(gold.get("gold_items", ""))
    if not gold_items:
        return {"accuracy": 0.0, "precision": 0.0, "recall": 0.0, "f1": 0.0, "refusal_correct": None}
    norm_pred = {normalize_text(x) for x in pred_items if normalize_text(x)}
    pool = normalize_text(answer_text + "||" + "||".join(pred_items))
    hit = 0
    for item in gold_items:
        norm = normalize_text(item)
        if norm in norm_pred or norm in pool:
            hit += 1
    pred_count = len(norm_pred) or len(pred_items)
    precision = hit / max(1, pred_count, hit)
    recall = hit / len(gold_items)
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return {"accuracy": 1.0 if hit == len(gold_items) else 0.0, "precision": precision, "recall": recall, "f1": f1, "refusal_correct": None}


def avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--pred", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    gold_rows = read_csv_rows(args.gold)
    pred_rows = {str(row.get("qid")): row for row in read_jsonl(args.pred)}
    scores: list[dict[str, Any]] = []
    by_cat: dict[str, list[dict[str, Any]]] = defaultdict(list)
    pred_qids = set(pred_rows)
    for gold in gold_rows:
        qid = gold.get("question_id", "")
        if qid not in pred_qids:
            continue
        pred = pred_rows.get(qid, {"status": "missing", "answer": [], "answer_text": ""})
        score = score_row(gold, pred)
        scores.append(score)
        by_cat[gold.get("category", "")].append(score)

    summary = {
        "total": len(scores),
        "accuracy": avg([s["accuracy"] for s in scores]),
        "precision": avg([s["precision"] for s in scores]),
        "recall": avg([s["recall"] for s in scores]),
        "f1": avg([s["f1"] for s in scores]),
        "refusal_accuracy": avg([1.0 if s["refusal_correct"] else 0.0 for s in scores if s["refusal_correct"] is not None]),
        "by_category": {
            cat: {
                "total": len(rows),
                "accuracy": avg([s["accuracy"] for s in rows]),
                "precision": avg([s["precision"] for s in rows]),
                "recall": avg([s["recall"] for s in rows]),
                "f1": avg([s["f1"] for s in rows]),
            }
            for cat, rows in sorted(by_cat.items())
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
