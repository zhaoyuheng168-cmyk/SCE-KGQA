#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Evaluate comparison JSONL outputs with strict and task-aware metrics."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BASELINE_DIR = ROOT / "tools/baselines"
if str(BASELINE_DIR) not in sys.path:
    sys.path.insert(0, str(BASELINE_DIR))

from common_io import normalize_text, read_csv_rows, split_items  # noqa: E402

STRICT_EVALUATOR = ROOT / "tools/baselines/evaluate_baseline_results.py"
TASK_AWARE_EVALUATOR = ROOT / "blind_tests/blind1200_v3/eval_tools/evaluate_paper_corrected_metrics.py"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def is_refusal(row: dict[str, Any]) -> bool:
    if row.get("status") == "refuse":
        return True
    raw = row.get("raw") or {}
    if raw.get("is_refusal"):
        return True
    text = normalize_text(row.get("answer_text", ""))
    markers = [
        "无法", "不能", "拒绝回答", "拒答", "超出甘肃科技金融知识图谱的可回答范围",
        "超出可回答范围", "非公开", "内部清册", "内部排名", "医疗记录", "病历诊断",
    ]
    return any(marker in text for marker in markers)


def strict_pass(gold: dict[str, str], pred: dict[str, Any]) -> bool:
    should_refuse = str(gold.get("should_refuse", "")).strip().lower() in {"yes", "true", "1", "是"}
    if should_refuse:
        return is_refusal(pred)
    gold_items = split_items(gold.get("gold_items", ""))
    answer_items = [str(x) for x in pred.get("answer") or []]
    pool = normalize_text(str(pred.get("answer_text") or "") + "||" + "||".join(answer_items))
    return bool(gold_items) and all(normalize_text(item) in pool for item in gold_items)


def convert_for_task_aware(
    pred_path: Path, output_path: Path, gold_by_qid: dict[str, dict[str, str]]
) -> None:
    rows = []
    for row in read_jsonl(pred_path):
        raw = row.get("raw") or {}
        answer_items = [str(x) for x in row.get("answer") or []]
        qid = str(row.get("qid", ""))
        rows.append(
            {
                "question_id": qid,
                "question": row.get("question", ""),
                "category": "",
                "subcategory": "",
                "gold_items_eval": "",
                "pred_items": "||".join(answer_items),
                "graph_answers": "||".join(answer_items),
                "answer_section": row.get("answer_text", ""),
                "passed": "1" if strict_pass(gold_by_qid.get(qid, {}), row) else "0",
                "system_refused": "1" if is_refusal(row) else "0",
                "route": raw.get("route", ""),
                "final_route": raw.get("final_route", ""),
                "answer_source": raw.get("answer_source", ""),
                "intent_source": raw.get("intent_source", ""),
                "system_question_type": raw.get("question_type", ""),
                "returncode": "0" if row.get("status") != "error" else "1",
                "error": row.get("error") or "",
                "latency_ms": row.get("latency_ms", ""),
            }
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0]) if rows else [
        "question_id", "question", "category", "subcategory", "gold_items_eval",
        "pred_items", "graph_answers", "answer_section", "passed", "system_refused",
        "route", "final_route", "answer_source", "intent_source",
        "system_question_type", "returncode", "error", "latency_ms",
    ]
    with output_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("predictions", nargs="+", type=Path)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    gold_by_qid = {row.get("question_id", ""): row for row in read_csv_rows(args.gold)}
    summaries = []
    for pred_path in args.predictions:
        method = pred_path.stem.removesuffix("_formal1300")
        method_dir = args.output_dir / method
        method_dir.mkdir(parents=True, exist_ok=True)
        strict_path = method_dir / "strict_metrics.json"
        task_input = method_dir / "task_aware_input.csv"
        task_dir = method_dir / "task_aware_metrics"

        convert_for_task_aware(pred_path, task_input, gold_by_qid)
        subprocess.run(
            [sys.executable, str(STRICT_EVALUATOR), "--gold", str(args.gold),
             "--pred", str(pred_path), "--output", str(strict_path)],
            cwd=ROOT,
            check=True,
        )
        subprocess.run(
            [sys.executable, str(TASK_AWARE_EVALUATOR), "--source", str(args.gold),
             "--result", str(task_input), "--out-dir", str(task_dir)],
            cwd=ROOT,
            check=True,
        )
        strict = load_json(strict_path)
        task = load_json(task_dir / "paper_corrected_metrics_summary.json")
        summaries.append(
            {
                "method": method,
                "rows": strict.get("total", 0),
                "strict_accuracy": strict.get("accuracy", 0),
                "strict_macro_precision": strict.get("precision", 0),
                "strict_macro_recall": strict.get("recall", 0),
                "strict_macro_f1": strict.get("f1", 0),
                "task_aware_success": task.get("paper_corrected_accuracy", 0),
                "task_aware_macro_f1": task.get("non_refusal_macro_f1", 0),
            }
        )

    summary_json = args.output_dir / "unified_metrics_summary.json"
    summary_json.write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# Unified Comparison Metrics",
        "",
        "| Method | Rows | Strict Accuracy | Strict Macro F1 | Task-aware Success | Task-aware Macro F1 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in summaries:
        lines.append(
            f"| {row['method']} | {row['rows']} | {row['strict_accuracy']:.2%} | "
            f"{row['strict_macro_f1']:.2%} | {row['task_aware_success']:.2%} | "
            f"{row['task_aware_macro_f1']:.2%} |"
        )
    (args.output_dir / "unified_metrics_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(summary_json)


if __name__ == "__main__":
    main()
