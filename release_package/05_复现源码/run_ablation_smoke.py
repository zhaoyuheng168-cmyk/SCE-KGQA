#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run small ablation smoke checks and capture route-level diagnostics."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Iterable, List


ROOT = Path(__file__).resolve().parents[1]
ANSWER_SCRIPT = ROOT / "app/retrieval_only/scripts/answer_hybrid_v8_graph_kag_fallback.py"
DEFAULT_EMBEDDING_MODEL = ROOT / "runtime_data/models/bge-small-zh-v1.5"


FULL_SYSTEM_FLAGS: Dict[str, str] = {
    "GTF_ENABLE_V7_FALLBACK": "0",
    "GTF_ENABLE_KAG_FALLBACK": "1",
    "GTF_ENABLE_GENERIC_RELATION_FALLBACK": "1",
    "GTF_ENABLE_REVERSE_RELATION": "1",
    "GTF_ENABLE_MULTIHOP_REASONING": "1",
    "GTF_ENABLE_V8_KAG_MULTIHOP_PLANNER": "1",
    "GTF_ENABLE_SCHEMA_MULTIHOP_ROUTER": "1",
    "GTF_ENABLE_V8_MULTIHOP_SAFETY_GATE": "1",
    "GTF_ENABLE_SCOPE_GATE_V2": "1",
    "GTF_ENABLE_SCOPE_LLM_GATE": "1",
    "GTF_ENABLE_REFUSAL_OUTPUT": "1",
    "GTF_ENABLE_LLM_ASSISTED_DECISION": "1",
    "GTF_ENABLE_LLM_RESPONSE_CACHE": "1",
    "GTF_LLM_RESPONSE_CACHE_DIR": str(ROOT / "app/retrieval_only/results/llm_response_cache"),
    "GTF_SCOPE_GATE_CACHE_PATH": str(ROOT / "app/retrieval_only/results/scope_gate_cache.json"),
    "GTF_ENABLE_EMBEDDING": "1",
    "GTF_ENABLE_EMBEDDING_EVIDENCE": "1",
    "GTF_ENABLE_ENTITY_EMBEDDING_GROUNDING": "1",
    "GTF_ENABLE_TRUE_ENTITY_GROUNDING": "1",
    "GTF_ENABLE_EMBEDDING_ENTITY_CANDIDATES": "1",
    "GTF_ENABLE_EMBEDDING_RELATION_FALLBACK": "1",
    "GTF_ENABLE_EMBEDDING_ANSWER_RERANK": "1",
    "GTF_EMBEDDING_MODEL_NAME": str(DEFAULT_EMBEDDING_MODEL),
    "GTF_ENTITY_GROUNDING_MIN_SCORE": "0.58",
    "GTF_ENTITY_GROUNDING_MIN_MARGIN": "0.03",
    "GTF_ENTITY_GROUNDING_ONLY_WHEN_WEAK_ROUTE": "1",
    "GTF_ENTITY_EMBEDDING_TOP_K": "10",
    "GTF_ENTITY_EMBEDDING_MIN_SCORE": "0.70",
    "GTF_EMBEDDING_EVIDENCE_TOP_K": "5",
    "GTF_EMBEDDING_EVIDENCE_MIN_SCORE": "0.65",
    "TOKENIZERS_PARALLELISM": "false",
    "TRANSFORMERS_OFFLINE": "1",
    "OMP_NUM_THREADS": "1",
}


