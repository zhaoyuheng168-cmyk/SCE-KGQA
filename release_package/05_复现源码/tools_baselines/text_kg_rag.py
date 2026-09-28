#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Text+KG RAG baseline over merged evidence chunks and textualized triples."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from common_io import call_chat_llm_with_usage, extract_answer_items
from common_prompt import TEXT_KG_RAG_SYSTEM
from retrieval import CorpusIndex


_INDEX: CorpusIndex | None = None


def get_index(corpus_path: Path) -> CorpusIndex:
    global _INDEX
    if _INDEX is None:
        _INDEX = CorpusIndex(corpus_path)
    return _INDEX


def answer(question: str, row: dict[str, str] | None = None, corpus_path: Path | None = None, top_k: int = 30, **_: Any) -> dict[str, Any]:
    if corpus_path is None:
        raise ValueError("corpus_path is required")
    hits = get_index(corpus_path).bm25(question, top_k=top_k)
    context = "\n\n".join(f"[{h['rank']}] source={h.get('source_type', '')}\n{h.get('text', '')}" for h in hits)
    llm = call_chat_llm_with_usage(
        TEXT_KG_RAG_SYSTEM,
        f"问题：{question}\n\n上下文：\n{context}\n\n答案：",
    )
    text = str(llm["text"])
    return {
        "answer": extract_answer_items(text),
        "answer_text": text,
        "evidence": hits,
        "raw": {
            "retriever": "bm25_text_kg_merged",
            "top_k": top_k,
            "llm_usage": llm["usage"],
            "llm_model": llm["model"],
        },
    }
