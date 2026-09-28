#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LLM with retrieved evidence chunks as prompt context.

This is a bridge baseline between LLM-only and full RAG/KGQA: it injects
retrieved evidence text into the same LLM, but does not use KG triples,
schema routing, graph execution, or multi-hop planning.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from common_io import call_chat_llm_with_usage, extract_answer_items
from common_prompt import EVIDENCE_ONLY_SYSTEM
from retrieval import CorpusIndex


_INDEX: CorpusIndex | None = None


def get_index(corpus_path: Path) -> CorpusIndex:
    global _INDEX
    if _INDEX is None:
        _INDEX = CorpusIndex(corpus_path)
    return _INDEX


def answer(question: str, row: dict[str, str] | None = None, corpus_path: Path | None = None, top_k: int = 20, **_: Any) -> dict[str, Any]:
    if corpus_path is None:
        raise ValueError("corpus_path is required")
    hits = get_index(corpus_path).bm25(question, top_k=top_k)
    evidence_text = "\n\n".join(f"[{h['rank']}] {h.get('text', '')}" for h in hits)
    llm = call_chat_llm_with_usage(
        EVIDENCE_ONLY_SYSTEM,
        f"问题：{question}\n\n候选证据：\n{evidence_text}\n\n答案：",
    )
    text = str(llm["text"])
    return {
        "answer": extract_answer_items(text),
        "answer_text": text,
        "evidence": hits,
        "raw": {
            "top_k": top_k,
            "corpus_mode": "evidence_only",
            "retriever": "vanilla_bm25",
            "llm_usage": llm["usage"],
            "llm_model": llm["model"],
        },
    }
