# -*- coding: utf-8 -*-
"""Small graph-answer helpers shared by the V8 graph answer path."""

from typing import Any, Dict, List


def extract_graph_answers_from_rows(rows: List[Dict[str, Any]], key: str) -> List[str]:
    out = []
    for row in rows:
        value = str(row.get(key) or "").strip()
        if value and value not in out:
            out.append(value)
    return out


__all__ = [
    "extract_graph_answers_from_rows",
]
