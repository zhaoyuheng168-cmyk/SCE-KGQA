#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Any

from common_io import call_chat_llm_with_usage, extract_answer_items
from common_prompt import LLM_ONLY_SYSTEM


def answer(question: str, row: dict[str, str] | None = None, **_: Any) -> dict[str, Any]:
    llm = call_chat_llm_with_usage(LLM_ONLY_SYSTEM, f"问题：{question}")
    text = str(llm["text"])
    return {
        "answer": extract_answer_items(text),
        "answer_text": text,
        "evidence": [],
        "raw": {"llm_usage": llm["usage"], "llm_model": llm["model"]},
    }
