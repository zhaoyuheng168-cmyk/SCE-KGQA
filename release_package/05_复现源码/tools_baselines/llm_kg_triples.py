#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LLM with retrieved KG triples verbalized as prompt context.

This baseline follows the common KGQA knowledge-injection setting: retrieve
relevant triples from a textualized KG corpus, prepend them to the prompt, and
let the same LLM answer without schema routing or graph execution.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from common_io import call_chat_llm_with_usage, extract_answer_items
from common_prompt import KG_TRIPLES_SYSTEM
from retrieval import CorpusIndex


_INDEX: CorpusIndex | None = None


def get_index(corpus_path: Path) -> CorpusIndex:
    global _INDEX
    if _INDEX is None:
        _INDEX = CorpusIndex(corpus_path)
    return _INDEX


def answer(question: str, row: dict[str, str] | None = None, corpus_path: Path | None = None, top_k: int = 40, **_: Any) -> dict[str, Any]:
    if corpus_path is None:
        raise ValueError("corpus_path is required")
    hits = get_index(corpus_path).bm25(question, top_k=top_k)
    triples_text = "\n".join(f"[{h['rank']}] {h.get('text', '')}" for h in hits)
    llm = call_chat_llm_with_usage(
        KG_TRIPLES_SYSTEM,
        f"问题：{question}\n\n候选KG三元组：\n{triples_text}\n\n答案：",
    )
    text = str(llm["text"])
    return {
        "answer": extract_answer_items(text),
        "answer_text": text,
        "evidence": hits,
        "raw": {
            "top_k": top_k,
            "corpus_mode": "kg_triples_only",
            "retriever": "vanilla_bm25",
            "llm_usage": llm["usage"],
            "llm_model": llm["model"],
        },
    }
