"""Pure relation JSON index checks for V8 routing helpers."""

from typing import Any, Dict


def relation_json_subject_has_edge_from_index(
    idx: Dict[str, Any],
    subject: Any,
    rel: Any,
    src_type: Any = "",
    dst_type: Any = "",
    direction: Any = "",
) -> bool:
    subject = str(subject or "").strip()
    if not subject:
        return False

    idx = idx or {}
    ids = set((idx.get("name_to_ids") or {}).get(subject, set()))
    if not ids:
        for name, node_ids in (idx.get("name_to_ids") or {}).items():
            if name and (name in subject or subject in name):
                ids |= set(node_ids)

    rel = str(rel or "").strip()
    src_type = str(src_type or "").strip()
    dst_type = str(dst_type or "").strip()
    direction = str(direction or "").strip()

    for nid in ids:
        for edge in (idx.get("edges_by_node") or {}).get(nid, []):
            if rel and edge.get("rel") != rel:
                continue
            if direction and edge.get("direction") != direction:
                continue
            if src_type and edge.get("src_type") != src_type:
                continue
            if dst_type and edge.get("dst_type") != dst_type:
                continue
            return True

    return False


__all__ = ["relation_json_subject_has_edge_from_index"]
