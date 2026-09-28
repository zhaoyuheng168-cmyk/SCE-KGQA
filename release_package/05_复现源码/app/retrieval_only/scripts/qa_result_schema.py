# -*- coding: utf-8 -*-
"""Shared result-field schema helpers for the KGQA refactor.

This module is intentionally standalone in stage 1A. It does not import or
modify V8/V7 logic; callers may opt in later by wrapping existing results.
"""

from typing import Any, Dict, List


STANDARD_RESULT_FIELDS = [
    "query",
    "question_type",
    "chain_id",
    "subject",
    "constraints",
    "intent_source",
    "route_candidates",
    "selected_route",
    "route_decision_reason",
    "validation_action",
    "validation_reason",
    "route",
    "final_route",
    "answer_source",
    "graph_answers",
    "kag_answers",
    "v7_answers",
    "cypher",
    "evidence_paths",
    "kag_used",
    "v7_used",
    "is_refusal",
    "refusal_reason",
    "answer",
]


_LIST_FIELDS = {
    "graph_answers",
    "kag_answers",
    "v7_answers",
    "evidence_paths",
    "route_candidates",
}

_BOOL_FIELDS = {
    "kag_used",
    "v7_used",
    "is_refusal",
}


def normalize_list_field(value: Any) -> List[Any]:
    """Normalize a result field to a list without interpreting item semantics."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, set):
        return list(value)
    if isinstance(value, str):
        if value == "":
            return []
        if "||" in value:
            return [item for item in value.split("||") if item != ""]
        return [value]
    return [value]


def normalize_bool_field(value: Any) -> bool:
    """Normalize common bool-like result field values to bool."""
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"", "0", "false", "no", "none", "null"}:
            return False
        if normalized in {"1", "true", "yes"}:
            return True
    return bool(value)


def _default_for_field(field: str) -> Any:
    if field == "constraints":
        return {}
    if field in _LIST_FIELDS:
        return []
    if field in _BOOL_FIELDS:
        return False
    return ""


def normalize_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """Return a schema-complete result dict while preserving existing fields.

    Existing values are not removed. Core string fields such as answer, route,
    final_route, answer_source, question_type, and subject are kept as provided.
    """
    normalized = dict(result or {})

    for field in STANDARD_RESULT_FIELDS:
        if field not in normalized:
            normalized[field] = _default_for_field(field)

    for field in _LIST_FIELDS:
        normalized[field] = normalize_list_field(normalized.get(field))

    if not isinstance(normalized.get("constraints"), dict):
        normalized["constraints"] = {}

    for field in _BOOL_FIELDS:
        normalized[field] = normalize_bool_field(normalized.get(field))

    return normalized


def make_standard_refusal(query: str, reason: str, **kwargs: Any) -> Dict[str, Any]:
    """Build a standard refusal result without adding external knowledge."""
    refusal_reason = str(reason or "")
    kwargs.pop("final_route", None)
    result = {
        "query": query,
        "question_type": kwargs.pop("question_type", "refuse"),
        "subject": kwargs.pop("subject", ""),
        "route": kwargs.pop("route", "refuse"),
        "final_route": "refuse",
        "answer_source": kwargs.pop("answer_source", "standard_refusal"),
        "kag_used": kwargs.pop("kag_used", False),
        "v7_used": kwargs.pop("v7_used", False),
        "is_refusal": True,
        "refusal_reason": refusal_reason,
        "answer": kwargs.pop("answer", f"无法回答：{refusal_reason}"),
    }
    result.update(kwargs)
    result["final_route"] = "refuse"
    return normalize_result(result)