VERSIONS: Dict[str, Dict[str, str]] = {
    "full_system": {},
    "without_evidence_aware_retrieval": {
        "GTF_ENABLE_KAG_FALLBACK": "0",
        "GTF_ENABLE_EMBEDDING_EVIDENCE": "0",
    },
    "without_multihop_planner": {
        "GTF_ENABLE_SCHEMA_MULTIHOP_ROUTER": "0",
        "GTF_ENABLE_V8_KAG_MULTIHOP_PLANNER": "0",
        "GTF_ENABLE_V8_MULTIHOP_SAFETY_GATE": "0",
    },
    "without_multihop_reasoning": {
        "GTF_ENABLE_MULTIHOP_REASONING": "0",
        "GTF_ENABLE_SCHEMA_MULTIHOP_ROUTER": "0",
        "GTF_ENABLE_V8_KAG_MULTIHOP_PLANNER": "0",
        "GTF_ENABLE_V8_MULTIHOP_SAFETY_GATE": "0",
    },
    "without_open_relation_module": {"GTF_ENABLE_GENERIC_RELATION_FALLBACK": "0"},
    "without_schema_semantic_router": {"GTF_ENABLE_SCHEMA_SEMANTIC_ROUTER": "0"},
    "without_reverse_relation": {"GTF_ENABLE_REVERSE_RELATION": "0"},
    "without_rule_reasoning": {"GTF_ENABLE_RULE_REASONING": "0"},
    "without_refusal_gate": {
        "GTF_ENABLE_REFUSAL_GATE": "0",
        "GTF_ENABLE_SCOPE_GATE_V2": "0",
        "GTF_ENABLE_SCOPE_LLM_GATE": "0",
        "GTF_ENABLE_REFUSAL_OUTPUT": "0",
    },
    "without_all_refusal_handling": {
        "GTF_ENABLE_REFUSAL_GATE": "0",
        "GTF_ENABLE_SCOPE_GATE_V2": "0",
        "GTF_ENABLE_SCOPE_LLM_GATE": "0",
        "GTF_ENABLE_REFUSAL_OUTPUT": "0",
    },
    "without_llm_assisted_decision": {
        "GTF_ENABLE_LLM_ASSISTED_DECISION": "0",
        "GTF_ENABLE_SCOPE_LLM_GATE": "0",
    },
    "without_template_based_fallback": {"GTF_ENABLE_V7_FALLBACK": "0"},
    "without_embedding_enhancement": {
        "GTF_ENABLE_EMBEDDING": "0",
        "GTF_ENABLE_ENTITY_EMBEDDING_GROUNDING": "0",
        "GTF_ENABLE_TRUE_ENTITY_GROUNDING": "0",
        "GTF_ENABLE_EMBEDDING_ENTITY_CANDIDATES": "0",
        "GTF_ENABLE_EMBEDDING_RELATION_FALLBACK": "0",
        "GTF_ENABLE_EMBEDDING_ANSWER_RERANK": "0",
    },
    "without_entity_embedding": {
        "GTF_ENABLE_EMBEDDING": "1",
        "GTF_ENABLE_ENTITY_EMBEDDING_GROUNDING": "0",
        "GTF_ENABLE_TRUE_ENTITY_GROUNDING": "0",
        "GTF_ENABLE_EMBEDDING_ENTITY_CANDIDATES": "0",
    },
    "without_relation_embedding": {
        "GTF_ENABLE_EMBEDDING": "1",
        "GTF_ENABLE_EMBEDDING_RELATION_FALLBACK": "0",
    },
    "without_answer_rerank": {
        "GTF_ENABLE_EMBEDDING": "1",
        "GTF_ENABLE_EMBEDDING_ANSWER_RERANK": "0",
    },
}


META_KEYS = [
    "query",
    "question_type",
    "subject",
    "route",
    "intent_source",
    "final_route",
    "answer_source",
    "kag_used",
    "graph_answers",
    "kag_answers",
    "is_refusal",
]


def build_env(overrides: Dict[str, str]) -> Dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("GTF_NEO4J_URI", "bolt://127.0.0.1:7688")
    env.setdefault("GTF_NEO4J_USER", "neo4j")
    env.setdefault("GTF_NEO4J_PASSWORD", "CHANGE_ME")
    env.setdefault("GTF_NEO4J_DATABASE", "neo4j")
    env.setdefault("GTF_NAMESPACE", "GansuTechFinanceDevV1Enhance")
    env["PYTHONPATH"] = f"{ROOT / 'app'}{os.pathsep}{env.get('PYTHONPATH', '')}"
    env.update(FULL_SYSTEM_FLAGS)
    env.update(overrides)
    return env


