#!/usr/bin/env python3
"""Read-only audit of the original MetaQA text dataset."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple


HOPS = (1, 2, 3)
SPLITS = ("train", "dev", "test")


def required_paths() -> List[str]:
    paths = ["kb.txt"]
    for hop in HOPS:
        for split in SPLITS:
            paths.append(f"{hop}-hop/qa_{split}_qtype.txt")
            paths.append(f"{hop}-hop/vanilla/qa_{split}.txt")
    return paths


def count_lines(path: Path) -> int:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return sum(1 for _ in handle)


def parse_qa_line(line: str) -> Tuple[str, List[str], Optional[str]]:
    text = line.rstrip("\r\n")
    if "\t" not in text:
        return text, [], "missing_tab"
    question, answer_text = text.split("\t", 1)
    answers = [answer.strip() for answer in answer_text.split("|") if answer.strip()]
    warning = "empty_answer" if not answers else None
    return question, answers, warning


def sample_aligned(qa_path: Path, qtype_path: Path, limit: int = 5):
    samples = []
    with qa_path.open("r", encoding="utf-8", errors="replace") as qa_handle:
        qa_lines = [next(qa_handle, "") for _ in range(limit)]
    with qtype_path.open("r", encoding="utf-8", errors="replace") as qtype_handle:
        qtype_lines = [next(qtype_handle, "") for _ in range(limit)]
    for index, (qa_line, qtype_line) in enumerate(zip(qa_lines, qtype_lines), start=1):
        question, answers, warning = parse_qa_line(qa_line)
        samples.append(
            {
                "line": index,
                "question": question,
                "answers": answers,
                "qtype": qtype_line.rstrip("\r\n"),
                "warning": warning or "",
                "raw": qa_line.rstrip("\r\n"),
            }
        )
    return samples


def escape_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()

    raw_dir = Path(args.raw_dir).resolve()
    report_path = Path(args.report).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)

    existence: Dict[str, bool] = {}
    line_counts: Dict[str, int] = {}
    anomalies: List[str] = []
    for relative in required_paths():
        path = raw_dir / relative
        existence[relative] = path.is_file()
        if path.is_file():
            line_counts[relative] = count_lines(path)
        else:
            anomalies.append(f"Missing required file: {relative}")

    alignments = []
    aligned_ok = True
    for hop in HOPS:
        for split in SPLITS:
            qtype_rel = f"{hop}-hop/qa_{split}_qtype.txt"
            qa_rel = f"{hop}-hop/vanilla/qa_{split}.txt"
            qtype_count = line_counts.get(qtype_rel)
            qa_count = line_counts.get(qa_rel)
            match = qtype_count is not None and qa_count is not None and qtype_count == qa_count
            aligned_ok = aligned_ok and match
            alignments.append((hop, split, qtype_count, qa_count, match))
            if not match:
                anomalies.append(
                    f"Line-count mismatch: {qtype_rel}={qtype_count}, {qa_rel}={qa_count}"
                )

    kb_path = raw_dir / "kb.txt"
    relation_counts: Counter[str] = Counter()
    subjects = set()
    objects = set()
    malformed_kb = 0
    total_kb = 0
    if kb_path.is_file():
        with kb_path.open("r", encoding="utf-8", errors="replace") as handle:
            for lineno, line in enumerate(handle, start=1):
                total_kb += 1
                text = line.rstrip("\r\n")
                parts = text.split("|")
                if len(parts) != 3 or not all(part.strip() for part in parts):
                    malformed_kb += 1
                    if len(anomalies) < 20:
                        anomalies.append(f"Malformed kb.txt line {lineno}: {text}")
                    continue
                subject, relation, obj = parts
                subjects.add(subject)
                objects.add(obj)
                relation_counts[relation] += 1

    qa_samples = {}
    for hop in HOPS:
        for split in SPLITS:
            qa_path = raw_dir / f"{hop}-hop/vanilla/qa_{split}.txt"
            qtype_path = raw_dir / f"{hop}-hop/qa_{split}_qtype.txt"
            if qa_path.is_file() and qtype_path.is_file():
                samples = sample_aligned(qa_path, qtype_path)
                qa_samples[(hop, split)] = samples
                for sample in samples:
                    if sample["warning"] and len(anomalies) < 20:
                        anomalies.append(
                            f"QA warning {hop}-hop/{split} line {sample['line']}: "
                            f"{sample['warning']} | {sample['raw']}"
                        )

    complete = all(existence.values())
    kb_ok = kb_path.is_file() and malformed_kb == 0 and total_kb == 134741
    passed = complete and aligned_ok and kb_ok

    lines = [
        "# MetaQA Raw Data Audit Report",
        "",
        f"- Raw directory: `{raw_dir}`",
        f"- Required files present: **{sum(existence.values())}/{len(existence)}**",
        f"- Audit conclusion: **{'PASS' if passed else 'FAIL'}**",
        "",
        "## File Existence",
        "",
        "| File | Exists | Lines |",
        "|---|---:|---:|",
    ]
    for relative in required_paths():
        lines.append(
            f"| `{escape_cell(relative)}` | {'yes' if existence[relative] else 'no'} | "
            f"{line_counts.get(relative, '-')} |"
        )

    lines.extend(
        [
            "",
            "## Qtype / QA Alignment",
            "",
            "| Hop | Split | Qtype lines | QA lines | Match |",
            "|---:|---|---:|---:|---:|",
        ]
    )
    for hop, split, qtype_count, qa_count, match in alignments:
        lines.append(f"| {hop} | {split} | {qtype_count} | {qa_count} | {'yes' if match else 'no'} |")

    lines.extend(
        [
            "",
            "## Knowledge Base Parse Check",
            "",
            f"- Total lines / triples: **{total_kb}**",
            f"- Expected total lines: **134741**",
            f"- Malformed lines: **{malformed_kb}**",
            f"- Distinct subjects: **{len(subjects)}**",
            f"- Distinct objects: **{len(objects)}**",
            f"- Distinct entities: **{len(subjects | objects)}**",
            f"- Distinct relations: **{len(relation_counts)}**",
            "",
            "### Top 20 Relations",
            "",
            "| Relation | Count |",
            "|---|---:|",
        ]
    )
    for relation, count in relation_counts.most_common(20):
        lines.append(f"| `{escape_cell(relation)}` | {count} |")

    lines.extend(["", "## QA Format Samples", ""])
    for (hop, split), samples in qa_samples.items():
        lines.extend(
            [
                f"### {hop}-hop / {split}",
                "",
                "| Line | Qtype | Question | Answers | Warning |",
                "|---:|---|---|---|---|",
            ]
        )
        for sample in samples:
            answers = " || ".join(sample["answers"])
            lines.append(
                f"| {sample['line']} | {escape_cell(sample['qtype'])} | "
                f"{escape_cell(sample['question'])} | {escape_cell(answers)} | "
                f"{escape_cell(sample['warning'])} |"
            )
        lines.append("")

    lines.extend(["## Anomalies (Maximum 20)", ""])
    if anomalies:
        for anomaly in anomalies[:20]:
            lines.append(f"- {anomaly}")
    else:
        lines.append("- None detected.")
    lines.extend(
        [
            "",
            "## Conclusion",
            "",
            f"Audit result: **{'PASS' if passed else 'FAIL'}**.",
            f"All 19 files present: **{'yes' if complete else 'no'}**.",
            f"All qtype/QA line counts aligned: **{'yes' if aligned_ok else 'no'}**.",
            f"`kb.txt` malformed lines: **{malformed_kb}**.",
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"report={report_path}")
    print(f"pass={passed}")
    print(f"required_files={sum(existence.values())}/{len(existence)}")
    print(f"kb_lines={total_kb}")
    print(f"kb_malformed={malformed_kb}")
    print(f"aligned={aligned_ok}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

