from typing import Any, Dict, Iterable, Mapping, Optional


__all__ = ["build_direct_schema_relation_priority_plan_from_inputs"]


def build_direct_schema_relation_priority_plan_from_inputs(
    query: Any,
    subject: Any,
    subject_types: Any,
    target_types: Any,
    registry: Optional[Iterable[Mapping[str, Any]]],
    relation_edge_hits: Any = None,
    multihop_preempt: bool = False,
) -> Dict[str, Any]:
    def as_string_set(values: Any) -> set:
        if values is None:
            return set()
        if isinstance(values, str):
            return {values} if values else set()
        if isinstance(values, (list, tuple, set)):
            return {str(x) for x in values if x}
        return set()

    def edge_hit(index: int, item: Mapping[str, Any]) -> bool:
        if relation_edge_hits is None:
            return False
        if isinstance(relation_edge_hits, Mapping):
            if index in relation_edge_hits:
                return bool(relation_edge_hits.get(index))
            key = (
                item.get("rel"),
                item.get("src_type"),
                item.get("dst_type"),
                item.get("direction"),
            )
            return bool(relation_edge_hits.get(key))
        if isinstance(relation_edge_hits, (list, tuple)):
            if 0 <= index < len(relation_edge_hits):
                return bool(relation_edge_hits[index])
        return False

    q = str(query or "").strip()
    if not q:
        return {}
    if multihop_preempt:
        return {}

    s = str(subject or "").strip()
    if not s:
        return {}

    subject_type_set = as_string_set(subject_types)
    if not subject_type_set:
        return {}

    target_type_set = as_string_set(target_types)
    if not target_type_set:
        return {}

    for index, item in enumerate(registry or []):
        st = item.get("subject_type")
        tt = item.get("target_type")
        if st not in subject_type_set or tt not in target_type_set:
            continue

        if item.get("question_type") == "product_provider" and "Policy" in target_type_set:
            continue

        if edge_hit(index, item):
            return {
                "question_type": item.get("question_type"),
                "subject": s,
                "intent_source": "direct_schema_relation_priority",
                "subject_types": sorted(subject_type_set),
                "target_type": tt,
                "schema_relation": item.get("name"),
            }

    return {}
