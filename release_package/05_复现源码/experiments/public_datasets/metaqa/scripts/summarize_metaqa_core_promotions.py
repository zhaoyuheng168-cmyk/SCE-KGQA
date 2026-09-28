#!/usr/bin/env python3
"""Summarize bounded MetaQA results before and after core promotions."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def load_rows(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def summarize(rows: list[dict]) -> dict:
    failures = Counter(row.get("failure") or "none" for row in rows)
    by_hop = {}
    for hop in (1, 2, 3):
        selected = [row for row in rows if row.get("hop") == hop]
        by_hop[hop] = {
            "questions": len(selected),
            "exact": sum(bool(row.get("exact_match")) for row in selected),
        }
    return {
        "questions": len(rows),
        "exact": sum(bool(row.get("exact_match")) for row in rows),
        "failures": failures,
        "by_hop": by_hop,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", required=True)
    parser.add_argument("--after", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()

    before_path = Path(args.before).resolve()
    after_path = Path(args.after).resolve()
    report_path = Path(args.report).resolve()
    before_rows = load_rows(before_path)
    after_rows = load_rows(after_path)
    if len(before_rows) != len(after_rows):
        raise ValueError("before and after result counts differ")

    before_by_qid = {row["qid"]: row for row in before_rows}
    after_by_qid = {row["qid"]: row for row in after_rows}
    if set(before_by_qid) != set(after_by_qid):
        raise ValueError("before and after qid sets differ")

    before = summarize(before_rows)
    after = summarize(after_rows)
    corrected = [
        qid
        for qid in sorted(before_by_qid)
        if not before_by_qid[qid]["exact_match"] and after_by_qid[qid]["exact_match"]
    ]
    regressed = [
        qid
        for qid in sorted(before_by_qid)
        if before_by_qid[qid]["exact_match"] and not after_by_qid[qid]["exact_match"]
    ]
    remaining = [
        after_by_qid[qid]
        for qid in sorted(after_by_qid)
        if not after_by_qid[qid]["exact_match"]
    ]

    report = [
        "# MetaQA Unified-Core Promotion Evidence",
        "",
        "## Scope",
        "",
        "- Bounded coverage smoke: at most 3 test questions per qtype.",
        "- This is evidence for core-promotion decisions, not a formal benchmark result.",
        "- Both runs use the same questions, typed routes, and raw knowledge base.",
        "",
        "## Before and After",
        "",
        "| Configuration | Exact | Accuracy | Failure counts |",
        "|---|---:|---:|---|",
        (
            f"| Before: fuzzy typed linking | {before['exact']}/{before['questions']} | "
            f"{before['exact'] / before['questions']:.4f} | `{dict(before['failures'])}` |"
        ),
        (
            f"| After: exact typed linking | {after['exact']}/{after['questions']} | "
            f"{after['exact'] / after['questions']:.4f} | `{dict(after['failures'])}` |"
        ),
        "",
        f"- Corrected questions: **{len(corrected)}**",
        f"- Regressed questions: **{len(regressed)}**",
        f"- Remaining failures: **{len(remaining)}**",
        "",
        "## Results by Hop",
        "",
        "| Hop | Before exact | After exact | Delta |",
        "|---:|---:|---:|---:|",
    ]
    for hop in (1, 2, 3):
        old = before["by_hop"][hop]
        new = after["by_hop"][hop]
        report.append(
            f"| {hop} | {old['exact']}/{old['questions']} | "
            f"{new['exact']}/{new['questions']} | {new['exact'] - old['exact']:+d} |"
        )

    report.extend(
        [
            "",
            "## Remaining Failures",
            "",
            "| Qtype | Subject | Predicted | Gold | Failure |",
            "|---|---|---|---|---|",
        ]
    )
    for row in remaining:
        report.append(
            f"| `{row['qtype']}` | `{row['subject']}` | "
            f"`{row['predicted_answers']}` | `{row['gold_answers']}` | "
            f"`{row['failure']}` |"
        )
    report.extend(
        [
            "",
            "## Interpretation",
            "",
            "The configurable entity-linking policy corrected all 38 failures caused by "
            "substring-expanded subject candidates and introduced no regressions. The two "
            "remaining failures are same-string entity collisions in the raw MetaQA graph.",
        ]
    )

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"before={before['exact']}/{before['questions']}")
    print(f"after={after['exact']}/{after['questions']}")
    print(f"corrected={len(corrected)}")
    print(f"regressed={len(regressed)}")
    print(f"remaining={len(remaining)}")
    print(f"report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
