#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Schema/entity lexicon helpers for strong adapted baselines.

These helpers read frozen schema-derived indexes and runtime KG files. They do
not import or call the SCE-KGQA router, planner, gates, rerankers, or fallback
logic.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from common_io import ROOT, normalize_text


ENTITY_META = ROOT / "app/retrieval_only/embedding_indexes/entity_names/metadata.jsonl"
RELATION_META = ROOT / "app/retrieval_only/embedding_indexes/relation_schema/metadata.jsonl"
NODES_PATH = ROOT / "app/builder/data/runtime/nodes_kag.json"
EDGES_PATH = ROOT / "app/builder/data/runtime/edges_kag.json"


RELATION_ALIASES: dict[str, list[str]] = {
    "providesProduct": ["提供", "推出", "办理", "金融产品", "贷款产品", "产品"],
    "supports": ["支持", "政策依据", "背后政策", "支撑"],
    "servesEnterprise": ["服务", "覆盖", "面向", "适用于", "关联企业"],
    "targetsEnterprise": ["面向企业", "目标企业", "支持企业"],
    "belongsToIndustry": ["属于", "产业", "行业", "领域", "赛道"],
    "locatedIn": ["位于", "地区", "区域", "城市", "地市", "范围内"],
    "potentiallyMatchesProduct": ["匹配", "适合", "可申请", "对应", "匹配度"],
    "potentiallyMatchesPolicy": ["匹配政策", "适用政策", "可申报政策"],
    "hasFeature": ["具有", "具备", "资质", "特征", "画像", "标签"],
    "issuesLoan": ["发放贷款", "授信", "贷款事件"],
    "loanToEnterprise": ["向企业放贷", "获贷", "得到贷款"],
    "grantsSubsidy": ["补贴", "奖补", "资助"],
    "benefitsEnterprise": ["惠及", "补助企业", "奖励企业"],
}


