"""
Pure result-shape helpers for V8 answer routing.

This module must not import V8 runtime code, Neo4j, LLM clients, or filesystem
side-effect modules. It mirrors the V8 legacy result item counter exactly.
"""

from typing import Any, Dict

__all__ = ["result_item_count"]


def result_item_count(res: Dict[str, Any]) -> int:
    """
    Count answer items from different result shapes.
    This helper does not inspect question surface forms.
    """
    try:
        if not isinstance(res, dict):
            return 0

        vals = res.get("answers")
        if isinstance(vals, (list, tuple, set)):
            return len([x for x in vals if str(x or "").strip()])

        for key in ["graph_answers", "kag_answers", "pred_items"]:
            v = res.get(key)
            if isinstance(v, (list, tuple, set)):
                return len([x for x in v if str(x or "").strip()])
            if isinstance(v, str) and v.strip():
                if "||" in v:
                    return len([x for x in v.split("||") if x.strip()])
                if "、" in v:
                    return len([x for x in v.split("、") if x.strip()])
                return 1

        ans = res.get("answer")
        if isinstance(ans, str) and ans.strip():
            return 1

        return 0
    except Exception:
        return 0
