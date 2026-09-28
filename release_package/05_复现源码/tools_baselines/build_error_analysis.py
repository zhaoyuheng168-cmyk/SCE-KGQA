#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build an auditable error-analysis table from unified task-aware rows."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--sample-per-category", type=int, default=10)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    failures = [row for row in read_csv(args.rows) if row.get("paper_passed", "").lower() not in {"true", "1"}]
    counts = Counter(row.get("category", "") for row in failures)
    selected = []
    used = Counter()
    for row in failures:
        category = row.get("category", "")
        if used[category] < args.sample_per_category:
            selected.append(row)
            used[category] += 1

    fields = [
        "question_id", "question", "category", "subcategory", "paper_metric_mode",
        "pass_reason", "precision", "recall", "f1", "route", "final_route",
        "answer_source", "pred_items", "gold_items", "manual_error_type",
        "manual_root_cause", "manual_fix_suggestion",
    ]
    with (args.output_dir / "error_analysis_samples.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in selected:
            writer.writerow(row)

    lines = [
        "# Error Analysis",
        "",
        f"- Total task-aware failures: {len(failures)}",
        "",
        "| Category | Failures |",
        "|---|---:|",
    ]
    lines.extend(f"| {category} | {count} |" for category, count in counts.most_common())
    lines.extend([
        "",
        "Manual labels should use: entity linking, routing, retrieval, multi-hop reasoning, "
        "rule reasoning, evidence grounding, refusal, answer formatting, or gold ambiguity.",
    ])
    (args.output_dir / "error_analysis_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(args.output_dir / "error_analysis_samples.csv")


if __name__ == "__main__":
    main()
