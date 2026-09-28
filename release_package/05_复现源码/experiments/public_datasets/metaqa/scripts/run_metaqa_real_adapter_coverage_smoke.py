#!/usr/bin/env python3
"""Bounded coverage smoke for all real MetaQA qtypes through the unified core.

This is not a formal evaluation runner. It enforces at most three questions per
qtype and at most 147 questions in total.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.generic_kgqa_framework.adapters.metaqa_real import MetaQARealAdapter
from tools.generic_kgqa_framework.datasets import load_triples
from tools.generic_kgqa_framework.graph import InMemoryKG
from tools.generic_kgqa_framework.validation import assert_valid_schema


SUBJECT_PATTERN = re.compile(r"\[([^\]]+)\]")
HOPS = (1, 2, 3)
SPLIT = "test"
MAX_PER_QTYPE = 3
MAX_TOTAL = 147
MAX_ANSWERS_PER_QUESTION = 10000


def classify_failure(
    *,
    subject_found: bool,
    predicted: List[str],
    gold: List[str],
    error: str = "",
) -> str:
    if error:
        return "execution_error"
    if not subject_found:
        return "subject_not_found"
    pred_set = set(predicted)
    gold_set = set(gold)
    if pred_set == gold_set:
        return ""
    if not pred_set and gold_set:
        return "empty_prediction"
    if pred_set - gold_set and not gold_set - pred_set:
        return "over_return"
    if gold_set - pred_set and not pred_set - gold_set:
        return "missing_answers"
    return "mixed_answer_mismatch"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--limit-per-qtype", type=int, default=3)
    args = parser.parse_args()

    if args.limit_per_qtype <= 0 or args.limit_per_qtype > MAX_PER_QTYPE:
        parser.error(f"--limit-per-qtype must be between 1 and {MAX_PER_QTYPE}")

    adapter = MetaQARealAdapter()
    schema = adapter.schema()
    assert_valid_schema(schema)
    if len(schema.routes) * args.limit_per_qtype > MAX_TOTAL:
        parser.error(f"requested total exceeds hard limit {MAX_TOTAL}")

    raw_dir = Path(args.raw_dir).resolve()
    out_dir = Path(args.out_dir).resolve()
    triples = load_triples(str(raw_dir / "kb.txt"))
    graph = InMemoryKG(triples, schema)

    selected: Dict[str, List[dict]] = defaultdict(list)
    for hop in HOPS:
        qa_path = raw_dir / f"{hop}-hop/vanilla/qa_{SPLIT}.txt"
        qtype_path = raw_dir / f"{hop}-hop/qa_{SPLIT}_qtype.txt"
        with qa_path.open("r", encoding="utf-8", errors="replace") as qa_handle, qtype_path.open(
            "r", encoding="utf-8", errors="replace"
        ) as qtype_handle:
            for source_index, (qa_line, qtype_line) in enumerate(zip(qa_handle, qtype_handle)):
                qtype = qtype_line.strip()
                if qtype not in schema.routes or len(selected[qtype]) >= args.limit_per_qtype:
                    continue
                raw_qa = qa_line.rstrip("\r\n")
                if "\t" not in raw_qa:
                    selected[qtype].append(
                        {
                            "source_index": source_index,
                            "hop": hop,
                            "qtype": qtype,
                            "question": raw_qa,
                            "gold_answers": [],
                            "parse_failure": "malformed_qa_missing_tab",
                        }
                    )
                    continue
                question, gold_text = raw_qa.split("\t", 1)
                match = SUBJECT_PATTERN.search(question)
                selected[qtype].append(
                    {
                        "source_index": source_index,
                        "hop": hop,
                        "qtype": qtype,
                        "question": question,
                        "subject": match.group(1) if match else "",
                        "gold_answers": [
                            item.strip() for item in gold_text.split("|") if item.strip()
                        ],
                        "parse_failure": "" if match else "subject_not_found",
                    }
                )

    rows = []
    for qtype, route in sorted(schema.routes.items(), key=lambda item: (item[1].metadata["hop"], item[0])):
        for sample_number, item in enumerate(selected.get(qtype, [])):
            predicted: List[str] = []
            evidence_paths = []
            step_frontier_sizes = []
            excluded_counts = []
            error = ""
            if not item.get("parse_failure"):
                try:
                    result = graph.execute_route(
                        route,
                        subject=item["subject"],
                        limit=MAX_ANSWERS_PER_QUESTION,
                    )
                    predicted = result.answers
                    evidence_paths = [
                        [
                            {
                                "source": triple.subject,
                                "relation": triple.relation,
                                "target": triple.object,
                            }
                            for triple in path
                        ]
                        for path in result.evidence_paths
                    ]
                    step_frontier_sizes = result.step_frontier_sizes
                    excluded_counts = result.excluded_start_revisit_counts
                except Exception as exc:
                    error = f"{type(exc).__name__}: {exc}"

            failure = item.get("parse_failure") or classify_failure(
                subject_found=bool(item.get("subject")),
                predicted=predicted,
                gold=item["gold_answers"],
                error=error,
            )
            rows.append(
                {
                    "qid": f"metaqa_{item['hop']}hop_test_{qtype}_{item['source_index']:06d}",
                    "source_index": item["source_index"],
                    "hop": item["hop"],
                    "split": SPLIT,
                    "qtype": qtype,
                    "question": item["question"],
                    "subject": item.get("subject", ""),
                    "subject_type": route.subject_type,
                    "target_type": route.target_type,
                    "typed_path": [
                        {
                            "source_type": step.src_type,
                            "relation": step.relation,
                            "target_type": step.dst_type,
                            "direction": step.direction,
                        }
                        for step in route.path
                    ],
                    "path_constraints": {
                        "exclude_start_at_steps": list(
                            route.path_constraints.exclude_start_at_steps
                        )
                    },
                    "step_frontier_sizes": step_frontier_sizes,
                    "excluded_start_revisit_counts": excluded_counts,
                    "predicted_answers": predicted,
                    "gold_answers": item["gold_answers"],
                    "exact_match": not failure,
                    "failure": failure,
                    "error": error,
                    "evidence_paths": evidence_paths,
                    "sample_number": sample_number,
                }
            )

    if len(rows) > MAX_TOTAL:
        raise RuntimeError(f"hard total limit exceeded: {len(rows)} > {MAX_TOTAL}")

    out_dir.mkdir(parents=True, exist_ok=True)
    results_path = out_dir / "metaqa_real_adapter_coverage_results.jsonl"
    with results_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    by_qtype = {}
    for qtype, route in sorted(schema.routes.items()):
        qrows = [row for row in rows if row["qtype"] == qtype]
        failures = Counter(row["failure"] or "none" for row in qrows)
        by_qtype[qtype] = {
            "hop": route.metadata["hop"],
            "selected": len(qrows),
            "exact": sum(1 for row in qrows if row["exact_match"]),
            "failure_counts": failures,
        }

    summary_path = out_dir / "metaqa_real_adapter_coverage_by_qtype.csv"
    with summary_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["hop", "qtype", "selected", "exact", "failure_counts"])
        for qtype, summary in sorted(by_qtype.items(), key=lambda item: (item[1]["hop"], item[0])):
            writer.writerow(
                [
                    summary["hop"],
                    qtype,
                    summary["selected"],
                    summary["exact"],
                    json.dumps(summary["failure_counts"], ensure_ascii=False, sort_keys=True),
                ]
            )

    failure_counts = Counter(row["failure"] or "none" for row in rows)
    exact_count = sum(1 for row in rows if row["exact_match"])
    complete_qtypes = sum(
        1 for summary in by_qtype.values() if summary["selected"] == args.limit_per_qtype
    )
    report = [
        "# Real MetaQA Unified-Core Coverage Smoke",
        "",
        "- This is a bounded coverage smoke, not a formal evaluation.",
        f"- Limit per qtype: **{args.limit_per_qtype}**",
        f"- Qtypes covered: **{complete_qtypes}/{len(schema.routes)}**",
        f"- Questions executed: **{len(rows)}/{MAX_TOTAL} maximum**",
        f"- Exact matches: **{exact_count}/{len(rows)}**",
        f"- Distinct failures: **{len([key for key in failure_counts if key != 'none'])}**",
        "",
        "## Failure Counts",
        "",
    ]
    for failure, count in sorted(failure_counts.items()):
        report.append(f"- `{failure}`: {count}")
    report.extend(
        [
            "",
            "## Per-Qtype Summary",
            "",
            "| Hop | Qtype | Selected | Exact | Failures |",
            "|---:|---|---:|---:|---|",
        ]
    )
    for qtype, summary in sorted(by_qtype.items(), key=lambda item: (item[1]["hop"], item[0])):
        report.append(
            f"| {summary['hop']} | `{qtype}` | {summary['selected']} | {summary['exact']} | "
            f"`{dict(summary['failure_counts'])}` |"
        )
    report_path = out_dir / "metaqa_real_adapter_coverage_report.md"
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")

    print(f"qtypes={complete_qtypes}/{len(schema.routes)}")
    print(f"questions={len(rows)}")
    print(f"exact={exact_count}/{len(rows)}")
    print(f"failures={dict(failure_counts)}")
    print(f"results={results_path}")
    print(f"summary={summary_path}")
    print(f"report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
