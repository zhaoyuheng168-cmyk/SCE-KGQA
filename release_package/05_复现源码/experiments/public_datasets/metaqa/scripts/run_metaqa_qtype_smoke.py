#!/usr/bin/env python3
"""Execute a bounded real-MetaQA qtype smoke using generated typed paths."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import DefaultDict, Dict, List, Tuple

from metaqa_schema_mapping import parse_qtype_path


SUBJECT_PATTERN = re.compile(r"\[([^\]]+)\]")
MAX_LIMIT = 10


def unique(values: List[str]) -> List[str]:
    return list(dict.fromkeys(values))


def build_indexes(kb_path: Path):
    forward: DefaultDict[Tuple[str, str], List[Tuple[str, dict]]] = defaultdict(list)
    reverse: DefaultDict[Tuple[str, str], List[Tuple[str, dict]]] = defaultdict(list)
    malformed = 0
    with kb_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            text = line.rstrip("\r\n")
            parts = text.split("|")
            if len(parts) != 3:
                malformed += 1
                continue
            source, relation, target = parts
            triple = {"source": source, "relation": relation, "target": target}
            forward[(source, relation)].append((target, triple))
            reverse[(target, relation)].append((source, triple))
    return forward, reverse, malformed


def execute_path(
    subject: str,
    steps: List[dict],
    forward: Dict[Tuple[str, str], List[Tuple[str, dict]]],
    reverse: Dict[Tuple[str, str], List[Tuple[str, dict]]],
    exclude_start_at_steps,
):
    frontier: List[Tuple[str, List[dict]]] = [(subject, [])]
    step_frontier_sizes = []
    excluded_revisit_counts = []
    for step_number, step in enumerate(steps, start=1):
        next_frontier: List[Tuple[str, List[dict]]] = []
        excluded_revisits = 0
        index = reverse if step["direction"] == "in" else forward
        for node, evidence in frontier:
            for next_node, triple in index.get((node, step["relation"]), []):
                if step_number in exclude_start_at_steps and next_node == subject:
                    excluded_revisits += 1
                    continue
                next_frontier.append((next_node, evidence + [triple]))
        frontier = next_frontier
        step_frontier_sizes.append(len(frontier))
        excluded_revisit_counts.append(excluded_revisits)
        if not frontier:
            break

    answers: List[str] = []
    evidence_by_answer: Dict[str, List[List[dict]]] = defaultdict(list)
    for answer, evidence in frontier:
        if answer == subject:
            continue
        if answer not in answers:
            answers.append(answer)
        evidence_by_answer[answer].append(evidence)
    return answers, evidence_by_answer, step_frontier_sizes, excluded_revisit_counts


def parse_step_numbers(value: str):
    if not str(value or "").strip():
        return set()
    steps = set()
    for part in str(value).split(","):
        number = int(part.strip())
        if number <= 0:
            raise ValueError("step numbers must be positive and 1-based")
        steps.add(number)
    return steps


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", required=True)
    parser.add_argument("--hop", type=int, choices=(1, 2, 3), required=True)
    parser.add_argument("--split", choices=("train", "dev", "test"), default="test")
    parser.add_argument("--qtype", required=True)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument(
        "--exclude-start-at-steps",
        default="",
        help="Comma-separated 1-based path steps where revisiting the start entity is excluded.",
    )
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    if args.limit <= 0 or args.limit > MAX_LIMIT:
        parser.error(f"--limit must be between 1 and {MAX_LIMIT}")

    steps = parse_qtype_path(args.qtype)
    if len(steps) != args.hop:
        parser.error(f"qtype generates {len(steps)} steps, but --hop is {args.hop}")
    try:
        exclude_start_at_steps = parse_step_numbers(args.exclude_start_at_steps)
    except ValueError as exc:
        parser.error(str(exc))
    invalid_constraint_steps = sorted(step for step in exclude_start_at_steps if step > len(steps))
    if invalid_constraint_steps:
        parser.error(
            f"--exclude-start-at-steps contains steps beyond path length: {invalid_constraint_steps}"
        )

    raw_dir = Path(args.raw_dir).resolve()
    out_dir = Path(args.out_dir).resolve()
    forward, reverse, malformed_kb = build_indexes(raw_dir / "kb.txt")
    qa_path = raw_dir / f"{args.hop}-hop/vanilla/qa_{args.split}.txt"
    qtype_path = raw_dir / f"{args.hop}-hop/qa_{args.split}_qtype.txt"

    rows = []
    with qa_path.open("r", encoding="utf-8", errors="replace") as qa_handle, qtype_path.open(
        "r", encoding="utf-8", errors="replace"
    ) as qtype_handle:
        for source_index, (qa_line, qtype_line) in enumerate(zip(qa_handle, qtype_handle)):
            if qtype_line.strip() != args.qtype:
                continue
            raw_qa = qa_line.rstrip("\r\n")
            if "\t" not in raw_qa:
                rows.append(
                    {
                        "source_index": source_index,
                        "qtype": args.qtype,
                        "failure": "malformed_qa_missing_tab",
                    }
                )
                continue
            question, gold_text = raw_qa.split("\t", 1)
            match = SUBJECT_PATTERN.search(question)
            if not match:
                rows.append(
                    {
                        "source_index": source_index,
                        "qtype": args.qtype,
                        "question": question,
                        "failure": "subject_not_found",
                    }
                )
                continue
            subject = match.group(1)
            predicted, evidence_by_answer, frontier_sizes, excluded_revisit_counts = execute_path(
                subject, steps, forward, reverse, exclude_start_at_steps
            )
            gold = [item.strip() for item in gold_text.split("|") if item.strip()]
            exact = set(predicted) == set(gold)
            rows.append(
                {
                    "qid": (
                        f"metaqa_{args.hop}hop_{args.split}_{args.qtype}_{source_index:06d}"
                    ),
                    "source_index": source_index,
                    "hop": args.hop,
                    "split": args.split,
                    "qtype": args.qtype,
                    "question": question,
                    "subject": subject,
                    "typed_path": steps,
                    "path_constraints": {
                        "exclude_start_at_steps": sorted(exclude_start_at_steps),
                    },
                    "step_frontier_sizes": frontier_sizes,
                    "excluded_start_revisit_counts": excluded_revisit_counts,
                    "predicted_answers": predicted,
                    "gold_answers": gold,
                    "exact_match": exact,
                    "evidence_paths_by_answer": evidence_by_answer,
                    "failure": "" if exact else "answer_set_mismatch",
                }
            )
            if len(rows) >= args.limit:
                break

    failure_counts = Counter(row.get("failure", "") or "none" for row in rows)
    exact_count = sum(1 for row in rows if row.get("exact_match") is True)
    out_dir.mkdir(parents=True, exist_ok=True)
    result_path = out_dir / f"{args.qtype}_{args.limit}_results.jsonl"
    with result_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    report = [
        f"# MetaQA {args.qtype} {args.limit}-Question Execution Smoke",
        "",
        f"- Hop: **{args.hop}**",
        f"- Split: **{args.split}**",
        f"- Questions executed: **{len(rows)}**",
        f"- Exact matches: **{exact_count}/{len(rows)}**",
        f"- KB malformed lines observed: **{malformed_kb}**",
        f"- Typed path: `{json.dumps(steps, ensure_ascii=False)}`",
        f"- Exclude start at steps: **{sorted(exclude_start_at_steps)}**",
        f"- Conclusion: **{'PASS' if len(rows) == args.limit and exact_count == len(rows) else 'FAIL'}**",
        "",
        "## Failure Counts",
        "",
    ]
    for failure, count in sorted(failure_counts.items()):
        report.append(f"- `{failure}`: {count}")
    report.extend(
        [
            "",
            "| QID | Subject | Frontier sizes | Excluded revisits | Predicted count | Gold count | Exact | Failure |",
            "|---|---|---|---|---:|---:|---:|---|",
        ]
    )
    for row in rows:
        report.append(
            f"| `{row.get('qid', '-')}` | {row.get('subject', '-')} | "
            f"{row.get('step_frontier_sizes', [])} | "
            f"{row.get('excluded_start_revisit_counts', [])} | "
            f"{len(row.get('predicted_answers', []))} | {len(row.get('gold_answers', []))} | "
            f"{row.get('exact_match', False)} | {row.get('failure', '')} |"
        )
    report_path = out_dir / f"{args.qtype}_{args.limit}_report.md"
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")

    print(f"questions={len(rows)}")
    print(f"exact={exact_count}/{len(rows)}")
    print(f"failures={dict(failure_counts)}")
    print(f"result={result_path}")
    print(f"report={report_path}")
    return 0 if len(rows) == args.limit and exact_count == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
