# -*- coding: utf-8 -*-
"""
Validation adapter helpers for mapping legacy V8 Type Gate metadata into
standard validation results and validation_shadow_* debug fields.

Stage 4E only:
- No V8/V7 imports.
- No graph database access.
- No model or network calls.
- No routing decisions.

For high-fidelity conversion, callers should pass original list/set/tuple type
values from the Type Gate internals. Passing already joined strings such as
"Entity||Policy" is supported as a low-fidelity compatibility path, but it may
drop upper-level labels by design of qa_validation_gate.normalize_type_list().
"""

from copy import deepcopy
from typing import Any, Dict, List

try:
    from qa_validation_gate import (
        normalize_type_list,
        build_validation_result,
        normalize_validation_result,
        is_validation_pass,
        is_validation_block,
        is_validation_repair,
    )
except Exception:
    from .qa_validation_gate import (
        normalize_type_list,
        build_validation_result,
        normalize_validation_result,
        is_validation_pass,
        is_validation_block,
        is_validation_repair,
    )


ADAPTER_VERSION = "stage4e_v1"
SHADOW_FIELD_PREFIX = "validation_shadow_"

SHADOW_FIELD_NAMES = [
    "validation_shadow_available",
    "validation_shadow_action",
    "validation_shadow_reason",
    "validation_shadow_passed",
    "validation_shadow_expected_subject_types",
    "validation_shadow_actual_subject_types",
    "validation_shadow_original_qtype",
    "validation_shadow_repaired_qtype",
    "validation_shadow_original_subject",
    "validation_shadow_repaired_subject",
    "validation_shadow_action_match",
    "validation_shadow_passed_match",
    "validation_shadow_expected_subject_types_match",
    "validation_shadow_actual_subject_types_match",
    "validation_shadow_error",
]

LEGACY_PASSING_ACTIONS = {"pass", "repair"}
LEGACY_BLOCKING_ACTIONS = {"block"}


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value).strip()
    except Exception:
        return ""


def normalize_legacy_action(action: str) -> str:
    """Normalize legacy V8 Type Gate action to a safe adapter action."""
    normalized = _safe_text(action).lower()
    if normalized in LEGACY_PASSING_ACTIONS or normalized in LEGACY_BLOCKING_ACTIONS:
        return normalized
    return "unknown"


def legacy_action_to_passed(action: str) -> bool:
    """Map legacy V8 Type Gate action to validation_passed semantics."""
    return normalize_legacy_action(action) in LEGACY_PASSING_ACTIONS


def build_validation_from_v8_gate(
    *,
    legacy_action: str = "",
    legacy_reason: str = "",
    expected_subject_types: Any = None,
    actual_subject_types: Any = None,
    original_qtype: str = "",
    repaired_qtype: str = "",
    original_subject: str = "",
    repaired_subject: str = "",
    metadata: Any = None,
) -> Dict[str, Any]:
    """Build a standard validation result from legacy V8 Type Gate fields."""
    safe_metadata = deepcopy(metadata) if isinstance(metadata, dict) else {}
    return build_validation_result(
        normalize_legacy_action(legacy_action),
        _safe_text(legacy_reason),
        expected_subject_types=expected_subject_types,
        actual_subject_types=actual_subject_types,
        original_qtype=original_qtype,
        repaired_qtype=repaired_qtype,
        original_subject=original_subject,
        repaired_subject=repaired_subject,
        metadata=safe_metadata,
    )


def compare_validation_with_legacy(
    validation: dict,
    *,
    legacy_action: str = "",
    expected_subject_types: Any = None,
    actual_subject_types: Any = None,
) -> Dict[str, bool]:
    """Compare a standard validation result with legacy V8 Type Gate inputs."""
    try:
        normalized = normalize_validation_result(validation)
        expected_norm = normalize_type_list(expected_subject_types)
        actual_norm = normalize_type_list(actual_subject_types)
        legacy_action_norm = normalize_legacy_action(legacy_action)
        return {
            "action_match": normalized.get("validation_action") == legacy_action_norm,
            "passed_match": bool(normalized.get("validation_passed"))
            is legacy_action_to_passed(legacy_action_norm),
            "expected_subject_types_match": (
                normalized.get("expected_subject_types", []) == expected_norm
            ),
            "actual_subject_types_match": (
                normalized.get("actual_subject_types", []) == actual_norm
            ),
        }
    except Exception:
        return {
            "action_match": False,
            "passed_match": False,
            "expected_subject_types_match": False,
            "actual_subject_types_match": False,
        }


