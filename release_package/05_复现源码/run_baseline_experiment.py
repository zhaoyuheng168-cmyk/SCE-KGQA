#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run V1 comparison baselines with a unified JSONL output format."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASELINE_DIR = ROOT / "tools" / "baselines"
if str(BASELINE_DIR) not in sys.path:
    sys.path.insert(0, str(BASELINE_DIR))

from common_io import now_ms, read_csv_rows  # noqa: E402


METHODS = {
    "llm_only": "llm_only",
    "llm_kg_triples": "llm_kg_triples",
    "llm_retrieved_evidence": "llm_retrieved_evidence",
    "naive_bm25_rag": "naive_bm25_rag",
    "naive_vector_rag": "naive_vector_rag",
    "graph_only_kgqa": "graph_only_kgqa",
    "hybrid_rag": "hybrid_rag",
    "text_kg_rag": "text_kg_rag",
    "kg_context_rag": "kg_context_rag",
    "entity_linked_graphrag": "entity_linked_graphrag",
    "rule_based_kgqa": "rule_based_kgqa",
    "naive_graphrag_2hop": "naive_graphrag_2hop",
    "llamaindex_rag": "llamaindex_rag",
    "langchain_rag": "langchain_rag",
    "external_graphrag_style": "external_graphrag_style",
    "openspg_kag_reuse": "openspg_kag_reuse",
    "schema_router_no_evidence": "schema_router_no_evidence",
    "sce_kgqa_full": "sce_kgqa_full",
}


def load_env_defaults() -> None:
    os.environ.setdefault("GTF_NEO4J_URI", "bolt://127.0.0.1:7688")
    os.environ.setdefault("GTF_NEO4J_USER", "neo4j")
    os.environ.setdefault("GTF_NEO4J_PASSWORD", "CHANGE_ME")
    os.environ.setdefault("GTF_NEO4J_DATABASE", "neo4j")
    os.environ.setdefault("GTF_NAMESPACE", "GansuTechFinanceDevV1Enhance")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("GTF_ENABLE_EMBEDDING", "1")
    os.environ.setdefault("GTF_EMBEDDING_MODEL_NAME", "runtime_data/models/bge-small-zh-v1.5")


def default_corpus_for_method(method: str) -> Path:
    if method in {"llamaindex_rag", "langchain_rag"}:
        return ROOT / "experiments/baselines/corpus/evidence_corpus.jsonl"
    if method == "llm_kg_triples":
        return ROOT / "experiments/baselines/corpus/kg_triples_corpus.jsonl"
    if method == "llm_retrieved_evidence":
        return ROOT / "experiments/baselines/corpus/evidence_corpus.jsonl"
    return ROOT / "experiments/baselines/corpus/merged_rag_corpus.jsonl"


