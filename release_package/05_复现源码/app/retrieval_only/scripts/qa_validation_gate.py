# -*- coding: utf-8 -*-
"""
Pure validation/type-gate helper functions for the KGQA refactor.

Stage 4A only:
- No main answer module imports.
- No graph database access.
- No model or external service calls.
- No routing decisions.
- No business repair logic.
"""

from typing import Any, Dict, List


VALIDATION_ACTIONS = {
    "pass",
    "block",
    "repair",
    "unknown",
}


STANDARD_VALIDATION_FIELDS = [
    "validation_action",
    "validation_reason",
    "validation_passed",
    "expected_subject_types",
    "actual_subject_types",
    "original_qtype",
    "repaired_qtype",
    "original_subject",
    "repaired_subject",
    "metadata",
]


def _safe_text(value: Any) -> str:
    """Return a stripped text value without raising on unusual input."""
    if value is None:
        return ""
    try:
        return str(value).strip()
    except Exception:
        return ""


def normalize_type_name(value: Any) -> str:
    """Normalize a single type label into a clean type name."""
    try:
        text = _safe_text(value)
        if not text:
            return ""

        if text.startswith("<") and text.endswith(">"):
            text = text[1:-1].strip()

        if "||" in text:
            parts = [part.strip() for part in text.split("||") if part.strip()]
            text = parts[-1] if parts else ""

        if ":" in text:
            text = text.rsplit(":", 1)[-1].strip()

        if "." in text:
            text = text.rsplit(".", 1)[-1].strip()

        if text.startswith("<") and text.endswith(">"):
            text = text[1:-1].strip()

        return text
    except Exception:
        return ""


def normalize_type_list(value: Any) -> List[str]:
    """Normalize one or many type labels into a de-duplicated list."""
    try:
        if value is None:
            return []

        if isinstance(value, (list, tuple, set)):
            raw_items = list(value)
        else:
            raw_items = [value]

        normalized: List[str] = []
        seen = set()
        for item in raw_items:
            type_name = normalize_type_name(item)
            if not type_name or type_name in seen:
                continue
            normalized.append(type_name)
            seen.add(type_name)
        return normalized
    except Exception:
        return []


def type_matches(actual_types: Any, expected_types: Any) -> bool:
    """Return True when normalized actual and expected type lists overlap."""
    try:
        actual = normalize_type_list(actual_types)
        expected = normalize_type_list(expected_types)
        if not actual or not expected:
            return False
        return bool(set(actual).intersection(expected))
    except Exception:
        return False


def _normalize_action(action: Any) -> str:
    """Normalize validation action to a known safe action."""
    normalized = _safe_text(action)
    return normalized if normalized in VALIDATION_ACTIONS else "unknown"


def _passed_for_action(action: str) -> bool:
    """Map a validation action to the standard validation_passed flag."""
    return action in {"pass", "repair"}


def build_validation_result(action: Any, reason: Any = "", **kwargs: Any) -> Dict[str, Any]:
    """Build a standard validation result without routing or answer fields."""
    try:
        normalized_action = _normalize_action(action)
        metadata = kwargs.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}

        result: Dict[str, Any] = {}
        for key, value in kwargs.items():
            if key not in STANDARD_VALIDATION_FIELDS:
                result[key] = value

        result.update(
            {
                "validation_action": normalized_action,
                "validation_reason": _safe_text(reason),
                "validation_passed": _passed_for_action(normalized_action),
                "expected_subject_types": normalize_type_list(
                    kwargs.get("expected_subject_types")
                ),
                "actual_subject_types": normalize_type_list(
                    kwargs.get("actual_subject_types")
                ),
                "original_qtype": _safe_text(kwargs.get("original_qtype")),
                "repaired_qtype": _safe_text(kwargs.get("repaired_qtype")),
                "original_subject": _safe_text(kwargs.get("original_subject")),
                "repaired_subject": _safe_text(kwargs.get("repaired_subject")),
                "metadata": dict(metadata),
            }
        )
        return result
    except Exception:
        return {
            "validation_action": "unknown",
            "validation_reason": _safe_text(reason),
            "validation_passed": False,
            "expected_subject_types": [],
            "actual_subject_types": [],
            "original_qtype": "",
            "repaired_qtype": "",
            "original_subject": "",
            "repaired_subject": "",
            "metadata": {},
        }


def is_validation_pass(result: Any) -> bool:
    """Return True when a validation result represents a pass."""
    try:
        if not isinstance(result, dict):
            return False
        return result.get("validation_action") == "pass" or result.get(
            "validation_passed"
        ) is True
    except Exception:
        return False


def is_validation_block(result: Any) -> bool:
    """Return True when a validation result represents a block."""
    try:
        if not isinstance(result, dict):
            return False
        return result.get("validation_action") == "block"
    except Exception:
        return False


def is_validation_repair(result: Any) -> bool:
    """Return True when a validation result represents a repair."""
    try:
        if not isinstance(result, dict):
            return False
        return result.get("validation_action") == "repair"
    except Exception:
        return False


def normalize_validation_result(result: Any) -> Dict[str, Any]:
    """Fill and normalize a validation result while preserving extra fields."""
    try:
        if not isinstance(result, dict):
            return build_validation_result("unknown", "invalid_validation_result")

        normalized = dict(result)
        action = _normalize_action(normalized.get("validation_action"))
        metadata = normalized.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}

        normalized["validation_action"] = action
        normalized["validation_reason"] = _safe_text(
            normalized.get("validation_reason")
        )
        normalized["validation_passed"] = _passed_for_action(action)
        normalized["expected_subject_types"] = normalize_type_list(
            normalized.get("expected_subject_types")
        )
        normalized["actual_subject_types"] = normalize_type_list(
            normalized.get("actual_subject_types")
        )
        normalized["original_qtype"] = _safe_text(normalized.get("original_qtype"))
        normalized["repaired_qtype"] = _safe_text(normalized.get("repaired_qtype"))
        normalized["original_subject"] = _safe_text(
            normalized.get("original_subject")
        )
        normalized["repaired_subject"] = _safe_text(
            normalized.get("repaired_subject")
        )
        normalized["metadata"] = dict(metadata)

        for field in STANDARD_VALIDATION_FIELDS:
            if field not in normalized:
                normalized[field] = build_validation_result("unknown")[field]

        return normalized
    except Exception:
        return build_validation_result("unknown", "invalid_validation_result")


__all__ = [
    "VALIDATION_ACTIONS",
    "STANDARD_VALIDATION_FIELDS",
    "normalize_type_name",
    "normalize_type_list",
    "type_matches",
    "build_validation_result",
    "normalize_validation_result",
    "is_validation_pass",
    "is_validation_block",
    "is_validation_repair",
]
