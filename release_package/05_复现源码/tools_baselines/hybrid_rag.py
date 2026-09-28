#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HybridRAG baseline with BM25 + vector retrieval fusion over Text+KG corpus."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from common_io import call_chat_llm_with_usage, extract_answer_items
from common_prompt import TEXT_KG_RAG_SYSTEM
from retrieval import CorpusIndex, SemanticVectorIndex


_INDEX: CorpusIndex | None = None
_VECTOR_INDEX: SemanticVectorIndex | None = None


def get_index(corpus_path: Path) -> CorpusIndex:
    global _INDEX
    if _INDEX is None:
        _INDEX = CorpusIndex(corpus_path)
    return _INDEX


def get_vector_index(corpus_path: Path) -> SemanticVectorIndex:
    global _VECTOR_INDEX
    if _VECTOR_INDEX is None:
        _VECTOR_INDEX = SemanticVectorIndex(corpus_path)
    return _VECTOR_INDEX


def _rrf_merge(hit_lists: list[list[dict[str, Any]]], top_k: int, k: int = 60) -> list[dict[str, Any]]:
    scores: dict[str, float] = {}
    docs: dict[str, dict[str, Any]] = {}
    for hits in hit_lists:
        for h in hits:
            doc_id = str(h.get("doc_id") or h.get("metadata", {}).get("source_file") or h.get("text", ""))
            if not doc_id:
                continue
            docs.setdefault(doc_id, h)
            rank = int(h.get("rank") or len(docs))
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
    out: list[dict[str, Any]] = []
    for rank, (doc_id, score) in enumerate(ranked, 1):
        doc = dict(docs[doc_id])
        doc["rank"] = rank
        doc["hybrid_score"] = score
        out.append(doc)
    return out


def answer(question: str, row: dict[str, str] | None = None, corpus_path: Path | None = None, top_k: int = 30, **_: Any) -> dict[str, Any]:
    if corpus_path is None:
        raise ValueError("corpus_path is required")
    index = get_index(corpus_path)
    bm25_hits = index.bm25(question, top_k=top_k)
    vector_hits = get_vector_index(corpus_path).search(question, top_k=top_k)
    hits = _rrf_merge([bm25_hits, vector_hits], top_k=top_k)
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
            "retriever": "bm25+bge_vector_rrf",
            "top_k": top_k,
            "bm25_hits": len(bm25_hits),
            "vector_hits": len(vector_hits),
            "llm_usage": llm["usage"],
            "llm_model": llm["model"],
        },
    }