def run_one(method: str, module: Any, row: dict[str, str], corpus_path: Path, top_k: int, dataset_index: int) -> dict[str, Any]:
    qid = row.get("question_id", "")
    question = row.get("question", "")
    start = now_ms()
    base = {
        "qid": qid,
        "dataset_index": dataset_index,
        "question": question,
        "method": method,
        "protocol_version": "comparison_protocol_v2_20260607",
        "input_policy": "question_id_and_question_only",
        "answer": [],
        "answer_text": "",
        "evidence": [],
        "status": "ok",
        "latency_ms": 0,
        "error": None,
        "raw": {},
    }
    try:
        # Baselines may only see question-side fields. Gold labels, canonical
        # subjects, target types, categories, and refusal annotations remain
        # exclusively inside the evaluator.
        question_only_row = {"question_id": qid, "question": question}
        result = module.answer(question, row=question_only_row, corpus_path=corpus_path, top_k=top_k)
        base.update(result)
        if str(base.get("answer_text", "")).startswith("无法") or "无法从" in str(base.get("answer_text", "")):
            base["status"] = "refuse"
    except Exception as exc:
        base["status"] = "error"
        base["error"] = f"{type(exc).__name__}: {exc}"
        base["raw"] = {"traceback": traceback.format_exc(limit=5)}
    finally:
        base["latency_ms"] = now_ms() - start
    return base


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--method", required=True, choices=sorted(METHODS))
    parser.add_argument("--dataset", type=Path, default=ROOT / "experiments/baselines/datasets/gtf_kgqa_1300_formal.csv")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=0, help="0 means all rows")
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--workers", type=int, default=1, choices=range(1, 9))
    parser.add_argument("--error-retries", type=int, default=0, choices=range(0, 4))
    parser.add_argument("--resume", action="store_true", help="append missing rows when output JSONL already exists")
    parser.add_argument(
        "--retry-errors",
        action="store_true",
        help="when resuming, remove existing error rows and retry only those dataset indexes",
    )
    args = parser.parse_args()

    load_env_defaults()
    module = importlib.import_module(METHODS[args.method])
    corpus_path = args.corpus or default_corpus_for_method(args.method)
    rows = read_csv_rows(args.dataset)
    if args.limit > 0:
        rows = rows[: args.limit]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    completed_indexes: set[int] = set()
    legacy_completed_qids: set[str] = set()
    if args.resume and args.output.exists():
        retained_lines: list[str] = []
        removed_errors = 0
        with args.output.open("r", encoding="utf-8") as existing:
            for line in existing:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if args.retry_errors and item.get("status") == "error":
                    removed_errors += 1
                    continue
                retained_lines.append(json.dumps(item, ensure_ascii=False))
                raw_index = item.get("dataset_index")
                if isinstance(raw_index, int) and 1 <= raw_index <= len(rows):
                    completed_indexes.add(raw_index)
                else:
                    qid = str(item.get("qid") or "")
                    if qid:
                        legacy_completed_qids.add(qid)

        if legacy_completed_qids:
            for idx, row in enumerate(rows, 1):
                if row.get("question_id", "") in legacy_completed_qids:
                    completed_indexes.add(idx)

        if removed_errors:
            with args.output.open("w", encoding="utf-8") as cleaned:
                for line in retained_lines:
                    cleaned.write(line + "\n")
            print(f"[{args.method}] retry_errors removed_rows={removed_errors}", flush=True)

        print(
            f"[{args.method}] resume enabled, completed_rows={len(completed_indexes)}",
            flush=True,
        )

    pending = [(idx, row) for idx, row in enumerate(rows, 1) if idx not in completed_indexes]

    def execute(item: tuple[int, dict[str, str]]) -> tuple[int, dict[str, Any]]:
        idx, row = item
        started = now_ms()
        result: dict[str, Any] = {}
        for attempt in range(1, args.error_retries + 2):
            result = run_one(args.method, module, row, corpus_path, args.top_k, idx)
            if result.get("status") != "error":
                break
        result["latency_ms"] = now_ms() - started
        raw = result.get("raw")
        if not isinstance(raw, dict):
            raw = {}
            result["raw"] = raw
        raw["runner_attempts"] = attempt
        return idx, result

    mode = "a" if args.resume else "w"
    with args.output.open(mode, encoding="utf-8") as f:
        def write_result(idx: int, result: dict[str, Any]) -> None:
            nonlocal written
            print(f"[{args.method}] completed {idx}/{len(rows)} {result.get('qid', '')}", flush=True)
            f.write(json.dumps(result, ensure_ascii=False) + "\n")
            f.flush()
            written += 1

        # Initialize module-level retrieval/index caches before concurrent calls.
        if args.workers > 1 and pending:
            idx, result = execute(pending.pop(0))
            write_result(idx, result)

        if args.workers == 1:
            iterator = map(execute, pending)
        else:
            pool = ThreadPoolExecutor(max_workers=args.workers)
            futures = [pool.submit(execute, item) for item in pending]
            iterator = (future.result() for future in as_completed(futures))
        try:
            for idx, result in iterator:
                write_result(idx, result)
        finally:
            if args.workers != 1:
                pool.shutdown(wait=True)
    print(
        json.dumps(
            {
                "method": args.method,
                "rows": written + len(completed_indexes),
                "new_rows": written,
                "workers": args.workers,
                "error_retries": args.error_retries,
                "corpus": str(corpus_path),
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
