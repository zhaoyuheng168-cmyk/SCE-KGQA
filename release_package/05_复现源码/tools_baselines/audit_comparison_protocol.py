#!/usr/bin/env python3
"""Fail-closed audit for the frozen paper comparison protocol."""

from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BASELINES = ROOT / "tools" / "baselines"
MAIN_GENERATIVE = [
    "llm_only.py",
    "naive_bm25_rag.py",
    "naive_vector_rag.py",
    "hybrid_rag.py",
    "text_kg_rag.py",
    "langchain_rag.py",
    "llamaindex_rag.py",
    "kg_context_rag.py",
    "entity_linked_graphrag.py",
]
MAIN_INDEPENDENT = ["rule_based_kgqa.py", "graph_only_kgqa.py"]
BANNED_GOLD = {
    "gold_items",
    "gold_answer_text",
    "gold_source_type",
    "canonical_subject",
    "should_refuse",
    "relation_type",
    "target_type",
}
BANNED_SCE_IMPORTS = {
    "schema_utils",
    "answer_hybrid_v8_graph_kag_fallback",
    "sce_kgqa_full",
    "schema_router_no_evidence",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def inspect_path(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    found_gold = sorted(
        token
        for token in BANNED_GOLD
        if re.search(rf"(?:row|gold)\s*\.get\(\s*['\"]{re.escape(token)}['\"]", text)
    )
    found_sce = sorted(BANNED_SCE_IMPORTS & imports(path))
    return {
        "path": str(path.relative_to(ROOT)),
        "gold_fields": found_gold,
        "sce_imports": found_sce,
        "pass": not found_gold and not found_sce,
    }


def count_jsonl(path: Path) -> int:
    with path.open("r", encoding="utf-8") as src:
        return sum(1 for line in src if line.strip())


def main() -> None:
    checks = [inspect_path(BASELINES / name) for name in MAIN_GENERATIVE + MAIN_INDEPENDENT]
    checks.append(inspect_path(ROOT / "experiments" / "external_baselines" / "lightrag" / "lightrag_adapter.py"))
    runner = (ROOT / "tools" / "run_baseline_experiment.py").read_text(encoding="utf-8")
    runner_boundary = 'question_only_row = {"question_id": qid, "question": question}' in runner
    corpora = {}
    for name in ["kg_triples_corpus.jsonl", "evidence_corpus.jsonl", "merged_rag_corpus.jsonl", "entity_lexicon.jsonl"]:
        path = ROOT / "experiments" / "baselines" / "corpus" / name
        corpora[name] = {"rows": count_jsonl(path), "sha256": sha256(path)}
    dataset = ROOT / "experiments" / "baselines" / "datasets" / "gtf_kgqa_1300_formal_expanded_gold.csv"
    prompt = BASELINES / "common_prompt.py"
    report = {
        "protocol": "comparison_protocol_v2_20260607",
        "runner_question_only_boundary": runner_boundary,
        "main_baselines": checks,
        "corpora": corpora,
        "formal_dataset": {"rows_with_header": sum(1 for _ in dataset.open(encoding="utf-8-sig")), "sha256": sha256(dataset)},
        "prompt_sha256": sha256(prompt),
        "pass": runner_boundary and all(item["pass"] for item in checks),
    }
    output = ROOT / "experiments" / "baselines" / "reports" / "comparison_protocol_v2_audit.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["pass"]:
        raise SystemExit("Comparison protocol audit failed")


if __name__ == "__main__":
    main()
