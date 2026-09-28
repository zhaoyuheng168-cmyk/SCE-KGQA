# -*- coding: utf-8 -*-
"""
Type Gate module shell.

This module only normalizes shadow data structures and reports module audit
status. It does not execute Type Gate decisions or call runtime services.
"""

from typing import Any, Dict, List


TYPE_GATE_MODULE_VERSION = "4P_module_shell_v1"
DEFAULT_SHADOW_AUDIT_FIELDS = [
    "question_type",
    "subject",
    "intent_source",
    "type_gate_action",
    "type_gate_reason",
    "type_gate_original_qtype",
    "type_gate_original_subject",
    "type_gate_expected_subject_types",
    "type_gate_subject_types",
]


def normalize_type_list(value: Any) -> List[str]:
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


def build_shadow_context(
    qtype: str,
    subject: str,
    intent_source: str = "",
    query: str = "",
) -> Dict[str, Any]:
    return {
        "query": str(query or ""),
        "qtype": str(qtype or "").strip(),
        "subject": str(subject or "").strip(),
        "intent_source": str(intent_source or "").strip(),
    }


def build_shadow_result(result: Any) -> Dict[str, Any]:
    source = dict(result or {}) if isinstance(result, dict) else {}
    return {
        "question_type": str(source.get("question_type", "") or ""),
        "subject": str(source.get("subject", "") or ""),
        "intent_source": str(source.get("intent_source", "") or ""),
        "type_gate_action": str(source.get("type_gate_action", "") or ""),
        "type_gate_reason": str(source.get("type_gate_reason", "") or ""),
        "type_gate_original_qtype": str(source.get("type_gate_original_qtype", "") or ""),
        "type_gate_original_subject": str(source.get("type_gate_original_subject", "") or ""),
        "type_gate_expected_subject_types": normalize_type_list(
            source.get("type_gate_expected_subject_types", [])
        ),
        "type_gate_subject_types": normalize_type_list(source.get("type_gate_subject_types", [])),
    }


def build_shadow_audit(
    legacy_result: Any,
    shadow_result: Any = None,
    fields: Any = None,
) -> Dict[str, Any]:
    legacy = build_shadow_result(legacy_result)
    shadow = build_shadow_result(legacy_result) if shadow_result is None else build_shadow_result(shadow_result)
    checked_fields = normalize_type_list(fields) or list(DEFAULT_SHADOW_AUDIT_FIELDS)
    missing_fields = []
    diffs = []

    for field in checked_fields:
        if field not in legacy:
            missing_fields.append(field)
            continue
        legacy_value = legacy.get(field)
        shadow_value = shadow.get(field)
        if legacy_value != shadow_value:
            diffs.append({
                "field": field,
                "legacy": legacy_value,
                "shadow": shadow_value,
            })

    shadow_result_ok = isinstance(shadow, dict) and all(field in shadow for field in checked_fields)
    return {
        "ok": not missing_fields and not diffs and shadow_result_ok,
        "checked_fields": checked_fields,
        "missing_fields": missing_fields,
        "diffs": diffs,
        "shadow_result_ok": shadow_result_ok,
    }


def build_shadow_bundle(
    legacy_result: Any,
    *,
    qtype: str = "",
    subject: str = "",
    intent_source: str = "",
    query: str = "",
    fields: Any = None,
) -> Dict[str, Any]:
    try:
        shadow_context = build_shadow_context(
            qtype=qtype,
            subject=subject,
            intent_source=intent_source,
            query=query,
        )
        shadow_result = build_shadow_result(legacy_result)
        shadow_audit = build_shadow_audit(legacy_result, shadow_result, fields)
        return {
            "ok": bool(shadow_audit.get("ok") is True),
            "context": shadow_context,
            "result": shadow_result,
            "audit": shadow_audit,
            "error": "",
        }
    except Exception as e:
        return {
            "ok": False,
            "context": {},
            "result": {},
            "audit": {},
            "error": type(e).__name__,
        }


def build_type_gate_decision(
    action: str,
    reason: str,
    original_qtype: str = "",
    expected_subject_types=None,
    actual_subject_types=None,
    repaired_qtype: str = "",
    repaired_subject: str = "",
    original_subject: str = "",
    metadata=None,
) -> Dict[str, Any]:
    return {
        "action": str(action or ""),
        "reason": str(reason or ""),
        "original_qtype": str(original_qtype or ""),
        "expected_subject_types": normalize_type_list(expected_subject_types),
        "actual_subject_types": normalize_type_list(actual_subject_types),
        "repaired_qtype": str(repaired_qtype or ""),
        "repaired_subject": str(repaired_subject or ""),
        "original_subject": str(original_subject or ""),
        "metadata": dict(metadata) if isinstance(metadata, dict) else {},
    }


