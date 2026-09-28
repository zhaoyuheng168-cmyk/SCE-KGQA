#!/usr/bin/env python3
"""Rerank generated KoPL programs with KB-derived schema constraints.

This stage uses only generated candidates and kb.json. It never reads gold
programs, SPARQL, answers, or choices.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


FUNCTION_ARITY = {
    "FindAll": 0,
    "Find": 1,
    "FilterConcept": 1,
    "FilterStr": 2,
    "FilterNum": 3,
    "FilterYear": 3,
    "FilterDate": 3,
    "QFilterStr": 2,
    "QFilterNum": 3,
    "QFilterYear": 3,
    "QFilterDate": 3,
    "Relate": 2,
    "And": 0,
    "Or": 0,
    "Count": 0,
    "What": 0,
    "SelectBetween": 2,
    "SelectAmong": 2,
    "QueryAttr": 1,
    "QueryAttrUnderCondition": 3,
    "VerifyStr": 1,
    "VerifyNum": 2,
    "VerifyYear": 2,
    "VerifyDate": 2,
    "QueryRelation": 0,
    "QueryAttrQualifier": 3,
    "QueryRelationQualifier": 2,
}

BINARY_FUNCTIONS = {"And", "Or", "SelectBetween", "QueryRelation", "QueryRelationQualifier"}
START_FUNCTIONS = {"Find", "FindAll"}
FILTER_ATTRIBUTE_FUNCTIONS = {"FilterStr", "FilterNum", "FilterYear", "FilterDate"}
FILTER_QUALIFIER_FUNCTIONS = {"QFilterStr", "QFilterNum", "QFilterYear", "QFilterDate"}
QUERY_ATTRIBUTE_FUNCTIONS = {"QueryAttr", "QueryAttrUnderCondition", "QueryAttrQualifier"}


class SchemaCatalog:
    def __init__(self, kb_path: Path):
        kb = json.loads(kb_path.read_text(encoding="utf-8"))
        self.entity_names = {str(item["name"]).strip() for item in kb["entities"].values()}
        self.concept_names = {str(item["name"]).strip() for item in kb["concepts"].values()}
        self.attribute_keys: set[str] = set()
        self.relation_keys: set[str] = set()
        self.qualifier_keys: set[str] = set()
        self.attribute_types: dict[str, Counter[str]] = {}
        self.qualifier_types: dict[str, Counter[str]] = {}

        for entity in kb["entities"].values():
            for attribute in entity.get("attributes", []):
                key = str(attribute["key"])
                value_type = str(attribute["value"]["type"])
                self.attribute_keys.add(key)
                self.attribute_types.setdefault(key, Counter())[value_type] += 1
                for qualifier_key, values in attribute.get("qualifiers", {}).items():
                    self._add_qualifier(str(qualifier_key), values)
            for relation in entity.get("relations", []):
                self.relation_keys.add(str(relation["predicate"]))
                for qualifier_key, values in relation.get("qualifiers", {}).items():
                    self._add_qualifier(str(qualifier_key), values)

    def _add_qualifier(self, key: str, values: list[dict[str, Any]]) -> None:
        self.qualifier_keys.add(key)
        for value in values:
            self.qualifier_types.setdefault(key, Counter())[str(value["type"])] += 1


def expected_type(function: str) -> set[str]:
    if function.endswith("Str"):
        return {"string"}
    if function.endswith("Num"):
        return {"quantity"}
    if function.endswith("Year") or function.endswith("Date"):
        return {"year", "date"}
    return set()


def dominant_types(counters: dict[str, Counter[str]], key: str) -> set[str]:
    values = counters.get(key)
    return set(values or {})


def score_candidate(program: list[dict[str, Any]], schema: SchemaCatalog) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []
    branch_depth = 0
    previous_output = False

    if not program:
        return -100.0, ["empty_program"]

    for index, step in enumerate(program):
        function = str(step.get("function") or "").strip()
        inputs = [str(value).strip() for value in step.get("inputs", [])]
        if function not in FUNCTION_ARITY:
            score -= 12.0
            reasons.append(f"unknown_function@{index}:{function}")
            continue

        score += 2.0
        expected_arity = FUNCTION_ARITY[function]
        if len(inputs) == expected_arity:
            score += 2.0
        else:
            score -= 8.0
            reasons.append(f"arity_mismatch@{index}:{function}:{len(inputs)}/{expected_arity}")

        if function in START_FUNCTIONS:
            branch_depth += 1
            previous_output = True
        elif function in BINARY_FUNCTIONS:
            if branch_depth < 2:
                score -= 10.0
                reasons.append(f"missing_branch@{index}:{function}")
            else:
                branch_depth -= 1
            previous_output = True
        elif not previous_output:
            score -= 10.0
            reasons.append(f"missing_dependency@{index}:{function}")

        if function == "Find" and inputs:
            if inputs[0] in schema.entity_names or inputs[0] in schema.concept_names:
                score += 5.0
            else:
                score -= 6.0
                reasons.append(f"unknown_entity_or_concept@{index}:{inputs[0]}")

        if function == "FilterConcept" and inputs:
            if inputs[0] in schema.concept_names:
                score += 5.0
            else:
                score -= 7.0
                reasons.append(f"unknown_concept@{index}:{inputs[0]}")

        if function in FILTER_ATTRIBUTE_FUNCTIONS and inputs:
            key = inputs[0]
            if key in schema.attribute_keys:
                score += 4.0
                required = expected_type(function)
                observed = dominant_types(schema.attribute_types, key)
                if required and observed and required.isdisjoint(observed):
                    score -= 5.0
                    reasons.append(f"attribute_type_mismatch@{index}:{key}:{sorted(observed)}")
            else:
                score -= 7.0
                reasons.append(f"unknown_attribute@{index}:{key}")

        if function in FILTER_QUALIFIER_FUNCTIONS and inputs:
            key = inputs[0]
            if key in schema.qualifier_keys:
                score += 4.0
                required = expected_type(function)
                observed = dominant_types(schema.qualifier_types, key)
                if required and observed and required.isdisjoint(observed):
                    score -= 5.0
                    reasons.append(f"qualifier_type_mismatch@{index}:{key}:{sorted(observed)}")
            else:
                score -= 7.0
                reasons.append(f"unknown_qualifier@{index}:{key}")

        if function == "Relate" and len(inputs) >= 2:
            if inputs[0] in schema.relation_keys:
                score += 5.0
            else:
                score -= 8.0
                reasons.append(f"unknown_relation@{index}:{inputs[0]}")
            if inputs[1] not in {"forward", "backward"}:
                score -= 5.0
                reasons.append(f"invalid_direction@{index}:{inputs[1]}")

        if function in QUERY_ATTRIBUTE_FUNCTIONS and inputs:
            key = inputs[0]
            if key in schema.attribute_keys:
                score += 4.0
            else:
                score -= 7.0
                reasons.append(f"unknown_query_attribute@{index}:{key}")

        if function == "QueryAttrUnderCondition" and len(inputs) >= 2:
            if inputs[1] in schema.qualifier_keys:
                score += 3.0
            else:
                score -= 6.0
                reasons.append(f"unknown_condition_qualifier@{index}:{inputs[1]}")

        if function == "QueryAttrQualifier" and len(inputs) >= 3:
            if inputs[2] in schema.qualifier_keys:
                score += 3.0
            else:
                score -= 6.0
                reasons.append(f"unknown_attr_qualifier@{index}:{inputs[2]}")

        if function == "QueryRelationQualifier" and len(inputs) >= 2:
            if inputs[0] in schema.relation_keys:
                score += 4.0
            else:
                score -= 7.0
                reasons.append(f"unknown_query_relation@{index}:{inputs[0]}")
            if inputs[1] in schema.qualifier_keys:
                score += 3.0
            else:
                score -= 6.0
                reasons.append(f"unknown_relation_qualifier@{index}:{inputs[1]}")

    if program[0].get("function") not in START_FUNCTIONS:
        score -= 12.0
        reasons.append("program_does_not_start_with_locator")
    return score, reasons


def main() -> None:
    parser = argparse.ArgumentParser()
    root = Path(__file__).resolve().parents[1]
    parser.add_argument("--kb", type=Path, default=root / "data" / "kqapro" / "kb.json")
    parser.add_argument(
        "--input",
        type=Path,
        default=root / "work" / "kqapro_val_bart_top5_candidates.jsonl",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "work" / "kqapro_val_sce_schema_selected.jsonl",
    )
    parser.add_argument("--model-weight", type=float, default=1.0)
    parser.add_argument("--schema-weight", type=float, default=0.15)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    if args.output.exists() and not args.overwrite:
        raise FileExistsError(f"Refusing to overwrite: {args.output}")

    schema = SchemaCatalog(args.kb)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    row_count = 0
    with args.input.open("r", encoding="utf-8") as source, args.output.open("w", encoding="utf-8") as target:
        for line in source:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            rescored = []
            for candidate in row["candidates"]:
                schema_score, reasons = score_candidate(candidate["program"], schema)
                final_score = (
                    args.model_weight * float(candidate["model_score"])
                    + args.schema_weight * schema_score
                )
                rescored.append(
                    {
                        **candidate,
                        "schema_score": schema_score,
                        "schema_violations": reasons,
                        "final_score": final_score,
                    }
                )
            rescored.sort(key=lambda item: item["final_score"], reverse=True)
            output = {
                "question_id": row["question_id"],
                "source_index": row["source_index"],
                "question": row["question"],
                "selection_method": "sce_schema_constrained_reranking",
                "selected_candidate": rescored[0],
                "candidates": rescored,
            }
            target.write(json.dumps(output, ensure_ascii=False) + "\n")
            row_count += 1

    print(
        json.dumps(
            {
                "output": str(args.output),
                "rows": row_count,
                "schema": {
                    "entity_names": len(schema.entity_names),
                    "concept_names": len(schema.concept_names),
                    "attribute_keys": len(schema.attribute_keys),
                    "relation_keys": len(schema.relation_keys),
                    "qualifier_keys": len(schema.qualifier_keys),
                },
                "gold_fields_read": [],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
