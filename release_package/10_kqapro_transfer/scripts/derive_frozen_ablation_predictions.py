#!/usr/bin/env python3
"""Derive comparison and ablation selections from frozen candidate executions.

This script never reads KQA Pro gold answers, programs, SPARQL, or choices.
All variants select among the exact same frozen top-5 candidates.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_INPUT_HASH = "53A5D7BABB2B1C87D4E947C80C68D896EC321B632A411BD36646ADF42FD39627"


def component_scores(candidate: dict[str, Any]) -> dict[str, float]:
    execution = candidate["execution"]
    return {
        "model": float(candidate.get("model_score") or 0.0),
        "schema": 0.06 * float(candidate.get("schema_score") or 0.0),
        "schema_original": 0.15 * float(candidate.get("schema_score") or 0.0),
        "execution": 1.5 if execution["status"] == "ok" else -8.0,
        "nonempty": 2.0 if execution.get("nonempty") else -2.0,
        "relevance": 2.5 * float(candidate.get("question_relevance") or 0.0),
        "evidence": min(float(execution.get("evidence_fact_steps") or 0), 2.0) * 0.3,
    }


VARIANTS = {
    "bart_top1": None,
    "schema_only": ("model", "schema_original"),
    "execution_only": ("model", "execution", "nonempty"),
    "sce_full": ("model", "schema", "execution", "nonempty", "relevance", "evidence"),
    "sce_wo_schema": ("model", "execution", "nonempty", "relevance", "evidence"),
    "sce_wo_execution": ("model", "schema", "relevance"),
    "sce_wo_nonempty": ("model", "schema", "execution", "relevance", "evidence"),
    "sce_wo_relevance": ("model", "schema", "execution", "nonempty", "evidence"),
    "sce_wo_evidence": ("model", "schema", "execution", "nonempty", "relevance"),
}


def select_variant(candidates: list[dict[str, Any]], variant: str) -> dict[str, Any]:
    if variant == "bart_top1":
        return next(candidate for candidate in candidates if int(candidate["rank"]) == 1)
    components = VARIANTS[variant]
    assert components is not None
    rescored = []
    for candidate in candidates:
        scores = component_scores(candidate)
        score = sum(scores[name] for name in components)
        rescored.append({**candidate, "ablation_score": round(score, 6), "active_components": list(components)})
    return max(rescored, key=lambda item: item["ablation_score"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=ROOT / "frozen"
        / "kqapro_holdout_11697_sce_blind_predictions.jsonl",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "work" / "kqapro_holdout_11697_ablation_predictions.jsonl",
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    if args.output.exists() and not args.overwrite:
        raise FileExistsError(f"Refusing to overwrite: {args.output}")

    import hashlib

    digest = hashlib.sha256(args.input.read_bytes()).hexdigest().upper()
    if digest != EXPECTED_INPUT_HASH:
        raise ValueError(f"Frozen input hash mismatch: {digest}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with args.input.open("r", encoding="utf-8") as source, args.output.open("w", encoding="utf-8") as target:
        for line in source:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            selections = {
                variant: select_variant(row["candidates"], variant)
                for variant in VARIANTS
            }
            output = {
                "question_id": row["question_id"],
                "source_index": row["source_index"],
                "question": row["question"],
                "input_policy": row["input_policy"],
                "frozen_candidate_source_sha256": digest,
                "variants": selections,
            }
            target.write(json.dumps(output, ensure_ascii=False) + "\n")
            count += 1

    print(json.dumps({"output": str(args.output), "rows": count, "variants": list(VARIANTS), "gold_fields_read": []}, ensure_ascii=False))


if __name__ == "__main__":
    main()
