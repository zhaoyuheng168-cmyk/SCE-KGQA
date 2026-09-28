"""Pure schema single-hop candidate assembly helpers."""

from typing import Any, Dict, List


__all__ = ["build_schema_singlehop_candidates_from_inputs"]


def build_schema_singlehop_candidates_from_inputs(
    query: Any,
    subject_candidates: Any,
    subject_types_by_subject: Any,
    registry: Any,
    should_skip_result: bool = False,
) -> List[Dict[str, Any]]:
    q = str(query or "").strip()
    if not q:
        return []
    if not subject_candidates:
        return []
    if should_skip_result:
        return []

    type_map = subject_types_by_subject or {}
    candidates = []

    for subject in subject_candidates:
        raw_subject_types = type_map.get(subject)
        if isinstance(raw_subject_types, str):
            value = raw_subject_types.strip()
            subject_types = [value] if value else []
        elif isinstance(raw_subject_types, (list, tuple, set)):
            subject_types = []
            for item in raw_subject_types:
                value = str(item or "").strip()
                if value:
                    subject_types.append(value)
        else:
            subject_types = []
        if not subject_types:
            continue

        subject_type_lookup = set(subject_types)
        for route in registry or []:
            wanted_type = str(route.get("subject_type", "") or "").strip()
            if not wanted_type:
                continue
            if wanted_type not in subject_type_lookup:
                continue

            candidate_id = f"c{len(candidates) + 1}"
            candidates.append({
                "candidate_id": candidate_id,
                "subject": subject,
                "subject_types": sorted(subject_types),
                "question_type": route["question_type"],
                "target_type": route.get("target_type", ""),
                "rel": route.get("rel", ""),
                "direction": route.get("direction", ""),
                "description": route.get("description", ""),
                "semantic_goal": route.get("semantic_goal", ""),
                "positive_intents": route.get("positive_intents", []),
                "negative_intents": route.get("negative_intents", []),
                "natural_phrases": route.get("natural_phrases", []),
                "confusable_with": route.get("confusable_with", []),
                "examples": route.get("examples", []),
                "route": route,
            })

    return candidates
