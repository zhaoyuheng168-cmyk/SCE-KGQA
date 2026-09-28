#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import os
from typing import Any

from neo4j import GraphDatabase

from common_io import call_chat_llm_with_usage, extract_answer_items, split_items
from common_prompt import GRAPHRAG_SYSTEM
from schema_utils import match_entities, structured_schema_answer


def _driver():
    return GraphDatabase.driver(
        os.getenv("GTF_NEO4J_URI", "bolt://127.0.0.1:7688"),
        auth=(os.getenv("GTF_NEO4J_USER", "neo4j"), os.getenv("GTF_NEO4J_PASSWORD", "CHANGE_ME")),
    )


def answer(question: str, row: dict[str, str] | None = None, top_k: int = 80, **_: Any) -> dict[str, Any]:
    row = row or {}
    schema_result = structured_schema_answer(question, top_k=top_k)
    if schema_result:
        graph_text = "\n".join(
            f"{t.get('s', '')} -[{t.get('p', '')}]-> {t.get('o', '')}"
            for t in schema_result.get("evidence", [])
        )
        if not graph_text:
            graph_text = "、".join(schema_result.get("answer", []))
        llm = call_chat_llm_with_usage(
            GRAPHRAG_SYSTEM,
            f"问题：{question}\n\nSchema-constrained candidate subgraph / answers：\n{graph_text}",
        )
        text = str(llm["text"])
        return {
            "answer": extract_answer_items(text),
            "answer_text": text,
            "evidence": schema_result.get("evidence", []),
            "raw": {
                **schema_result.get("raw", {}),
                "schema_constrained_graphrag": True,
                "llm_usage": llm["usage"],
                "llm_model": llm["model"],
            },
        }
    matched = match_entities(question, limit=6)
    subjects = [str(x.get("name") or "") for x in matched if str(x.get("name") or "")]
    if not subjects:
        subjects = split_items(str(row.get("canonical_subject") or row.get("subject") or ""))[:4]
    cypher = """
    MATCH p=(n)-[*1..2]-(m)
    WHERE any(name IN $subjects WHERE coalesce(n.name, "") CONTAINS name OR name CONTAINS coalesce(n.name, ""))
    WITH relationships(p) AS rels
    UNWIND rels AS r
    WITH DISTINCT startNode(r) AS s, r AS r, endNode(r) AS o
    RETURN coalesce(s.name, s.id, "") AS s, type(r) AS p, coalesce(o.name, o.id, "") AS o
    LIMIT $limit
    """
    triples: list[dict[str, str]] = []
    with _driver() as driver:
        with driver.session(database=os.getenv("GTF_NEO4J_DATABASE", "neo4j")) as session:
            for record in session.run(cypher, subjects=subjects, limit=top_k):
                triples.append(dict(record))
    graph_text = "\n".join(f"{t['s']} -[{t['p']}]-> {t['o']}" for t in triples)
    llm = call_chat_llm_with_usage(GRAPHRAG_SYSTEM, f"问题：{question}\n\n匹配实体：{'、'.join(subjects)}\n\n2-hop 子图三元组：\n{graph_text}")
    text = str(llm["text"])
    return {
        "answer": extract_answer_items(text),
        "answer_text": text,
        "evidence": triples,
        "raw": {"cypher": cypher, "subjects": subjects, "top_k": top_k, "llm_usage": llm["usage"], "llm_model": llm["model"]},
    }
