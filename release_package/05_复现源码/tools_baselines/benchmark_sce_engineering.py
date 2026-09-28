#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run a bounded concurrency benchmark for SCE-KGQA."""

from __future__ import annotations

import argparse
import importlib
import json
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BASELINE_DIR = ROOT / "tools/baselines"
if str(BASELINE_DIR) not in sys.path:
    sys.path.insert(0, str(BASELINE_DIR))

from common_io import read_csv_rows  # noqa: E402


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * fraction)] if ordered else 0.0


def run_question(module: Any, row: dict[str, str], corpus: Path, top_k: int) -> dict[str, Any]:
    start = time.perf_counter()
    try:
        result = module.answer(row.get("question", ""), row=row, corpus_path=corpus, top_k=top_k)
        return {
            "qid": row.get("question_id", ""),
            "status": "ok",
            "latency_ms": (time.perf_counter() - start) * 1000,
            "answer_empty": not bool(result.get("answer") or result.get("answer_text")),
        }
    except Exception as exc:
        return {
            "qid": row.get("question_id", ""),
            "status": "error",
            "latency_ms": (time.perf_counter() - start) * 1000,
            "answer_empty": True,
            "error": f"{type(exc).__name__}: {exc}",
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--workers", type=int, required=True, choices=[1, 4, 8, 16])
    parser.add_argument("--top-k", type=int, default=50)
    parser.add_argument(
        "--corpus",
        type=Path,
        default=ROOT / "experiments/baselines/corpus/merged_rag_corpus.jsonl",
    )
    args = parser.parse_args()
    if args.limit < 1 or args.limit > 100:
        raise SystemExit("--limit must be between 1 and 100")

    module = importlib.import_module("sce_kgqa_full")
    rows = read_csv_rows(args.dataset)[: args.limit]
    started = time.perf_counter()
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(run_question, module, row, args.corpus, args.top_k) for row in rows]
        for future in as_completed(futures):
            results.append(future.result())
    wall_seconds = time.perf_counter() - started
    latencies = [float(row["latency_ms"]) for row in results]
    errors = sum(row["status"] == "error" for row in results)
    report = {
        "dataset": str(args.dataset),
        "limit": args.limit,
        "workers": args.workers,
        "wall_seconds": wall_seconds,
        "qps": len(results) / wall_seconds if wall_seconds else 0,
        "mean_latency_ms": statistics.mean(latencies) if latencies else 0,
        "p50_latency_ms": percentile(latencies, 0.50),
        "p95_latency_ms": percentile(latencies, 0.95),
        "p99_latency_ms": percentile(latencies, 0.99),
        "error_rate": errors / len(results) if results else 0,
        "empty_answer_rate": sum(row["answer_empty"] for row in results) / len(results) if results else 0,
        "rows": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
