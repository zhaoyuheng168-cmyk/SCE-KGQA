#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Summarize latency, reliability, token usage, and optional API cost."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * fraction)]


def summarize(path: Path, input_price: float, output_price: float) -> dict[str, Any]:
    rows = read_jsonl(path)
    latencies = [float(row["latency_ms"]) for row in rows if row.get("latency_ms") is not None]
    statuses = Counter(str(row.get("status", "")) for row in rows)
    prompt_tokens = completion_tokens = total_tokens = 0
    llm_call_rows = kag_used_rows = 0
    for row in rows:
        raw = row.get("raw") or {}
        usage = raw.get("llm_usage") or {}
        prompt_tokens += int(usage.get("prompt_tokens") or 0)
        completion_tokens += int(usage.get("completion_tokens") or 0)
        total_tokens += int(usage.get("total_tokens") or 0)
        llm_call_rows += int(int(raw.get("llm_call_count") or 0) > 0)
        kag_used_rows += int(bool(raw.get("kag_used")))
    estimated_cost = prompt_tokens / 1_000_000 * input_price + completion_tokens / 1_000_000 * output_price
    errors = statuses.get("error", 0)
    return {
        "method": rows[0].get("method", path.stem) if rows else path.stem,
        "path": str(path),
        "rows": len(rows),
        "mean_latency_ms": statistics.mean(latencies) if latencies else 0,
        "median_latency_ms": percentile(latencies, 0.50),
        "p95_latency_ms": percentile(latencies, 0.95),
        "p99_latency_ms": percentile(latencies, 0.99),
        "statuses": dict(statuses),
        "error_rate": errors / len(rows) if rows else 0,
        "successful_execution_rate": (len(rows) - errors) / len(rows) if rows else 0,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "avg_tokens_per_question": total_tokens / len(rows) if rows else 0,
        "llm_call_rows": llm_call_rows,
        "kag_used_rows": kag_used_rows,
        "input_price_per_million_tokens": input_price,
        "output_price_per_million_tokens": output_price,
        "estimated_api_cost": estimated_cost,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--input-price-per-million", type=float, default=0.0)
    parser.add_argument("--output-price-per-million", type=float, default=0.0)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    rows = [
        summarize(path, args.input_price_per_million, args.output_price_per_million)
        for path in args.paths
    ]
    (args.output_dir / "engineering_metrics.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# Engineering Metrics",
        "",
        "API cost remains zero unless token prices are explicitly supplied.",
        "",
        "| Method | Rows | Mean Latency | P95 | P99 | Error Rate | Tokens/Q | Estimated Cost |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['method']} | {row['rows']} | {row['mean_latency_ms']:.0f} ms | "
            f"{row['p95_latency_ms']:.0f} ms | {row['p99_latency_ms']:.0f} ms | "
            f"{row['error_rate']:.2%} | {row['avg_tokens_per_question']:.2f} | "
            f"{row['estimated_api_cost']:.6f} |"
        )
    (args.output_dir / "engineering_metrics.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(args.output_dir / "engineering_metrics.json")


if __name__ == "__main__":
    main()
