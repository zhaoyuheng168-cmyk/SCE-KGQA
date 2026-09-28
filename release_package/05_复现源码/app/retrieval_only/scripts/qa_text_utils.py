# -*- coding: utf-8 -*-
"""Pure text/list helpers for V8."""

import re
from typing import List


__all__ = ["norm", "unique", "contains_answer"]


def norm(s: str) -> str:
    s = str(s or "")
    s = re.sub(r"\s+", "", s)
    s = s.replace("（", "(").replace("）", ")").replace("“", "").replace("”", "")
    return s


def unique(vals: List[str]) -> List[str]:
    out = []
    for v in vals:
        v = str(v or "").strip()
        if v and v not in out:
            out.append(v)
    return out


def contains_answer(answer: str, vals: List[str]) -> bool:
    a = norm(answer)
    return any(norm(v) and norm(v) in a for v in vals)
