# -*- coding: utf-8 -*-
"""Convert MetaQA-style QA files into the framework eval TSV format.

Supported input variants:

1. question<TAB>answer1|answer2
2. question<TAB>answer1<TAB>answer2|answer3
3. qid<TAB>question<TAB>subject<TAB>subject_type<TAB>answer1|answer2

When subject and subject_type are absent, this script extracts the entity inside
square brackets, e.g. "who acted in [Titanic]?", and uses --default-subject-type.
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import List, Sequence


ENTITY_PATTERN = re.compile(r"\[([^\]]+)\]")


def _split_answers(value: str) -> List[str]:
    normalized = str(value or "").replace(";", "|").replace("||", "|")
    return [item.strip() for item in normalized.split("|") if item.strip()]


def _extract_subject(question: str) -> str:
    match = ENTITY_PATTERN.search(str(question or ""))
    return match.group(1).strip() if match else ""


def _clean_question(question: str) -> str:
    return ENTITY_PATTERN.sub(lambda m: m.group(1), str(question or "")).strip()


def convert_row(
    parts: Sequence[str],
    *,
    index: int,
    default_subject_type: str,
) -> List[str]:
    cols = [str(part or "").strip() for part in parts]
    if len(cols) >= 5:
        qid, question, subject, subject_type, answers = cols[0], cols[1], cols[2], cols[3], cols[4]
    elif len(cols) >= 3:
        qid = str(index)
        question, subject, answers = cols[0], cols[1], cols[2]
        subject_type = default_subject_type
    elif len(cols) == 2:
        qid = str(index)
        question, answers = cols
        subject = _extract_subject(question)
        subject_type = default_subject_type
    else:
        raise ValueError(f"Expected at least 2 columns, got {len(cols)}")

    clean_question = _clean_question(question)
    gold_answers = "||".join(_split_answers(answers))
    return [qid or str(index), clean_question, subject, subject_type, gold_answers]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--default-subject-type", default="Movie")
    parser.add_argument("--delimiter", default="\t")
    args = parser.parse_args()

    source = Path(args.input)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for idx, line in enumerate(source.read_text(encoding="utf-8").splitlines(), start=1):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        parts = text.split(args.delimiter)
        try:
            rows.append(convert_row(parts, index=idx, default_subject_type=args.default_subject_type))
        except ValueError as exc:
            raise ValueError(f"{source}:{idx}: {exc}") from exc

    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["qid", "question", "subject", "subject_type", "gold_answers"])
        writer.writerows(rows)

    print(f"converted={len(rows)}")
    print(f"output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

