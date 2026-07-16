"""Pure Type Gate qtype-subject-type consistency helpers."""

from typing import Any, Dict, List


def _normalize_type_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, set):
        return sorted(str(v).strip() for v in value if str(v or "").strip())
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v or "").strip()]
    text = str(value or "").strip()
    if not text:
        return []
    return [part.strip() for part in text.split("||") if part.strip()]


def _normalize_type_name_for_match(value: Any) -> str:
    text = str(value or "").strip()
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


def _type_sets_match(actual: List[str], expected: List[str]) -> bool:
    normalized_actual = {
        _normalize_type_name_for_match(item) for item in actual if str(item or "").strip()
    }
    normalized_expected = {
        _normalize_type_name_for_match(item) for item in expected if str(item or "").strip()
    }
    return bool(normalized_actual & normalized_expected)


def decide_qtype_subject_type_consistency(
    qtype: str,
    subject_types: Any,
    expected_subject_types: Any,
) -> Dict[str, Any]:
    """Return the pure pass/block decision for qtype and subject type sets."""
    qtype = str(qtype or "").strip()
    actual = _normalize_type_list(subject_types)
    expected = _normalize_type_list(expected_subject_types)

    if not qtype:
        return {
            "action": "pass",
            "reason": "empty_qtype_or_subject_pass",
            "qtype": qtype,
            "expected_subject_types": expected,
            "subject_types": actual,
        }

    if not expected:
        return {
            "action": "pass",
            "reason": "qtype_not_registered_pass",
            "qtype": qtype,
            "expected_subject_types": expected,
            "subject_types": actual,
        }

    if not actual:
        return {
            "action": "pass",
            "reason": "subject_type_unknown_pass",
            "qtype": qtype,
            "expected_subject_types": expected,
            "subject_types": actual,
        }

    if _type_sets_match(actual, expected):
        return {
            "action": "pass",
            "reason": "subject_type_consistent",
            "qtype": qtype,
            "expected_subject_types": expected,
            "subject_types": actual,
        }

    return {
        "action": "block",
        "reason": "subject_type_mismatch_block",
        "qtype": qtype,
        "expected_subject_types": expected,
        "subject_types": actual,
    }


__all__ = ["decide_qtype_subject_type_consistency"]