def apply_type_gate_decision_to_base(
    base: Dict[str, Any],
    decision: Dict[str, Any],
    *,
    question_type: str = "",
    subject: str = "",
    intent_source: str = "",
) -> Dict[str, Any]:
    result = dict(base or {})
    decision = dict(decision or {})

    action = str(decision.get("action", "") or "")
    reason = str(decision.get("reason", "") or "")
    if action:
        result["type_gate_action"] = action
    if reason:
        result["type_gate_reason"] = reason

    original_qtype = str(decision.get("original_qtype", "") or "")
    original_subject = str(decision.get("original_subject", "") or "")
    if original_qtype:
        result["type_gate_original_qtype"] = original_qtype
    if original_subject:
        result["type_gate_original_subject"] = original_subject

    result["type_gate_expected_subject_types"] = list(
        decision.get("expected_subject_types", []) or []
    )
    result["type_gate_subject_types"] = list(decision.get("actual_subject_types", []) or [])

    if action == "repair":
        repaired_qtype = str(decision.get("repaired_qtype", "") or "")
        repaired_subject = str(decision.get("repaired_subject", "") or "")
        result["question_type"] = repaired_qtype or str(
            question_type or result.get("question_type", "") or ""
        )
        result["subject"] = repaired_subject or str(subject or result.get("subject", "") or "")
        result["intent_source"] = str(intent_source or result.get("intent_source", "") or "")

    return result


def join_type_gate_meta_types(value: Any) -> str:
    items = normalize_type_list(value)
    return "||".join(items)


def build_type_gate_legacy_meta(
    action: str,
    reason: str,
    original_qtype: str,
    expected_subject_types=None,
    actual_subject_types=None,
    original_subject: str = "",
    **extra_fields,
) -> Dict[str, Any]:
    meta = {
        "v8_type_gate_action": str(action or ""),
        "v8_type_gate_reason": str(reason or ""),
        "v8_type_gate_original_qtype": str(original_qtype or ""),
        "v8_type_gate_expected_subject_types": join_type_gate_meta_types(expected_subject_types),
        "v8_type_gate_subject_types": join_type_gate_meta_types(actual_subject_types),
    }
    for key, value in (extra_fields or {}).items():
        if str(key or "").startswith("v8_type_gate_"):
            meta[key] = value
    return meta


def build_validation_result_from_legacy_meta(
    legacy_meta: Dict[str, Any],
) -> Dict[str, Any]:
    legacy_meta = dict(legacy_meta or {}) if isinstance(legacy_meta, dict) else {}
    action = str(legacy_meta.get("v8_type_gate_action", "") or "").strip()
    if action not in {"pass", "block", "repair", "unknown"}:
        action = "unknown"

    return {
        "validation_action": action,
        "validation_reason": str(legacy_meta.get("v8_type_gate_reason", "") or "").strip(),
        "validation_passed": action in {"pass", "repair"},
        "expected_subject_types": normalize_type_list(
            legacy_meta.get("v8_type_gate_expected_subject_types", "")
        ),
        "actual_subject_types": normalize_type_list(
            legacy_meta.get("v8_type_gate_subject_types", "")
        ),
        "original_qtype": str(legacy_meta.get("v8_type_gate_original_qtype", "") or "").strip(),
        "repaired_qtype": "",
        "original_subject": str(
            legacy_meta.get("v8_type_gate_original_subject", "") or ""
        ).strip(),
        "repaired_subject": "",
        "metadata": {},
    }