@lru_cache(maxsize=1)
def load_nodes() -> list[dict[str, Any]]:
    return json.loads(NODES_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_edges() -> list[dict[str, Any]]:
    return json.loads(EDGES_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def node_by_id() -> dict[str, dict[str, Any]]:
    return {str(row.get("id")): row for row in load_nodes()}


@lru_cache(maxsize=1)
def entity_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if ENTITY_META.exists():
        for line in ENTITY_META.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows
    for row in load_nodes():
        rows.append(
            {
                "entity_id": row.get("id"),
                "name": row.get("name"),
                "labels": [row.get("label")],
                "aliases": row.get("properties", {}).get("aliases", []),
                "relation_contexts": [],
            }
        )
    return rows


@lru_cache(maxsize=1)
def relation_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if RELATION_META.exists():
        for line in RELATION_META.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _labels(row: dict[str, Any]) -> list[str]:
    return [str(x).split(".")[-1] for x in row.get("labels", []) if str(x).strip()]


def match_entities(
    question: str,
    label_filter: list[str] | None = None,
    limit: int = 12,
    allow_partial: bool = True,
) -> list[dict[str, Any]]:
    filters = set(label_filter or [])
    q_norm = normalize_text(question)
    scored: list[tuple[int, int, dict[str, Any]]] = []
    for row in entity_rows():
        labels = _labels(row)
        if filters and not (set(labels) & filters):
            continue
        names = [str(row.get("name") or "")]
        aliases = row.get("aliases") or []
        if isinstance(aliases, list):
            names.extend(str(x) for x in aliases)
        for name in names:
            n_norm = normalize_text(name)
            if not n_norm or len(n_norm) < 2:
                continue
            if n_norm in q_norm:
                scored.append((len(n_norm), 1, row))
                break
            if allow_partial and len(n_norm) >= 4 and any(part and part in q_norm for part in re.split(r"[()（）·\s]+", n_norm)):
                scored.append((len(n_norm), 0, row))
                break
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for _, _, row in sorted(scored, key=lambda x: (x[1], x[0]), reverse=True):
        eid = str(row.get("entity_id") or row.get("id") or row.get("name"))
        if eid not in seen:
            seen.add(eid)
            out.append(row)
        if len(out) >= limit:
            break
    return out


def infer_relations(question: str, limit: int = 5) -> list[str]:
    scores: dict[str, int] = {}
    for rel, aliases in RELATION_ALIASES.items():
        score = sum(1 for item in aliases if item and item in question)
        if score:
            scores[rel] = max(scores.get(rel, 0), score)
    for row in relation_rows():
        rel = str(row.get("relation") or "")
        hay = " ".join([rel, str(row.get("description") or ""), str(row.get("question_type") or "")])
        score = sum(1 for token in re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z]+", hay) if token in question)
        if score:
            scores[rel] = max(scores.get(rel, 0), score)
    ranked = [rel for rel, _ in sorted(scores.items(), key=lambda x: x[1], reverse=True)]
    return ranked[:limit]


def expand_query(question: str, include_context: bool = False) -> str:
    entities = match_entities(question, limit=8, allow_partial=False)
    rels = infer_relations(question, limit=5)
    pieces = [question]
    for row in entities:
        labels = "/".join(_labels(row))
        pieces.append(f"实体名称：{row.get('name')} 实体类型：{labels}")
        if include_context:
            contexts = row.get("relation_contexts") or []
            pieces.extend(str(x) for x in contexts[:4])
    for rel in rels:
        pieces.append(rel)
        pieces.extend(RELATION_ALIASES.get(rel, []))
    return "；".join(x for x in pieces if str(x).strip())


def _name(row: dict[str, Any] | None) -> str:
    return str((row or {}).get("name") or "")


def structured_schema_answer(question: str, top_k: int = 80) -> dict[str, Any] | None:
    """Answer common schema-template questions with frozen KG paths."""
    products = match_entities(question, ["FinancialProduct"], limit=4)
    regions = match_entities(question, ["Region"], limit=4)
    industries = match_entities(question, ["IndustrySegment"], limit=4)
    enterprises = match_entities(question, ["Enterprise"], limit=4)
    institutions = match_entities(question, ["FinancialInstitution"], limit=4)
    policies = match_entities(question, ["Policy"], limit=4)
    nodes = node_by_id()
    edges = load_edges()

    triples: list[dict[str, str]] = []
    answers: list[str] = []

    def add_answer(value: str) -> None:
        if value and value not in answers:
            answers.append(value)

    def node_label(eid: str) -> str:
        return str(nodes.get(eid, {}).get("label") or "")

    def node_name(eid: str) -> str:
        return _name(nodes.get(eid)) or eid

    def selected_ids(rows: list[dict[str, Any]]) -> set[str]:
        return {str(row.get("entity_id") or row.get("id")) for row in rows if str(row.get("entity_id") or row.get("id"))}

    product_ids = selected_ids(products)
    region_ids = selected_ids(regions)
    industry_ids = selected_ids(industries)
    enterprise_ids = selected_ids(enterprises)
    institution_ids = selected_ids(institutions)
    policy_ids = selected_ids(policies)

    # Enterprise -> region.
    if enterprise_ids and any(token in question for token in ["地区", "区域", "城市", "地市", "归属", "位于", "哪里"]):
        for e in edges:
            if e.get("type") == "locatedIn" and e.get("from") in enterprise_ids:
                add_answer(node_name(str(e.get("to"))))
                triples.append({"s": node_name(str(e.get("from"))), "p": "locatedIn", "o": node_name(str(e.get("to")))})

    # Financial institution -> products.
    if institution_ids and ("产品" in question or "提供" in question):
        for e in edges:
            if e.get("type") == "providesProduct" and e.get("from") in institution_ids:
                add_answer(node_name(str(e.get("to"))))
                triples.append({"s": node_name(str(e.get("from"))), "p": "providesProduct", "o": node_name(str(e.get("to")))})

    # Product -> provider.
    if product_ids and ("由" in question and "提供" in question or "哪家" in question):
        for e in edges:
            if e.get("type") == "providesProduct" and e.get("to") in product_ids:
                add_answer(node_name(str(e.get("from"))))
                triples.append({"s": node_name(str(e.get("from"))), "p": "providesProduct", "o": node_name(str(e.get("to")))})

    # Enterprise -> potential matched products/policies/features.
    if enterprise_ids and any(token in question for token in ["潜在匹配", "匹配对象", "匹配度", "对应"]):
        rels = {"potentiallyMatchesProduct", "potentiallyMatchesPolicy"}
        for e in edges:
            if e.get("from") in enterprise_ids and e.get("type") in rels:
                add_answer(node_name(str(e.get("to"))))
                triples.append({"s": node_name(str(e.get("from"))), "p": str(e.get("type")), "o": node_name(str(e.get("to")))})

    # Product + region/industry -> enterprises through direct or rule edges.
    if product_ids and (regions or industries or "企业" in question):
        direct_enterprises: set[str] = set()
        for e in edges:
            if e.get("type") in {"servesEnterprise", "potentiallyMatchesProduct"}:
                if e.get("from") in product_ids and node_label(str(e.get("to"))) == "Enterprise":
                    direct_enterprises.add(str(e.get("to")))
                if e.get("to") in product_ids and node_label(str(e.get("from"))) == "Enterprise":
                    direct_enterprises.add(str(e.get("from")))
        region_ok: set[str] | None = None
        if region_ids:
            region_ok = set()
            for e in edges:
                if e.get("type") == "locatedIn" and e.get("to") in region_ids:
                    region_ok.add(str(e.get("from")))
        industry_ok: set[str] | None = None
        if industry_ids:
            industry_ok = set()
            for e in edges:
                if e.get("type") == "belongsToIndustry" and e.get("to") in industry_ids:
                    industry_ok.add(str(e.get("from")))
        selected = direct_enterprises
        if region_ok is not None:
            selected = selected & region_ok
        if industry_ok is not None:
            selected = selected & industry_ok
        for eid in sorted(selected, key=node_name):
            add_answer(node_name(eid))
            if len(answers) >= top_k:
                break

    # Policy -> products / enterprises / regions / industries.
    if policy_ids and any(token in question for token in ["支持", "面向", "覆盖", "涉及"]):
        for e in edges:
            if e.get("from") in policy_ids and e.get("type") in {"supports", "targetsEnterprise", "hasCoverageRegion", "hasCoverageIndustry"}:
                add_answer(node_name(str(e.get("to"))))
                triples.append({"s": node_name(str(e.get("from"))), "p": str(e.get("type")), "o": node_name(str(e.get("to")))})

    if not answers:
        return None
    return {
        "answer": answers[:top_k],
        "answer_text": "、".join(answers[:top_k]),
        "evidence": triples[:top_k],
        "raw": {
            "matched_products": [_name(r) for r in products],
            "matched_regions": [_name(r) for r in regions],
            "matched_industries": [_name(r) for r in industries],
            "matched_enterprises": [_name(r) for r in enterprises],
            "matched_institutions": [_name(r) for r in institutions],
            "schema_template_used": True,
        },
    }
