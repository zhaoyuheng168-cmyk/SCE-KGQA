#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Score ablation raw results with the paper-corrected metric script."""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
METRICS_SCRIPT = ROOT / "blind_tests/blind1200_v3/eval_tools/evaluate_paper_corrected_metrics.py"

DEFAULT_VERSIONS = [
    "full_system",
    "without_embedding_enhancement",
    "without_entity_embedding",
    "without_relation_embedding",
    "without_answer_rerank",
    "without_evidence_aware_retrieval",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "是"}


SEP_RE = re.compile(r"\|\||[；;，,\n\r]+")


def norm_text(value: object) -> str:
    s = "" if value is None else str(value).strip()
    if not s or s.lower() == "nan":
        return ""
    s = re.sub(r"\s+", "", s)
    return s.replace("（", "(").replace("）", ")").replace("“", "").replace("”", "")


def split_items(value: object) -> list[str]:
    s = "" if value is None else str(value)
    if not s or s.lower() == "nan":
        return []
    out: list[str] = []
    for part in SEP_RE.split(s):
        item = part.strip().strip("。；;，,、 ")
        if item and item.lower() != "nan" and item not in out:
            out.append(item)
    return out


def official_legacy_pass(row: dict[str, str], pred_items: str, answer_text: str, is_timeout: bool) -> bool:
    """Mirror the legacy batch evaluator's coarse pass bit used by paper metrics."""
    if is_timeout:
        return False
    system_refused = truthy(row.get("is_refusal", ""))
    if row.get("category", "") == "refusal_boundary":
        return system_refused

    gold_items = split_items(row.get("gold_items", ""))
    answer_pool = "\n".join(
        [
            answer_text,
            pred_items,
            row.get("graph_answers", "") or "",
            row.get("kag_answers", "") or "",
        ]
    )
    norm_pool = norm_text(answer_pool)
    return bool(gold_items) and all(norm_text(g) and norm_text(g) in norm_pool for g in gold_items)


def looks_like_refusal(row: dict[str, str]) -> bool:
    if truthy(row.get("system_refused", "")):
        return True
    text = norm_text(row.get("answer_section", ""))
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


