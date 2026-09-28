#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""External GraphRAG-style baseline.

This is a framework-inspired baseline for environments where the Microsoft
GraphRAG package is not installed. It uses frozen KG-derived graph context and
community-like local neighborhoods, but does not call SCE-KGQA's router,
planner, gates, KAG fallback, reranker, or validation chain.
"""

from __future__ import annotations

from typing import Any

from common_io import call_chat_llm_with_usage, extract_answer_items
from common_prompt import GRAPHRAG_SYSTEM
from schema_utils import match_entities, structured_schema_answer


def answer(question: str, row: dict[str, str] | None = None, top_k: int = 80, **_: Any) -> dict[str, Any]:
    schema = structured_schema_answer(question, top_k=top_k)
    if schema:
        triples = [
            f"{t.get('s', '')} -[{t.get('p', '')}]-> {t.get('o', '')}"
            for t in schema.get("evidence", [])
        ]
        answers = [str(x) for x in schema.get("answer", []) if str(x).strip()]
        graph_text = "\n".join(triples)
        if answers:
            answer_text = "、".join(answers)
            graph_text = (graph_text + "\n" if graph_text else "") + f"KG候选答案列表：{answer_text}"
        matched = schema.get("raw", {})
    else:
        entities = match_entities(question, limit=10)
        contexts: list[str] = []
        for ent in entities:
            name = str(ent.get("name") or "")
            for ctx in (ent.get("relation_contexts") or [])[:20]:
                contexts.append(f"{name}: {ctx}")
        graph_text = "\n".join(contexts[:top_k])
        matched = {"matched_entities": [e.get("name") for e in entities]}

    llm = call_chat_llm_with_usage(
        GRAPHRAG_SYSTEM,
        "问题：{question}\n\nGraphRAG-style local graph context:\n{graph_text}".format(
            question=question,
            graph_text=graph_text,
        ),
    )
    text = str(llm["text"])
    return {
        "answer": extract_answer_items(text),
        "answer_text": text,
        "evidence": graph_text.splitlines(),
        "raw": {"framework_style": "external_graphrag", **matched, "llm_usage": llm["usage"], "llm_model": llm["model"]},
    }
