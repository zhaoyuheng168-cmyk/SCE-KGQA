#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Graph-only KGQA baseline using independent entity linking and generic Neo4j lookup."""

from __future__ import annotations

import os
from typing import Any

from neo4j import GraphDatabase

from strong_baseline_utils import candidate_entities, infer_target_types, link_entities


def _driver():
    return GraphDatabase.driver(
        os.getenv("GTF_NEO4J_URI", "bolt://127.0.0.1:7688"),
        auth=(os.getenv("GTF_NEO4J_USER", "neo4j"), os.getenv("GTF_NEO4J_PASSWORD", "CHANGE_ME")),
    )


def answer(question: str, row: dict[str, str] | None = None, top_k: int = 80, **_: Any) -> dict[str, Any]:
    entities = link_entities(question, limit=8)
    subjects = [str(x.get("name") or "") for x in entities if str(x.get("name") or "")]
    cypher = """
    MATCH (s)-[r]-(o)
    WHERE any(name IN $subjects WHERE
      coalesce(s.name, "") = name OR coalesce(o.name, "") = name
    )
    RETURN
      coalesce(s.name, s.id, "") AS s,
      type(r) AS p,
      coalesce(o.name, o.id, "") AS o,
      labels(s)[0] AS s_type,
      labels(o)[0] AS o_type,
      1 AS distance
    LIMIT $limit
    """
    triples: list[dict[str, Any]] = []
    if subjects:
        with _driver() as driver:
            with driver.session(database=os.getenv("GTF_NEO4J_DATABASE", "neo4j")) as session:
                for record in session.run(cypher, subjects=subjects, limit=max(top_k * 6, 120)):
                    triples.append(dict(record))
    candidates = candidate_entities(
        question,
        triples,
        subjects,
        explicit_limit=min(top_k, 20),
        fallback_limit=min(top_k, 10),
    )
    text = "、".join(candidates) if candidates else "无法根据当前图谱邻域确定。"
    return {
        "answer": candidates,
        "answer_text": text,
        "evidence": triples,
        "raw": {
            "baseline": "graph_only_kgqa",
            "cypher": cypher,
            "subjects": subjects,
            "target_types": infer_target_types(question),
            "top_k": top_k,
        },
    }