def strict_score(result_row: dict[str, str], source_row: dict[str, str]) -> dict[str, float]:
    should_refuse = str(source_row.get("should_refuse", "")).strip().lower() in {
        "yes", "true", "1", "是"
    }
    if should_refuse:
        ok = looks_like_refusal(result_row)
        value = 1.0 if ok else 0.0
        return {"accuracy": value, "precision": value, "recall": value, "f1": value}

    gold = split_items(source_row.get("gold_items", ""))
    pred = split_items(
        result_row.get("pred_items", "")
        or result_row.get("graph_answers", "")
        or result_row.get("answer_section", "")
    )
    pred_norm = {norm_text(item) for item in pred if norm_text(item)}
    pool = norm_text(
        str(result_row.get("answer_section", "") or "") + "||" + "||".join(pred)
    )
    hit = sum(1 for item in gold if norm_text(item) in pred_norm or norm_text(item) in pool)
    pred_count = len(pred_norm) or len(pred)
    precision = hit / max(1, pred_count, hit)
    recall = hit / len(gold) if gold else 0.0
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return {
        "accuracy": 1.0 if gold and hit == len(gold) else 0.0,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def strict_summary(source: Path, metrics_input: Path) -> dict[str, object]:
    source_by_qid = {row.get("question_id", ""): row for row in read_csv(source)}
    scores = []
    by_category: dict[str, list[dict[str, float]]] = defaultdict(list)
    for row in read_csv(metrics_input):
        gold = source_by_qid.get(row.get("question_id", ""), {})
        score = strict_score(row, gold)
        scores.append(score)
        by_category[gold.get("category", "")].append(score)

    def avg(key: str, rows: list[dict[str, float]]) -> float:
        return sum(row[key] for row in rows) / len(rows) if rows else 0.0

    return {
        "total": len(scores),
        "strict_accuracy": avg("accuracy", scores),
        "strict_macro_precision": avg("precision", scores),
        "strict_macro_recall": avg("recall", scores),
        "strict_macro_f1": avg("f1", scores),
        "by_category": {
            category: {
                "total": len(rows),
                "strict_accuracy": avg("accuracy", rows),
                "strict_macro_precision": avg("precision", rows),
                "strict_macro_recall": avg("recall", rows),
                "strict_macro_f1": avg("f1", rows),
            }
            for category, rows in sorted(by_category.items())
        },
    }


def convert_raw_for_metrics(raw_csv: Path, converted_csv: Path) -> None:
    rows = []
    for row in read_csv(raw_csv):
        is_timeout = str(row.get("returncode", "")).strip() != "0"
        pred_items = "" if is_timeout else (row.get("graph_answers") or row.get("kag_answers") or "")
        answer_text = "" if is_timeout else row.get("answer", "")
        legacy_passed = official_legacy_pass(row, pred_items, answer_text, is_timeout)
        rows.append(
            {
                "question_id": row.get("question_id", ""),
                "question": row.get("question", ""),
                "category": row.get("category", ""),
                "subcategory": row.get("subcategory", ""),
                "gold_items_eval": row.get("gold_items", ""),
                "pred_items": pred_items,
                "graph_answers": pred_items,
                "answer_section": answer_text,
                "passed": "1" if legacy_passed else "0",
                "system_refused": "1" if truthy(row.get("is_refusal", "")) else "0",
                "route": row.get("route", ""),
                "final_route": row.get("final_route", ""),
                "answer_source": row.get("answer_source", ""),
                "intent_source": row.get("intent_source", ""),
                "system_question_type": row.get("question_type", ""),
                "returncode": row.get("returncode", ""),
                "error": row.get("error", ""),
                "latency_ms": row.get("latency_ms", ""),
            }
        )
    fieldnames = [
        "question_id",
        "question",
        "category",
        "subcategory",
        "gold_items_eval",
        "pred_items",
        "graph_answers",
        "answer_section",
        "passed",
        "system_refused",
        "route",
        "final_route",
        "answer_source",
        "intent_source",
        "system_question_type",
        "returncode",
        "error",
        "latency_ms",
    ]
    write_csv(converted_csv, rows, fieldnames)


def pct(value: object) -> str:
    try:
        return f"{float(value) * 100:.2f}%"
    except Exception:
        return ""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        type=Path,
        default=ROOT / "experiments/ablation_embedding_focused_120.csv",
    )
    parser.add_argument(
        "--result-root",
        type=Path,
        default=ROOT / "experiments/results/ablation_embedding_focused_120_rerun_workers4",
    )
    parser.add_argument("--versions", nargs="+", default=DEFAULT_VERSIONS)
    args = parser.parse_args()

    result_root = args.result_root.resolve()
    source = args.source.resolve()
    summary_rows: list[dict[str, object]] = []
    for version in args.versions:
        version_dir = result_root / version
        raw_csv = version_dir / "raw_result.csv"
        if not raw_csv.exists():
            raise FileNotFoundError(raw_csv)

        converted_csv = version_dir / "metrics_input.csv"
        metrics_dir = version_dir / "paper_corrected_metrics"
        convert_raw_for_metrics(raw_csv, converted_csv)
        subprocess.run(
            [
                sys.executable,
                str(METRICS_SCRIPT),
                "--source",
                str(source),
                "--result",
                str(converted_csv),
                "--out-dir",
                str(metrics_dir),
            ],
            cwd=str(ROOT),
            check=True,
        )

        summary_json = metrics_dir / "paper_corrected_metrics_summary.json"
        summary = json.loads(summary_json.read_text(encoding="utf-8"))
        strict = strict_summary(source, converted_csv)
        (version_dir / "strict_metrics.json").write_text(
            json.dumps(strict, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        summary_rows.append(
            {
                "version": version,
                "total": summary.get("total", ""),
                "strict_accuracy": strict.get("strict_accuracy", ""),
                "strict_macro_precision": strict.get("strict_macro_precision", ""),
                "strict_macro_recall": strict.get("strict_macro_recall", ""),
                "strict_macro_f1": strict.get("strict_macro_f1", ""),
                "task_aware_success": summary.get("paper_corrected_accuracy", ""),
                "task_aware_macro_f1": summary.get("non_refusal_macro_f1", ""),
                "metrics_input": str(converted_csv.relative_to(ROOT)),
                "metrics_dir": str(metrics_dir.relative_to(ROOT)),
            }
        )

    summary_csv = result_root / "ablation_correctness_summary.csv"
    summary_fields = [
        "version",
        "total",
        "strict_accuracy",
        "strict_macro_precision",
        "strict_macro_recall",
        "strict_macro_f1",
        "task_aware_success",
        "task_aware_macro_f1",
        "metrics_input",
        "metrics_dir",
    ]
    write_csv(summary_csv, summary_rows, summary_fields)

    lines = [
        "# Unified Ablation Metrics",
        "",
        f"样本文件：`{source.relative_to(ROOT)}`",
        "",
        "| 系统版本 | 样本数 | Strict Accuracy | Strict Macro F1 | Task-aware Success | Task-aware Macro F1 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in summary_rows:
        lines.append(
            "| {version} | {total} | {strict_acc} | {strict_f1} | {task_success} | {task_f1} |".format(
                version=f"`{row['version']}`",
                total=row["total"],
                strict_acc=pct(row["strict_accuracy"]),
                strict_f1=pct(row["strict_macro_f1"]),
                task_success=pct(row["task_aware_success"]),
                task_f1=pct(row["task_aware_macro_f1"]),
            )
        )
    summary_md = result_root / "ablation_correctness_summary.md"
    summary_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"summary_csv={summary_csv}")
    print(f"summary_md={summary_md}")


if __name__ == "__main__":
    main()
