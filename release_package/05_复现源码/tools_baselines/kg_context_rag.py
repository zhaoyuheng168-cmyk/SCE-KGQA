#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KG-Context RAG baseline using local KG neighborhoods without schema planner."""

from __future__ import annotations

import os
from typing import Any

from neo4j import GraphDatabase

from common_io import call_chat_llm_with_usage, extract_answer_items
from common_prompt import GRAPHRAG_SYSTEM
from strong_baseline_utils import infer_target_types, link_entities, rank_triples


def _driver():
    return GraphDatabase.driver(
        os.getenv("GTF_NEO4J_URI", "bolt://127.0.0.1:7688"),
        auth=(os.getenv("GTF_NEO4J_USER", "neo4j"), os.getenv("GTF_NEO4J_PASSWORD", "CHANGE_ME")),
    )


def _subjects(question: str, limit: int = 8) -> list[str]:
    matched = link_entities(question, limit=limit)
    subjects = [str(x.get("name") or "") for x in matched if str(x.get("name") or "")]
    return subjects[:limit]


def answer(question: str, row: dict[str, str] | None = None, top_k: int = 80, **_: Any) -> dict[str, Any]:
    subjects = _subjects(question)
    cypher = """
    MATCH p=(n)-[*1..2]-(m)
    WHERE any(name IN $subjects WHERE
      coalesce(n.name, "") CONTAINS name OR name CONTAINS coalesce(n.name, "")
    )
    WITH relationships(p) AS rels, length(p) AS distance
    UNWIND rels AS r
    WITH DISTINCT startNode(r) AS s, r AS r, endNode(r) AS o, distance
    RETURN
      coalesce(s.name, s.id, "") AS s,
      type(r) AS p,
      coalesce(o.name, o.id, "") AS o,
      labels(s)[0] AS s_type,
      labels(o)[0] AS o_type,
      distance
    LIMIT $limit
    """
    triples: list[dict[str, Any]] = []
    if subjects:
        with _driver() as driver:
            with driver.session(database=os.getenv("GTF_NEO4J_DATABASE", "neo4j")) as session:
                for record in session.run(cypher, subjects=subjects, limit=max(top_k * 6, 120)):
                    triples.append(dict(record))
    triples = rank_triples(question, triples, subjects, top_k=min(top_k, 30))
    graph_text = "\n".join(f"{t['s']} -[{t['p']}]-> {t['o']}" for t in triples)
    llm = call_chat_llm_with_usage(
        GRAPHRAG_SYSTEM,
        f"问题：{question}\n\n实体链接结果：{'、'.join(subjects)}\n"
        f"弱目标类型：{'、'.join(infer_target_types(question))}\n\n"
        f"已排序的 KG 1-2 hop local context：\n{graph_text}\n\n答案：",
    )
    text = str(llm["text"])
    return {
        "answer": extract_answer_items(text),
        "answer_text": text,
        "evidence": triples,
        "raw": {
            "baseline": "kg_context_rag",
            "cypher": cypher,
            "subjects": subjects,
            "target_types": infer_target_types(question),
            "top_k": top_k,
            "llm_usage": llm["usage"],
            "llm_model": llm["model"],
        },
    }
