#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check strong baseline JSONL/CSV outputs for completeness and anomalies."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


def inspect_jsonl(path: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    bad_json = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            bad_json += 1
    qids = [str(row.get("qid") or "") for row in rows]
    statuses = Counter(str(row.get("status") or "") for row in rows)
    methods = Counter(str(row.get("method") or "") for row in rows)
    protocols = Counter(str(row.get("protocol_version") or "") for row in rows)
    models: Counter[str] = Counter()
    for row in rows:
        raw = row.get("raw") or {}
        if raw.get("llm_model"):
            models[str(raw["llm_model"])] += 1
        for model, count in (raw.get("llm_models") or {}).items():
            models[str(model)] += int(count)
    return {
        "path": str(path),
        "format": "jsonl",
        "rows": len(rows),
        "unique_question_ids": len(set(qids)),
        "duplicates": len(qids) - len(set(qids)),
        "returncode_nonzero": statuses.get("error", 0) + bad_json,
        "empty_prediction": sum(1 for row in rows if not row.get("answer") and not str(row.get("answer_text") or "").strip()),
        "refuse": statuses.get("refuse", 0),
        "statuses": dict(statuses),
        "methods": dict(methods),
        "protocols": dict(protocols),
        "models": dict(models),
        "bad_json": bad_json,
    }


def inspect_csv(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    qids = [str(row.get("question_id") or "") for row in rows]
    returncodes = [str(row.get("returncode") or "0") for row in rows]
    return {
        "path": str(path),
        "format": "csv",
        "rows": len(rows),
        "unique_question_ids": len(set(qids)),
        "duplicates": len(qids) - len(set(qids)),
        "returncode_nonzero": sum(1 for value in returncodes if value not in {"", "0"}),
        "empty_prediction": sum(1 for row in rows if not str(row.get("prediction") or "").strip()),
        "refuse": sum(1 for row in rows if "无法" in str(row.get("raw_answer") or "")),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-rows", type=int, default=0)
    parser.add_argument("--expected-protocol", default="")
    parser.add_argument("--expected-model", default="")
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()
    failed = False
    for path in args.paths:
        if not path.exists():
            report = {"path": str(path), "missing": True}
        elif path.suffix.lower() == ".csv":
            report = inspect_csv(path)
        else:
            report = inspect_jsonl(path)
        print(json.dumps(report, ensure_ascii=False))
        if report.get("missing") or report.get("duplicates", 0) or report.get("returncode_nonzero", 0):
            failed = True
        if args.expected_rows and (
            report.get("rows") != args.expected_rows
            or report.get("unique_question_ids") != args.expected_rows
        ):
            failed = True
        if args.expected_protocol and report.get("format") == "jsonl":
            if set(report.get("protocols", {})) != {args.expected_protocol}:
                failed = True
        if args.expected_model and report.get("format") == "jsonl":
            models = set(report.get("models", {}))
            if models and models != {args.expected_model}:
                failed = True
    if failed:
        raise SystemExit("Baseline output gate failed")


if __name__ == "__main__":
    main()