def interesting_flags(env: Dict[str, str], overrides: Dict[str, str], version: str) -> Dict[str, object]:
    prefixes = ("GTF_ENABLE_", "GTF_SCHEMA_", "GTF_EMBEDDING_", "GTF_ENTITY_", "GTF_RELATION_")
    effective = {k: env[k] for k in sorted(env) if k.startswith(prefixes)}
    for key in sorted(FULL_SYSTEM_FLAGS | overrides):
        effective[key] = env[key]
    return {
        "version": version,
        "base_full_system_flags": FULL_SYSTEM_FLAGS,
        "version_overrides": overrides,
        "effective_flags": effective,
    }


def parse_answer_section(raw: str) -> str:
    marker = "===== ANSWER ====="
    if marker not in raw:
        return ""
    tail = raw.split(marker, 1)[1]
    for stop in ["===== CYPHER =====", "===== KAG EVIDENCE =====", "===== KAG EVIDENCE ANSWER ====="]:
        if stop in tail:
            tail = tail.split(stop, 1)[0]
    return tail.strip()


def parse_meta(raw: str) -> Dict[str, str]:
    meta: Dict[str, str] = {}
    for key in META_KEYS:
        match = re.search(rf"^{re.escape(key)}\s*=\s*(.*)$", raw, flags=re.MULTILINE)
        if match:
            meta[key] = match.group(1).strip()
    meta["answer"] = parse_answer_section(raw)
    return meta


