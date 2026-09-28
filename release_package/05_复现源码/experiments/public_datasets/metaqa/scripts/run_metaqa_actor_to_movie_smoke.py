#!/usr/bin/env python3
"""Execute exactly ten actor_to_movie MetaQA test questions over raw kb.txt."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path


SUBJECT_PATTERN = re.compile(r"\[([^\]]+)\]")
QTYPE = "actor_to_movie"
RELATION = "starred_actors"
LIMIT = 10


def answer_set(text: str):
    return {item.strip() for item in text.split("|") if item.strip()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    raw_dir = Path(args.raw_dir).resolve()
    out_dir = Path(args.out_dir).resolve()
    reverse_index = defaultdict(list)
    malformed_kb = 0
    with (raw_dir / "kb.txt").open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            parts = line.rstrip("\r\n").split("|")
            if len(parts) != 3:
                malformed_kb += 1
                continue
            movie, relation, obj = parts
            if relation == RELATION:
                reverse_index[obj].append(movie)

    qa_path = raw_dir / "1-hop/vanilla/qa_test.txt"
    qtype_path = raw_dir / "1-hop/qa_test_qtype.txt"
    rows = []
    with qa_path.open("r", encoding="utf-8", errors="replace") as qa_handle, qtype_path.open(
        "r", encoding="utf-8", errors="replace"
    ) as qtype_handle:
        for source_index, (qa_line, qtype_line) in enumerate(zip(qa_handle, qtype_handle)):
            if qtype_line.strip() != QTYPE:
                continue
            raw_qa = qa_line.rstrip("\r\n")
            if "\t" not in raw_qa:
                rows.append({"source_index": source_index, "failure": "malformed_qa_missing_tab"})
                continue
            question, gold_text = raw_qa.split("\t", 1)
            match = SUBJECT_PATTERN.search(question)
            if not match:
                rows.append({"source_index": source_index, "question": question, "failure": "subject_not_found"})
                continue
            subject = match.group(1)
            predicted = list(dict.fromkeys(reverse_index.get(subject, [])))
            gold = [item.strip() for item in gold_text.split("|") if item.strip()]
            exact = set(predicted) == set(gold)
            evidence = [
                {"source": movie, "relation": RELATION, "target": subject}
                for movie in predicted
            ]
            rows.append(
                {
                    "qid": f"metaqa_1hop_test_actor_to_movie_{source_index:06d}",
                    "source_index": source_index,
                    "qtype": QTYPE,
                    "question": question,
                    "subject": subject,
                    "typed_path": [
                        {
                            "source_role": "actor",
                            "relation": RELATION,
                            "target_role": "movie",
                            "direction": "in",
                        }
                    ],
                    "predicted_answers": predicted,
                    "gold_answers": gold,
                    "exact_match": exact,
                    "evidence_paths": evidence,
                    "failure": "" if exact else "answer_set_mismatch",
                }
            )
            if len(rows) >= LIMIT:
                break

    out_dir.mkdir(parents=True, exist_ok=True)
    result_path = out_dir / "actor_to_movie_10_results.jsonl"
    with result_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    passed = sum(1 for row in rows if row.get("exact_match") is True)
    failures = [row for row in rows if row.get("exact_match") is not True]
    report = [
        "# MetaQA actor_to_movie 10-Question Execution Smoke",
        "",
        f"- Questions executed: **{len(rows)}**",
        f"- Exact matches: **{passed}/{len(rows)}**",
        f"- KB malformed lines observed: **{malformed_kb}**",
        f"- Conclusion: **{'PASS' if len(rows) == LIMIT and not failures else 'FAIL'}**",
        "",
        "| QID | Subject | Predicted | Gold | Exact | Failure |",
        "|---|---|---|---|---:|---|",
    ]
    for row in rows:
        report.append(
            f"| `{row.get('qid', '-')}` | {row.get('subject', '-')} | "
            f"{' ; '.join(row.get('predicted_answers', []))} | "
            f"{' ; '.join(row.get('gold_answers', []))} | "
            f"{row.get('exact_match', False)} | {row.get('failure', '')} |"
        )
    report_path = out_dir / "actor_to_movie_10_report.md"
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")

    print(f"questions={len(rows)}")
    print(f"exact={passed}/{len(rows)}")
    print(f"result={result_path}")
    print(f"report={report_path}")
    return 0 if len(rows) == LIMIT and not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())