def audit_type_gate_module() -> Dict[str, Any]:
    required_exports = [
        "TYPE_GATE_MODULE_VERSION",
        "normalize_type_list",
        "build_shadow_context",
        "build_shadow_result",
        "build_shadow_audit",
        "build_shadow_bundle",
        "build_type_gate_decision",
        "apply_type_gate_decision_to_base",
        "join_type_gate_meta_types",
        "build_type_gate_legacy_meta",
        "build_validation_result_from_legacy_meta",
        "audit_type_gate_module",
    ]
    available_exports = globals()
    missing = [name for name in required_exports if name not in available_exports]
    smoke_types = normalize_type_list("Entity||Policy")
    smoke_context = build_shadow_context(
        qtype="policy_supports_product",
        subject="示例政策",
        intent_source="audit",
        query="示例政策支持哪些产品？",
    )
    smoke_result = build_shadow_result({
        "type_gate_action": "pass",
        "type_gate_expected_subject_types": ["Policy"],
        "type_gate_subject_types": ["Entity", "Policy"],
    })
    smoke_audit = build_shadow_audit(smoke_result)
    smoke_bundle = build_shadow_bundle(
        smoke_result,
        qtype="policy_supports_product",
        subject="示例政策",
        intent_source="audit",
        query="示例政策支持哪些产品？",
    )
    smoke_decision = build_type_gate_decision(
        action="pass",
        reason="subject_type_consistent",
        original_qtype="policy_supports_product",
        expected_subject_types="Policy",
        actual_subject_types="Entity||Policy",
        original_subject="示例政策",
    )
    smoke_base = {
        "question_type": "policy_supports_product",
        "subject": "示例政策",
        "intent_source": "audit",
        "type_gate_action": "pass",
    }
    smoke_apply_pass = apply_type_gate_decision_to_base(smoke_base, smoke_decision)
    smoke_apply_repair = apply_type_gate_decision_to_base(
        smoke_base,
        build_type_gate_decision(
            action="repair",
            reason="repair_policy_product_forward",
            original_qtype="product_supported_by_policies",
            expected_subject_types=["FinancialProduct"],
            actual_subject_types=["Entity", "Policy"],
            repaired_qtype="policy_supports_product",
            repaired_subject="示例政策",
            original_subject="示例政策",
        ),
        intent_source="audit_repair",
    )
    smoke_apply_block = apply_type_gate_decision_to_base(
        smoke_base,
        build_type_gate_decision(
            action="block",
            reason="subject_type_mismatch_block",
            original_qtype="policy_supports_product",
            expected_subject_types=["Policy"],
            actual_subject_types=["FinancialProduct"],
            original_subject="示例产品",
        ),
    )
    smoke_meta = build_type_gate_legacy_meta(
        action="pass",
        reason="subject_type_consistent",
        original_qtype="policy_supports_product",
        expected_subject_types=["Policy"],
        actual_subject_types=["Entity", "Policy"],
        v8_type_gate_original_subject="示例政策",
    )
    smoke_validation_pass = build_validation_result_from_legacy_meta(smoke_meta)
    smoke_validation_block = build_validation_result_from_legacy_meta(
        build_type_gate_legacy_meta(
            action="block",
            reason="subject_type_mismatch_block",
            original_qtype="policy_supports_product",
            expected_subject_types=["Policy"],
            actual_subject_types=["FinancialProduct"],
            v8_type_gate_original_subject="示例产品",
        )
    )
    return {
        "ok": not missing
        and smoke_types == ["Entity", "Policy"]
        and smoke_context.get("qtype") == "policy_supports_product"
        and smoke_result.get("type_gate_action") == "pass"
        and smoke_audit.get("ok") is True
        and smoke_bundle.get("ok") is True
        and smoke_decision.get("action") == "pass"
        and smoke_decision.get("expected_subject_types") == ["Policy"]
        and smoke_decision.get("actual_subject_types") == ["Entity", "Policy"]
        and smoke_apply_pass.get("type_gate_action") == "pass"
        and smoke_apply_repair.get("question_type") == "policy_supports_product"
        and smoke_apply_block.get("type_gate_action") == "block"
        and smoke_meta.get("v8_type_gate_action") == "pass"
        and smoke_meta.get("v8_type_gate_expected_subject_types") == "Policy"
        and smoke_meta.get("v8_type_gate_subject_types") == "Entity||Policy"
        and smoke_meta.get("v8_type_gate_original_subject") == "示例政策"
        and smoke_validation_pass.get("validation_action") == "pass"
        and smoke_validation_pass.get("validation_passed") is True
        and smoke_validation_pass.get("actual_subject_types") == ["Entity", "Policy"]
        and smoke_validation_block.get("validation_action") == "block"
        and smoke_validation_block.get("validation_passed") is False,
        "version": TYPE_GATE_MODULE_VERSION,
        "missing_exports": missing,
        "responsibility": "type_gate_pure_structure_helpers_only",
    }


__all__ = [
    "TYPE_GATE_MODULE_VERSION",
    "normalize_type_list",
    "build_shadow_context",
    "build_shadow_result",
    "build_shadow_audit",
    "build_shadow_bundle",
    "build_type_gate_decision",
    "apply_type_gate_decision_to_base",
    "join_type_gate_meta_types",
    "build_type_gate_legacy_meta",
    "build_validation_result_from_legacy_meta",
    "audit_type_gate_module",
]
