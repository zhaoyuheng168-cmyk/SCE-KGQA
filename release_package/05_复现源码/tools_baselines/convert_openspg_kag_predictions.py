#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Convert OpenSPG-KAG answer exports to the common baseline JSONL format."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any


SEP_RE = re.compile(r"\|\||[；;，,\n\r、]+")


def split_items(value: object) -> list[str]:
    text = "" if value is None else str(value)
    items: list[str] = []
    for part in SEP_RE.split(text):
        item = part.strip().strip("。；;，,、 ")
        if item and item not in items:
            items.append(item)
    return items


def read_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        return rows
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [dict(row) for row in data]
        if isinstance(data, dict) and isinstance(data.get("data"), list):
            return [dict(row) for row in data["data"]]
        raise ValueError("JSON input must be a list or an object with a data list")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def first_value(row: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return ""


def looks_like_refusal(text: str) -> bool:
    markers = ["无法", "不能", "拒绝回答", "拒答", "超出可回答范围", "不知道"]
    return any(marker in text for marker in markers)


def convert_row(row: dict[str, Any]) -> dict[str, Any]:
    qid = str(first_value(row, ["qid", "id", "question_id", "query_id"]))
    question = str(first_value(row, ["question", "query", "input"]))
    answer_obj = first_value(row, ["answer", "answers", "answer_text", "response", "output", "result"])
    if isinstance(answer_obj, list):
        answer_items = [str(x) for x in answer_obj if str(x).strip()]
        answer_text = "||".join(answer_items)
    else:
        answer_text = str(answer_obj or "")
        answer_items = split_items(answer_text)
    evidence = first_value(row, ["evidence", "references", "retrieved", "context"])
    status = str(first_value(row, ["status"])) or "ok"
    if status == "ok" and looks_like_refusal(answer_text):
        status = "refuse"
    return {
        "qid": qid,
        "question": question,
        "method": "openspg_kag",
        "answer": answer_items,
        "answer_text": answer_text,
        "evidence": evidence if isinstance(evidence, list) else [],
        "status": status,
        "latency_ms": int(float(first_value(row, ["latency_ms", "latency", "cost_ms"]) or 0)),
        "error": first_value(row, ["error"]) or None,
        "raw": row,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rows = [convert_row(row) for row in read_rows(args.input)]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps({"rows": len(rows), "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