def read_rows(path: Path) -> List[Dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for pos, row in enumerate(rows, start=1):
        row.setdefault("smoke_index", str(pos))
        if not row["smoke_index"]:
            row["smoke_index"] = str(pos)
    return rows


def _safe_file_token(value: str) -> str:
    token = re.sub(r"[^0-9A-Za-z_.-]+", "_", value.strip())
    return token[:120] or "unknown"


def run_question(version: str, row: Dict[str, str], env: Dict[str, str], timeout: int, raw_dir: Path) -> Dict[str, str]:
    question = row["question"].strip()
    script = ANSWER_SCRIPT
    start = time.monotonic()
    error = ""
    try:
        proc = subprocess.run(
            [sys.executable, str(script), question],
            cwd=str(ROOT / "app"),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
        )
        raw = proc.stdout or ""
        returncode = proc.returncode
    except subprocess.TimeoutExpired as exc:
        raw = exc.stdout if isinstance(exc.stdout, str) else ""
        returncode = -999
        error = f"timeout after {timeout}s"
    latency_ms = int((time.monotonic() - start) * 1000)

    smoke_index = row.get("smoke_index", "")
    question_id = _safe_file_token(row.get("question_id", ""))
    try:
        smoke_token = f"{int(smoke_index):04d}"
    except Exception:
        smoke_token = _safe_file_token(smoke_index)
    raw_path = raw_dir / f"{smoke_token}_{question_id}.log"
    raw_path.write_text(raw, encoding="utf-8")
    meta = parse_meta(raw)

    out = {
        "version_name": version,
        "smoke_index": row.get("smoke_index", ""),
        "smoke_group": row.get("smoke_group", ""),
        "target_ablation": row.get("target_ablation", ""),
        "question_id": row.get("question_id", ""),
        "category": row.get("category", ""),
        "subcategory": row.get("subcategory", ""),
        "metric_mode": row.get("metric_mode", ""),
        "question": question,
        "gold_items": row.get("gold_items", ""),
        "should_refuse": row.get("should_refuse", ""),
        "returncode": str(returncode),
        "error": error,
        "latency_ms": str(latency_ms),
        "raw_log_path": str(raw_path),
    }
    out.update({key: meta.get(key, "") for key in META_KEYS})
    out["answer"] = meta.get("answer", "")
    out["has_traceback"] = str("Traceback" in raw)
    out["has_neo4j_connection_error"] = str("Couldn't connect" in raw or "Neo4j" in raw and "Operation not permitted" in raw)
    return out


def write_csv(path: Path, rows: Iterable[Dict[str, str]]) -> None:
    rows = list(rows)
    if not rows:
        return
    fieldnames: List[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _sort_results(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    def key(row: Dict[str, str]) -> tuple[int, str]:
        try:
            index = int(row.get("smoke_index", "0"))
        except Exception:
            index = 0
        return index, row.get("question_id", "")

    return sorted(rows, key=key)


def write_route_distribution(path: Path, rows: List[Dict[str, str]]) -> None:
    fields = ["route", "final_route", "answer_source", "intent_source", "smoke_group"]
    out_rows: List[Dict[str, str]] = []
    for field in fields:
        counts = Counter(row.get(field, "") or "(empty)" for row in rows)
        for value, count in counts.most_common():
            out_rows.append({"field": field, "value": value, "count": str(count)})
    write_csv(path, out_rows)


def _flush_results(out_dir: Path, results: List[Dict[str, str]]) -> None:
    ordered = _sort_results(results)
    write_csv(out_dir / "raw_result.csv", ordered)
    write_route_distribution(out_dir / "route_distribution.csv", ordered)


def run_version(
    version: str,
    sample_path: Path,
    out_root: Path,
    timeout: int,
    resume: bool = False,
    workers: int = 1,
) -> None:
    overrides = VERSIONS[version]
    env = build_env(overrides)
    out_dir = out_root / version
    raw_dir = out_dir / "raw_logs"
    raw_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "feature_flags.json").write_text(
        json.dumps(interesting_flags(env, overrides, version), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    rows = read_rows(sample_path)
    result_path = out_dir / "raw_result.csv"
    results: List[Dict[str, str]] = []
    completed = set()
    if resume and result_path.exists():
        results = read_rows(result_path)
        completed = {row.get("smoke_index", "") for row in results}

    total = len(rows)
    pending: List[tuple[int, Dict[str, str]]] = []
    for pos, row in enumerate(rows, start=1):
        smoke_index = row.get("smoke_index", "")
        if resume and smoke_index in completed:
            print(f"[SKIP] {version} {pos}/{total} smoke_index={smoke_index}", flush=True)
        else:
            pending.append((pos, row))

    if not pending:
        _flush_results(out_dir, results)
        return

    workers = max(1, int(workers))
    if workers == 1:
        for pos, row in pending:
            print(
                f"[RUN] {version} {pos}/{total} smoke_index={row.get('smoke_index', '')} question_id={row.get('question_id', '')}",
                flush=True,
            )
            results.append(run_question(version, row, env, timeout, raw_dir))
            _flush_results(out_dir, results)
        return

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {}
        for pos, row in pending:
            print(
                f"[RUN] {version} {pos}/{total} smoke_index={row.get('smoke_index', '')} question_id={row.get('question_id', '')}",
                flush=True,
            )
            futures[pool.submit(run_question, version, row, env, timeout, raw_dir)] = (pos, row)

        for future in as_completed(futures):
            pos, row = futures[future]
            result = future.result()
            results.append(result)
            print(
                f"[DONE] {version} {pos}/{total} smoke_index={row.get('smoke_index', '')} returncode={result.get('returncode', '')} latency_ms={result.get('latency_ms', '')}",
                flush=True,
            )
            _flush_results(out_dir, results)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=Path, default=ROOT / "experiments/ablation_smoke_20.csv")
    parser.add_argument("--out-root", type=Path, default=ROOT / "experiments/results/ablation_switch_smoke_20")
    parser.add_argument("--versions", nargs="+", default=["full_system"], choices=sorted(VERSIONS))
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--resume", action="store_true", help="Skip rows already present in raw_result.csv and flush after each row.")
    parser.add_argument("--workers", type=int, default=1, help="Number of questions to run concurrently within each version.")
    args = parser.parse_args()

    for version in args.versions:
        print(f"[SMOKE] {version}", flush=True)
        run_version(
            version,
            args.sample,
            args.out_root,
            args.timeout,
            resume=args.resume,
            workers=args.workers,
        )
    print(f"out_root={args.out_root}", flush=True)


if __name__ == "__main__":
    main()
