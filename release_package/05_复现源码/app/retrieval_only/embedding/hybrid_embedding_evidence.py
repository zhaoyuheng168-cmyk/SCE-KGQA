# -*- coding: utf-8 -*-
"""Optional evidence support interfaces for Stage EMB ablations.

These helpers are assist-only and are not part of the recommended main
pipeline. They must not decide final answers or replace graph_answers from the
controlled KGQA pipeline.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from embedding_config import get_embedding_config
from embedding_assist_wrapper import assist_retrieve
from graph_answer_reranker import rerank_graph_answers
from embedding_retriever import retrieve_evidence


def get_embedding_evidence_support(question: str, top_k: int = 5) -> Dict[str, object]:
    cfg = get_embedding_config()
    if not cfg["enable_embedding"] or not cfg["enable_embedding_evidence"]:
        return {
            "used": False,
            "answer_source": "embedding_evidence_disabled",
            "retrieved_chunks": [],
            "support_text": "",
        }
    chunks = retrieve_evidence(
        question,
        top_k=top_k,
        min_score=float(cfg["evidence_min_score"]),
    )
    support_text = "\n\n".join(str(item.get("text", "")) for item in chunks)
    return {
        "used": bool(chunks),
        "answer_source": "embedding_evidence_support",
        "is_final_answer": False,
        "retrieved_chunks": chunks,
        "support_text": support_text,
    }


def get_embedding_assist_for_graph_answers(
    question: str,
    subject: str,
    relation: str,
    graph_answers: Optional[List[str]] = None,
    top_k: int = 5,
    min_score: Optional[float] = None,
) -> Dict[str, object]:
    """Return evidence candidates for KG-confirmed graph answers.

    This is the preferred future V8 integration boundary:
    V8/KG decides qtype, subject, relation, and graph_answers first; embedding
    only retrieves supporting evidence candidates for those confirmed facts.
    """

    cfg = get_embedding_config()
    disabled = not cfg["enable_embedding"] or not cfg["enable_embedding_evidence"]
    base = {
        "enabled": not disabled,
        "used_as_assist": False,
        "is_final_answer": False,
        "answer_policy": "embedding_assist_only_kgqa_final_answer_must_come_from_graph_or_controlled_pipeline",
        "subject": subject,
        "relation": relation,
        "graph_answers": graph_answers or [],
        "evidence_groups": [],
    }
    if disabled:
        base["reason"] = "embedding_evidence_disabled"
        return base
    if not subject or not relation:
        base["reason"] = "missing_subject_or_relation"
        return base

    result = assist_retrieve(
        question,
        entity_filters=[subject],
        relation_filters=[relation],
        graph_answers=graph_answers or [],
        evidence_top_k=top_k,
        evidence_min_score=min_score if min_score is not None else float(cfg["evidence_min_score"]),
    )
    return {
        **base,
        "used_as_assist": bool(result.get("used_as_assist")),
        "kg_confirmed_mode": bool(result.get("kg_confirmed_mode")),
        "entity_filters": result.get("entity_filters", []),
        "relation_filters": result.get("relation_filters", []),
        "graph_answer_filters": result.get("graph_answer_filters", []),
        "selection_reason": result.get("selection_reason", {}),
        "evidence_groups": result.get("evidence_groups", []),
        "notes": result.get("notes", []),
    }


def get_embedding_rerank_for_graph_answers(
    question: str,
    graph_answers: List[object],
    context: str = "",
    top_n: Optional[int] = None,
) -> Dict[str, object]:
    """Return an assist-only embedding rerank for existing graph answers."""

    return rerank_graph_answers(question, graph_answers, context=context, top_n=top_n)


__all__ = [
    "get_embedding_evidence_support",
    "get_embedding_assist_for_graph_answers",
    "get_embedding_rerank_for_graph_answers",
]
