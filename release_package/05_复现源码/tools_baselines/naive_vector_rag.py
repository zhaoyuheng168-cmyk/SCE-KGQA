#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Vanilla BGE vector RAG over the exact frozen comparison corpus."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from common_io import call_chat_llm_with_usage, extract_answer_items
from common_prompt import RAG_SYSTEM
from retrieval import SemanticVectorIndex


_INDEX: SemanticVectorIndex | None = None


def get_index(corpus_path: Path) -> SemanticVectorIndex:
    global _INDEX
    if _INDEX is None:
        _INDEX = SemanticVectorIndex(corpus_path)
    return _INDEX


def answer(question: str, row: dict[str, str] | None = None, corpus_path: Path | None = None, top_k: int = 20, **_: Any) -> dict[str, Any]:
    if corpus_path is None:
        raise ValueError("corpus_path is required")
    hits = get_index(corpus_path).search(question, top_k=top_k)
    evidence_text = "\n\n".join(f"[{hit['rank']}] {hit.get('text', '')}" for hit in hits)
    llm = call_chat_llm_with_usage(
        RAG_SYSTEM,
        f"问题：{question}\n\n检索片段：\n{evidence_text}\n\n答案：",
    )
    text = str(llm["text"])
    return {
        "answer": extract_answer_items(text),
        "answer_text": text,
        "evidence": hits,
        "raw": {
            "top_k": top_k,
            "retriever": "bge_semantic_vector",
            "llm_usage": llm["usage"],
            "llm_model": llm["model"],
        },
    }