def validation_to_shadow_fields(
    validation: dict,
    *,
    legacy_action: str = "",
    expected_subject_types: Any = None,
    actual_subject_types: Any = None,
    prefix: str = SHADOW_FIELD_PREFIX,
    error: str = "",
) -> Dict[str, Any]:
    """Convert a standard validation result into validation_shadow_* fields."""
    normalized = normalize_validation_result(validation)
    comparison = compare_validation_with_legacy(
        normalized,
        legacy_action=legacy_action,
        expected_subject_types=expected_subject_types,
        actual_subject_types=actual_subject_types,
    )
    p = _safe_text(prefix) or SHADOW_FIELD_PREFIX
    return {
        f"{p}available": True,
        f"{p}action": normalized.get("validation_action", ""),
        f"{p}reason": normalized.get("validation_reason", ""),
        f"{p}passed": bool(normalized.get("validation_passed")),
        f"{p}expected_subject_types": "||".join(
            normalized.get("expected_subject_types", []) or []
        ),
        f"{p}actual_subject_types": "||".join(
            normalized.get("actual_subject_types", []) or []
        ),
        f"{p}original_qtype": normalized.get("original_qtype", ""),
        f"{p}repaired_qtype": normalized.get("repaired_qtype", ""),
        f"{p}original_subject": normalized.get("original_subject", ""),
        f"{p}repaired_subject": normalized.get("repaired_subject", ""),
        f"{p}action_match": comparison.get("action_match", False),
        f"{p}passed_match": comparison.get("passed_match", False),
        f"{p}expected_subject_types_match": comparison.get(
            "expected_subject_types_match", False
        ),
        f"{p}actual_subject_types_match": comparison.get(
            "actual_subject_types_match", False
        ),
        f"{p}error": _safe_text(error),
    }


def build_shadow_fields_from_v8_gate(
    *,
    legacy_action: str = "",
    legacy_reason: str = "",
    expected_subject_types: Any = None,
    actual_subject_types: Any = None,
    original_qtype: str = "",
    repaired_qtype: str = "",
    original_subject: str = "",
    repaired_subject: str = "",
    metadata: Any = None,
) -> Dict[str, Any]:
    """Build validation_shadow_* fields directly from legacy V8 Type Gate fields."""
    try:
        validation = build_validation_from_v8_gate(
            legacy_action=legacy_action,
            legacy_reason=legacy_reason,
            expected_subject_types=expected_subject_types,
            actual_subject_types=actual_subject_types,
            original_qtype=original_qtype,
            repaired_qtype=repaired_qtype,
            original_subject=original_subject,
            repaired_subject=repaired_subject,
            metadata=metadata,
        )
        return validation_to_shadow_fields(
            validation,
            legacy_action=legacy_action,
            expected_subject_types=expected_subject_types,
            actual_subject_types=actual_subject_types,
        )
    except Exception as e:
        return {
            f"{SHADOW_FIELD_PREFIX}available": False,
            f"{SHADOW_FIELD_PREFIX}error": type(e).__name__,
        }


def attach_shadow_fields_to_meta(meta: dict, **kwargs: Any) -> Dict[str, Any]:
    """Return a copied meta dict with validation_shadow_* fields attached."""
    out = deepcopy(meta) if isinstance(meta, dict) else {}
    out.update(build_shadow_fields_from_v8_gate(**kwargs))
    return out


def list_shadow_field_names() -> List[str]:
    """Return a copy of all standard validation shadow field names."""
    return list(SHADOW_FIELD_NAMES)


def strip_shadow_fields(result: dict) -> Dict[str, Any]:
    """Return a copy without validation_shadow_* fields."""
    if not isinstance(result, dict):
        return {}
    return {k: v for k, v in result.items() if not str(k).startswith(SHADOW_FIELD_PREFIX)}


def has_shadow_fields(result: dict) -> bool:
    """Return True if result contains any validation_shadow_* field."""
    if not isinstance(result, dict):
        return False
    return any(str(k).startswith(SHADOW_FIELD_PREFIX) for k in result)


def summarize_shadow_fields(result: dict) -> Dict[str, Any]:
    """Return only validation_shadow_* fields from a dict."""
    if not isinstance(result, dict):
        return {}
    return {k: v for k, v in result.items() if str(k).startswith(SHADOW_FIELD_PREFIX)}


__all__ = [
    "ADAPTER_VERSION",
    "SHADOW_FIELD_PREFIX",
    "SHADOW_FIELD_NAMES",
    "LEGACY_PASSING_ACTIONS",
    "LEGACY_BLOCKING_ACTIONS",
    "normalize_legacy_action",
    "legacy_action_to_passed",
    "build_validation_from_v8_gate",
    "compare_validation_with_legacy",
    "validation_to_shadow_fields",
    "build_shadow_fields_from_v8_gate",
    "attach_shadow_fields_to_meta",
    "list_shadow_field_names",
    "strip_shadow_fields",
    "has_shadow_fields",
    "summarize_shadow_fields",
    "is_validation_pass",
    "is_validation_block",
    "is_validation_repair",
]
