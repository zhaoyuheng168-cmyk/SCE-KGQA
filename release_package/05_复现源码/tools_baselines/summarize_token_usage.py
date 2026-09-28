#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Summarize LLM token usage recorded in baseline JSONL outputs."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()

    for path in args.paths:
        rows = read_jsonl(path)
        totals = defaultdict(int)
        statuses = Counter(str(row.get("status", "")) for row in rows)
        methods = Counter(str(row.get("method", "")) for row in rows)
        usage_rows = 0
        models = Counter()
        routes = Counter()
        final_routes = Counter()
        answer_sources = Counter()
        kag_used = 0

        for row in rows:
            raw = row.get("raw") or {}
            usage = raw.get("llm_usage") or {}
            if usage:
                usage_rows += 1
                totals["prompt_tokens"] += int(usage.get("prompt_tokens") or 0)
                totals["completion_tokens"] += int(usage.get("completion_tokens") or 0)
                totals["total_tokens"] += int(usage.get("total_tokens") or 0)
            if raw.get("llm_model"):
                models[str(raw.get("llm_model"))] += 1
            elif raw.get("llm_models") and isinstance(raw.get("llm_models"), dict):
                models.update({str(k): int(v) for k, v in raw.get("llm_models", {}).items()})
            if raw.get("route"):
                routes[str(raw.get("route"))] += 1
            if raw.get("final_route"):
                final_routes[str(raw.get("final_route"))] += 1
            if raw.get("answer_source"):
                answer_sources[str(raw.get("answer_source"))] += 1
            if raw.get("kag_used"):
                kag_used += 1

        avg_total = totals["total_tokens"] / usage_rows if usage_rows else 0.0
        print(json.dumps(
            {
                "path": str(path),
                "rows": len(rows),
                "method": methods.most_common(1)[0][0] if methods else "",
                "statuses": dict(statuses),
                "usage_rows": usage_rows,
                "prompt_tokens": totals["prompt_tokens"],
                "completion_tokens": totals["completion_tokens"],
                "total_tokens": totals["total_tokens"],
                "avg_total_tokens_per_usage_row": round(avg_total, 2),
                "models": dict(models),
                "kag_used_rows": kag_used,
                "routes_top10": dict(routes.most_common(10)),
                "final_routes_top10": dict(final_routes.most_common(10)),
                "answer_sources_top10": dict(answer_sources.most_common(10)),
            },
            ensure_ascii=False,
        ))


if __name__ == "__main__":
    main()
