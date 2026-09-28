#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Independent traditional rule/template KGQA baseline."""

from __future__ import annotations

import os
from typing import Any

from neo4j import GraphDatabase

from strong_baseline_utils import RELATION_TERMS, infer_target_types, link_entities


def _driver():
    return GraphDatabase.driver(
        os.getenv("GTF_NEO4J_URI", "bolt://127.0.0.1:7688"),
        auth=(os.getenv("GTF_NEO4J_USER", "neo4j"), os.getenv("GTF_NEO4J_PASSWORD", "CHANGE_ME")),
    )


def infer_relations(question: str) -> list[str]:
    scored = []
    for relation, terms in RELATION_TERMS.items():
        score = sum(1 for term in terms if term in question)
        if score:
            scored.append((score, relation))
    return [relation for _, relation in sorted(scored, reverse=True)]


def answer(question: str, row: dict[str, str] | None = None, top_k: int = 50, **_: Any) -> dict[str, Any]:
    subjects = [str(item.get("name") or "") for item in link_entities(question, limit=6)]
    relations = infer_relations(question)
    target_types = infer_target_types(question)
    if not subjects or not relations:
        return {
            "answer": [],
            "answer_text": "无法从当前可用知识中确定。",
            "evidence": [],
            "raw": {"subjects": subjects, "relations": relations, "target_types": target_types},
        }

    cypher = """
    MATCH (s)-[r]-(o)
    WHERE any(name IN $subjects WHERE
      coalesce(s.name, "") = name OR coalesce(o.name, "") = name
    )
    AND type(r) IN $relations
    RETURN
      coalesce(s.name, s.id, "") AS s,
      type(r) AS p,
      coalesce(o.name, o.id, "") AS o,
      labels(s)[0] AS s_type,
      labels(o)[0] AS o_type
    LIMIT $limit
    """
    triples: list[dict[str, Any]] = []
    with _driver() as driver:
        with driver.session(database=os.getenv("GTF_NEO4J_DATABASE", "neo4j")) as session:
            for record in session.run(
                cypher,
                subjects=subjects,
                relations=relations,
                limit=top_k,
            ):
                triples.append(dict(record))

    answers: list[str] = []
    target_set = set(target_types)
    for triple in triples:
        for name_key, type_key in (("s", "s_type"), ("o", "o_type")):
            name = str(triple.get(name_key) or "")
            entity_type = str(triple.get(type_key) or "").split(".")[-1]
            if not name or name in subjects or name in answers:
                continue
            if target_set and entity_type not in target_set:
                continue
            answers.append(name)
    return {
        "answer": answers,
        "answer_text": "答案：" + "||".join(answers) if answers else "无法从当前可用知识中确定。",
        "evidence": triples,
        "raw": {
            "baseline": "independent_rule_based_kgqa",
            "subjects": subjects,
            "relations": relations,
            "target_types": target_types,
            "cypher": cypher,
        },
    }
