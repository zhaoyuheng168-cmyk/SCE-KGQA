# -*- coding: utf-8 -*-
"""Pure CLI answer formatting helpers for V8 results."""

from typing import Any, Dict


REFUSAL_ANSWER_PREFIX = "无法回答：当前知识库未检索到足够证据。"

__all__ = ["looks_like_refusal_result", "format_answer_for_print"]


def looks_like_refusal_result(result: Dict[str, Any]) -> bool:
    route_values = [
        str(result.get("route", "")),
        str(result.get("final_route", "")),
        str(result.get("answer_source", "")),
    ]
    if result.get("is_refusal") is True:
        return True
    if any("refuse" in v or "unsupported" in v for v in route_values):
        return True
    answer = str(result.get("answer", ""))
    refusal_phrases = [
        "无法给出可靠答案",
        "未检索到",
        "暂不支持",
        "不支持该问句",
        "当前系统无法处理",
        "拒绝降级为单跳回答",
    ]
    return any(p in answer for p in refusal_phrases)


def format_answer_for_print(result: Dict[str, Any]) -> str:
    answer = str(result.get("answer", ""))
    if not looks_like_refusal_result(result):
        return answer
    if answer.startswith(REFUSAL_ANSWER_PREFIX) or answer.startswith("无法回答"):
        return answer
    return f"{REFUSAL_ANSWER_PREFIX}\n{answer}"
