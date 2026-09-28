#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run reproducible baseline and ablation experiments for the delivered KGQA system."""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "experiments/baselines/datasets/gtf_kgqa_1300_formal.csv"
GOLD = ROOT / "experiments/baselines/datasets/gtf_kgqa_1300_formal_expanded_gold.csv"
BATCH_SCRIPT = ROOT / "app/评测脚本/真实自由问答测试集批量评测_v1.py"
METRICS_SCRIPT = ROOT / "blind_tests/blind1200_v3/eval_tools/evaluate_paper_corrected_metrics.py"


FULL_SYSTEM_FLAGS: dict[str, str] = {
    "GTF_ENABLE_V7_FALLBACK": "0",
    "GTF_ENABLE_KAG_FALLBACK": "1",
    "GTF_ENABLE_GENERIC_RELATION_FALLBACK": "1",
    "GTF_ENABLE_REVERSE_RELATION": "1",
    "GTF_ENABLE_V8_KAG_MULTIHOP_PLANNER": "1",
    "GTF_ENABLE_SCOPE_GATE_V2": "1",
    "GTF_ENABLE_SCOPE_LLM_GATE": "1",
    "GTF_ENABLE_REFUSAL_OUTPUT": "1",
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
    "GTF_EMBEDDING_MODEL_NAME": "runtime_data/models/bge-small-zh-v1.5",
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


EXPERIMENTS: dict[str, dict[str, str]] = {
    "full_embedding": {},
    "full_v8": {},
    "without_embedding": {
        "GTF_ENABLE_EMBEDDING": "0",
        "GTF_ENABLE_EMBEDDING_EVIDENCE": "0",
        "GTF_ENABLE_ENTITY_EMBEDDING_GROUNDING": "0",
        "GTF_ENABLE_TRUE_ENTITY_GROUNDING": "0",
        "GTF_ENABLE_EMBEDDING_ENTITY_CANDIDATES": "0",
        "GTF_ENABLE_EMBEDDING_RELATION_FALLBACK": "0",
        "GTF_ENABLE_EMBEDDING_ANSWER_RERANK": "0",
    },
    "without_entity_embedding": {
        "GTF_ENABLE_ENTITY_EMBEDDING_GROUNDING": "0",
        "GTF_ENABLE_TRUE_ENTITY_GROUNDING": "0",
        "GTF_ENABLE_EMBEDDING_ENTITY_CANDIDATES": "0",
    },
    "without_relation_grounding": {
        "GTF_ENABLE_EMBEDDING_RELATION_FALLBACK": "0",
    },
    "without_answer_rerank": {
        "GTF_ENABLE_EMBEDDING_ANSWER_RERANK": "0",
    },
    "without_reverse_relation": {
        "GTF_ENABLE_REVERSE_RELATION": "0",
    },
    "without_schema_semantic_router": {
        "GTF_ENABLE_SCHEMA_SEMANTIC_ROUTER": "0",
    },
    "text_rag_embedding_baseline": {
        "GTF_BASELINE_MODE": "text_rag_embedding",
        "GTF_ENABLE_EMBEDDING": "1",
        "GTF_ENABLE_EMBEDDING_EVIDENCE": "1",
        "GTF_ENABLE_ENTITY_EMBEDDING_GROUNDING": "0",
        "GTF_ENABLE_TRUE_ENTITY_GROUNDING": "0",
        "GTF_ENABLE_EMBEDDING_ENTITY_CANDIDATES": "0",
        "GTF_ENABLE_EMBEDDING_RELATION_FALLBACK": "0",
        "GTF_ENABLE_EMBEDDING_ANSWER_RERANK": "0",
    },
    "graph_only": {
        "GTF_ENABLE_KAG_FALLBACK": "0",
        "GTF_ENABLE_V7_FALLBACK": "0",
        "GTF_ENABLE_RULE_REASONING": "0",
        "GTF_ENABLE_MULTIHOP": "0",
        "GTF_ENABLE_GENERIC_RELATION": "0",
        "GTF_ENABLE_GENERIC_RELATION_FALLBACK": "0",
        "GTF_ENABLE_EMBEDDING": "0",
        "GTF_ENABLE_EMBEDDING_EVIDENCE": "0",
        "GTF_ENABLE_ENTITY_EMBEDDING_GROUNDING": "0",
        "GTF_ENABLE_EMBEDDING_ENTITY_CANDIDATES": "0",
        "GTF_ENABLE_EMBEDDING_RELATION_FALLBACK": "0",
        "GTF_ENABLE_EMBEDDING_ANSWER_RERANK": "0",
    },
    "without_type_gate": {
        "GTF_ENABLE_TYPE_GATE": "0",
    },
    "without_kag_evidence": {
        "GTF_ENABLE_KAG_FALLBACK": "0",
    },
    "without_rule_reasoning": {
        "GTF_ENABLE_RULE_REASONING": "0",
    },
    "without_refusal_gate": {
        "GTF_ENABLE_REFUSAL_GATE": "0",
        "GTF_ENABLE_SCOPE_GATE_V2": "0",
        "GTF_ENABLE_SCOPE_LLM_GATE": "0",
        "GTF_ENABLE_REFUSAL_OUTPUT": "0",
    },
    "without_multihop": {
        "GTF_ENABLE_MULTIHOP": "0",
        "GTF_ENABLE_SCHEMA_MULTIHOP_ROUTER": "0",
        "GTF_ENABLE_V8_KAG_MULTIHOP_PLANNER": "0",
        "GTF_ENABLE_V8_MULTIHOP_SAFETY_GATE": "0",
    },
    "without_generic_relation": {
        "GTF_ENABLE_GENERIC_RELATION": "0",
        "GTF_ENABLE_GENERIC_RELATION_FALLBACK": "0",
    },
    "without_v7_fallback": {
        "GTF_ENABLE_V7_FALLBACK": "0",
    },
}


def result_paths(limit: int) -> tuple[Path, Path]:
    result_name = "真实自由问答测试集_v1评测结果"
    if limit > 0:
        result_name = f"真实自由问答测试集_v1前{limit}题冒烟评测结果"
    result_dir = ROOT / "app/retrieval_only/tests/results" / result_name
    return result_dir / f"{result_name}.csv", result_dir / f"{result_name}.md"


def run_one(name: str, flags: dict[str, str], workers: int, limit: int, timeout: int, out_root: Path) -> dict[str, str]:
    exp_dir = out_root / name
    exp_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env.setdefault("GTF_NEO4J_URI", "bolt://127.0.0.1:7688")
    env.setdefault("GTF_NEO4J_USER", "neo4j")
    env.setdefault("GTF_NEO4J_PASSWORD", "CHANGE_ME")
    env.setdefault("GTF_NEO4J_DATABASE", "neo4j")
    env.setdefault("GTF_NAMESPACE", "GansuTechFinanceDevV1Enhance")
    env["EVAL_TEST_CSV"] = str(DATASET)
    env["EVAL_WORKERS"] = str(workers)
    env["EVAL_TIMEOUT"] = str(timeout)
    if limit > 0:
        env["EVAL_LIMIT"] = str(limit)
    else:
        env.pop("EVAL_LIMIT", None)
    env.update(FULL_SYSTEM_FLAGS)
    env.update(flags)

    effective_flags = {k: env[k] for k in sorted(FULL_SYSTEM_FLAGS | flags)}
    (exp_dir / "feature_flags.json").write_text(
        json.dumps(
            {
                "experiment": name,
                "base_full_system_flags": FULL_SYSTEM_FLAGS,
                "experiment_overrides": flags,
                "effective_flags": effective_flags,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    subprocess.run([sys.executable, str(BATCH_SCRIPT)], cwd=str(ROOT), env=env, check=True)

    raw_csv, raw_md = result_paths(limit)
    copied_csv = exp_dir / "raw_result.csv"
    copied_md = exp_dir / "raw_report.md"
    shutil.copy2(raw_csv, copied_csv)
    if raw_md.exists():
        shutil.copy2(raw_md, copied_md)

    metrics_dir = exp_dir / "paper_corrected_metrics"
    subprocess.run(
        [
            sys.executable,
            str(METRICS_SCRIPT),
            "--source",
            str(GOLD),
            "--result",
            str(copied_csv),
            "--out-dir",
            str(metrics_dir),
        ],
        cwd=str(ROOT),
        env=env,
        check=True,
    )

    summary_path = metrics_dir / "paper_corrected_metrics_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    return {
        "experiment": name,
        "flags": json.dumps(effective_flags, ensure_ascii=False, sort_keys=True),
        "total_rows": str(summary.get("total_rows", summary.get("total", ""))),
        "old_accuracy": str(summary.get("old_accuracy", "")),
        "paper_corrected_accuracy": str(summary.get("paper_corrected_accuracy", "")),
        "non_refusal_macro_precision": str(summary.get("non_refusal_macro_precision", "")),
        "non_refusal_macro_recall": str(summary.get("non_refusal_macro_recall", "")),
        "non_refusal_macro_f1": str(summary.get("non_refusal_macro_f1", "")),
        "raw_result": str(copied_csv),
        "metrics_dir": str(metrics_dir),
    }


def main() -> None:
    global DATASET, GOLD
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiments", nargs="+", default=["full_v8"], choices=sorted(EXPERIMENTS))
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--limit", type=int, default=0, help="0 means all rows of the selected dataset.")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--out-root", type=Path, default=ROOT / "experiments/results/ablations")
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--gold", type=Path, default=GOLD)
    args = parser.parse_args()
    DATASET = args.dataset.resolve()
    GOLD = args.gold.resolve()

    args.out_root.mkdir(parents=True, exist_ok=True)
    rows = []
    for name in args.experiments:
        print(f"[RUN] {name}")
        rows.append(run_one(name, EXPERIMENTS[name], args.workers, args.limit, args.timeout, args.out_root))

    summary_csv = args.out_root / "ablation_summary.csv"
    fieldnames = [
        "experiment",
        "total_rows",
        "old_accuracy",
        "paper_corrected_accuracy",
        "non_refusal_macro_precision",
        "non_refusal_macro_recall",
        "non_refusal_macro_f1",
        "flags",
        "raw_result",
        "metrics_dir",
    ]
    with summary_csv.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"summary={summary_csv}")


if __name__ == "__main__":
    main()
