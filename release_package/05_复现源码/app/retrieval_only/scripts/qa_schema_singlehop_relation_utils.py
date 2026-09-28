"""
Pure relation-decision helpers for V8 schema single-hop routing.

This module must not import V8 runtime code, relation JSON loaders, Neo4j, LLM
clients, filesystem helpers, or environment configuration. V8 wrappers compute
relation JSON state and compare module results with legacy results before use.
"""

from typing import Any, Dict, Optional

__all__ = ["schema_singlehop_edge_valid"]


def schema_singlehop_edge_valid(
    subject: Any,
    route: Dict[str, Any],
    *,
    relation_json_loaded: Optional[bool] = None,
    edge_exists: Optional[bool] = None,
    edge_check_error: bool = False,
) -> bool:
    """
    Decide whether a schema single-hop route passes edge validation.

    This is a pure decision function. It does not load relation JSON or check
    graph edges directly.
    """
    if not route.get("require_edge", False):
        return True

    rel = str(route.get("rel", "") or "").strip()
    if not rel or "/" in rel:
        return True

    if edge_check_error:
        return True

    if relation_json_loaded is False:
        return True

    return bool(edge_exists)
