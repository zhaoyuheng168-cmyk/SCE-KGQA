"""Pure multihop planner payload normalization helpers."""

from typing import Any, Dict, List


def normalize_multihop_plan_payload(
    payload: Any,
    schema_candidates: List[Dict[str, Any]],
    registry: Dict[str, Dict[str, Any]],
    *,
    min_confidence: float = 0.60,
    intent_source: str = "schema_multihop_router_llm",
    default_subject: str = "",
    default_subject_type: str = "",
) -> Dict[str, Any]:
    """Validate an LLM-selected multihop candidate and build the plan envelope."""
    if not isinstance(payload, dict):
        return {}

    is_multihop = bool(payload.get("is_multihop", False))
    candidate_id = str(payload.get("candidate_id", "") or "").strip()
    confidence = float(payload.get("confidence", 0) or 0)

    if not is_multihop:
        return {}

    allowed_candidate_ids = [
        str(c.get("candidate_id", "") or "")
        for c in schema_candidates
        if isinstance(c, dict)
    ]
    if candidate_id not in allowed_candidate_ids:
        return {}

    if confidence < float(min_confidence):
        return {}

    picked = None
    for c in schema_candidates:
        if isinstance(c, dict) and c.get("candidate_id") == candidate_id:
            picked = c
            break
    if not picked:
        return {}

    chain_id = picked["chain_id"]
    spec = registry[chain_id]

    subject = picked.get("subject", default_subject)
    subject_type = spec.get("subject_type", default_subject_type)

    return {
        "is_multihop": True,
        "chain_id": chain_id,
        "subject": subject,
        "subject_type": subject_type,
        "target_type": spec["target_type"],
        "question_type": spec["question_type"],
        "confidence": confidence,
        "reason": str(payload.get("reason", "") or ""),
        "intent_source": intent_source,
        "schema_multihop_candidate_id": candidate_id,
        "schema_multihop_candidates": schema_candidates,
        "raw": payload,
    }


__all__ = ["normalize_multihop_plan_payload"]
