#!/usr/bin/env python3
"""Read-only failure audit for the bounded MetaQA coverage smoke."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Set


def load_jsonl(path: Path) -> List[dict]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def subject_role_evidence(raw_dir: Path):
    """Infer possible roles for entity strings from MetaQA relations."""

    source_roles = defaultdict(set)
    object_roles = defaultdict(set)
    relation_object_roles = {
        "starred_actors": "actor",
        "directed_by": "director",
        "written_by": "writer",
        "has_genre": "genre",
        "release_year": "year",
        "in_language": "language",
        "has_tags": "tag",
        "has_imdb_rating": "imdbrating",
        "has_imdb_votes": "imdbvotes",
    }
    with (raw_dir / "kb.txt").open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            parts = line.rstrip("\r\n").split("|")
            if len(parts) != 3:
                continue
            source, relation, target = parts
            source_roles[source].add("movie")
            role = relation_object_roles.get(relation)
            if role:
                object_roles[target].add(role)
    return source_roles, object_roles


def evidence_supports_answer(row: dict, answer: str) -> bool:
    predicted = row.get("predicted_answers", [])
    evidence_paths = row.get("evidence_paths", [])
    for index, predicted_answer in enumerate(predicted):
        if predicted_answer == answer and index < len(evidence_paths) and evidence_paths[index]:
            return True
    return False


def classify_row(row: dict, source_roles, object_roles):
    predicted = set(row.get("predicted_answers", []))
    gold = set(row.get("gold_answers", []))
    extra = sorted(predicted - gold)
    missing = sorted(gold - predicted)
    subject = row.get("subject", "")
    subject_roles = sorted(source_roles.get(subject, set()) | object_roles.get(subject, set()))
    expected_role = str(row.get("subject_type", "")).lower()

    categories = []
    if len(subject_roles) > 1:
        categories.append("ambiguous_subject_string_roles")
    if extra and all(evidence_supports_answer(row, answer) for answer in extra):
        categories.append("extra_answers_have_valid_graph_paths")
    if missing:
        categories.append("missing_gold_answers")
    if extra and not missing:
        categories.append("over_return_only")
    if extra and missing:
        categories.append("mixed_mismatch")
    if expected_role and subject_roles and expected_role not in subject_roles:
        categories.append("subject_role_not_supported_by_kb_inference")
    if not categories:
        categories.append("unclassified")

    return {
        "extra": extra,
        "missing": missing,
        "subject_roles": subject_roles,
        "categories": categories,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", required=True)
    parser.add_argument("--results", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--details", required=True)
    args = parser.parse_args()

    raw_dir = Path(args.raw_dir).resolve()
    results_path = Path(args.results).resolve()
    report_path = Path(args.report).resolve()
    details_path = Path(args.details).resolve()
    rows = load_jsonl(results_path)
    failures = [row for row in rows if not row.get("exact_match")]
    source_roles, object_roles = subject_role_evidence(raw_dir)

    audited = []
    category_counts = Counter()
    qtype_counts = Counter()
    hop_counts = Counter()
    extra_count = 0
    missing_count = 0
    for row in failures:
        audit = classify_row(row, source_roles, object_roles)
        record = dict(row)
        record["audit"] = audit
        audited.append(record)
        category_counts.update(audit["categories"])
        qtype_counts[row["qtype"]] += 1
        hop_counts[row["hop"]] += 1
        extra_count += len(audit["extra"])
        missing_count += len(audit["missing"])

    details_path.parent.mkdir(parents=True, exist_ok=True)
    with details_path.open("w", encoding="utf-8") as handle:
        for row in audited:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    ambiguous = [row for row in audited if "ambiguous_subject_string_roles" in row["audit"]["categories"]]
    graph_supported_extra = [
        row for row in audited if "extra_answers_have_valid_graph_paths" in row["audit"]["categories"]
    ]
    lines = [
        "# MetaQA Coverage Smoke Failure Audit",
        "",
        f"- Input results: `{results_path}`",
        f"- Total smoke questions: **{len(rows)}**",
        f"- Failed questions audited: **{len(failures)}**",
        f"- Total extra answers: **{extra_count}**",
        f"- Total missing answers: **{missing_count}**",
        f"- Failures with ambiguous subject-string roles: **{len(ambiguous)}**",
        f"- Failures whose extra answers all have graph evidence: **{len(graph_supported_extra)}**",
        "",
        "## Category Counts",
        "",
    ]
    for category, count in category_counts.most_common():
        lines.append(f"- `{category}`: {count}")

    lines.extend(["", "## Failures by Hop", "", "| Hop | Failures |", "|---:|---:|"])
    for hop, count in sorted(hop_counts.items()):
        lines.append(f"| {hop} | {count} |")

    lines.extend(
        ["", "## Failures by Qtype", "", "| Qtype | Failures |", "|---|---:|"]
    )
    for qtype, count in qtype_counts.most_common():
        lines.append(f"| `{qtype}` | {count} |")

    lines.extend(
        [
            "",
            "## Representative Failures",
            "",
            "| Hop | Qtype | Subject | Subject roles | Extra | Missing | Categories |",
            "|---:|---|---|---|---|---|---|",
        ]
    )
    for row in audited[:20]:
        audit = row["audit"]
        lines.append(
            f"| {row['hop']} | `{row['qtype']}` | {row.get('subject', '')} | "
            f"{' ; '.join(audit['subject_roles'])} | {' ; '.join(audit['extra'][:8])} | "
            f"{' ; '.join(audit['missing'][:8])} | {' ; '.join(audit['categories'])} |"
        )

    lines.extend(
        [
            "",
            "## Interpretation Guard",
            "",
            "- A graph-supported extra answer is not automatically a framework error.",
            "- It may indicate an ambiguous entity string, benchmark answer filtering, or a missing route constraint.",
            "- This audit does not modify predictions, raw data, routes, or the unified core.",
            "",
        ]
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"failures={len(failures)}")
    print(f"extra_answers={extra_count}")
    print(f"missing_answers={missing_count}")
    print(f"ambiguous_subject_failures={len(ambiguous)}")
    print(f"graph_supported_extra_failures={len(graph_supported_extra)}")
    print(f"report={report_path}")
    print(f"details={details_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

