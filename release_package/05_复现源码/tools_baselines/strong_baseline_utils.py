#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Independent helpers for strong comparison baselines.

This module intentionally does not import SCE routers, planners, schema
templates, rule fallbacks, or evaluation-gold fields.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

from common_io import ROOT, normalize_text


ENTITY_LEXICON = ROOT / "experiments/baselines/corpus/entity_lexicon.jsonl"

TARGET_TYPE_TERMS: list[tuple[tuple[str, ...], tuple[str, ...]]] = [
    (("产品", "金融产品", "贷款产品", "信贷产品"), ("FinancialProduct",)),
    (("政策", "政策文件", "扶持政策"), ("Policy",)),
    (("机构", "银行", "金融机构"), ("FinancialInstitution",)),
    (("企业", "公司", "主体"), ("Enterprise",)),
    (("特征", "资质", "标签", "企业特征"), ("QualificationCreditFeature",)),
    (("行业", "产业"), ("IndustrySegment",)),
    (("地区", "区域", "市州", "位于"), ("Region",)),
    (("平台", "服务平台"), ("ServicePlatform",)),
    (("贷款", "批贷", "放款"), ("LoanEvent", "Enterprise")),
    (("补贴", "奖补", "补助"), ("SubsidyEvent", "Enterprise")),
]

RELATION_TERMS: dict[str, tuple[str, ...]] = {
    "providesProduct": ("提供", "推出", "产品"),
    "supports": ("支持", "扶持", "政策"),
    "servesEnterprise": ("服务", "覆盖", "企业"),
    "hasFeature": ("特征", "资质", "标签"),
    "belongsToIndustry": ("行业", "产业"),
    "locatedIn": ("地区", "区域", "位于", "市州"),
    "loanToEnterprise": ("贷款", "批贷", "放款"),
    "issuesLoan": ("贷款", "批贷", "放款"),
    "grantsSubsidy": ("补贴", "奖补", "补助"),
    "benefitsEnterprise": ("补贴", "奖补", "补助"),
}


@lru_cache(maxsize=1)
def load_entity_lexicon() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with ENTITY_LEXICON.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def link_entities(question: str, limit: int = 10) -> list[dict[str, Any]]:
    q_norm = normalize_text(question)
    scored: list[tuple[int, int, dict[str, Any]]] = []
    for row in load_entity_lexicon():
        names = [str(row.get("name") or "")]
        names.extend(str(x) for x in row.get("aliases") or [])
        best: tuple[int, int] | None = None
        for name in names:
            n_norm = normalize_text(name)
            if len(n_norm) < 2:
                continue
            if n_norm in q_norm:
                candidate = (2, len(n_norm))
            elif len(n_norm) >= 4 and any(
                len(part) >= 3 and part in q_norm
                for part in re.split(r"[()（）·\s]+", n_norm)
            ):
                candidate = (1, len(n_norm))
            else:
                continue
            if best is None or candidate > best:
                best = candidate
        if best:
            scored.append((best[0], best[1], row))
    return [row for _, _, row in sorted(scored, key=lambda x: (x[0], x[1]), reverse=True)[:limit]]


def infer_target_types(question: str) -> list[str]:
    scores: Counter[str] = Counter()
    for terms, types in TARGET_TYPE_TERMS:
        hits = sum(1 for term in terms if term in question)
        for entity_type in types:
            scores[entity_type] += hits
    return [entity_type for entity_type, score in scores.most_common() if score > 0]


def _short_label(value: Any) -> str:
    return str(value or "").split(".")[-1]


def score_triple(
    question: str,
    triple: dict[str, Any],
    subject_names: set[str],
    target_types: set[str],
) -> float:
    subject = str(triple.get("s") or "")
    predicate = str(triple.get("p") or "")
    obj = str(triple.get("o") or "")
    subject_type = _short_label(triple.get("s_type"))
    object_type = _short_label(triple.get("o_type"))
    distance = int(triple.get("distance") or 1)
    score = 0.0
    if subject in subject_names or obj in subject_names:
        score += 5.0
    if subject_type in target_types:
        score += 4.0
    if object_type in target_types:
        score += 4.0
    for relation, terms in RELATION_TERMS.items():
        if predicate == relation:
            score += 3.0 * sum(1 for term in terms if term in question)
    compact_question = re.sub(r"\s+", "", question)
    triple_text = f"{subject}{predicate}{obj}"
    q_tokens = set(re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9_]+", compact_question))
    score += 0.3 * sum(1 for token in q_tokens if token in triple_text)
    score += 2.0 if distance <= 1 else 0.5
    return score


def rank_triples(
    question: str,
    triples: list[dict[str, Any]],
    subjects: list[str],
    top_k: int,
) -> list[dict[str, Any]]:
    subject_names = set(subjects)
    target_types = set(infer_target_types(question))
    scored: list[tuple[float, str, dict[str, Any]]] = []
    for triple in triples:
        score = score_triple(question, triple, subject_names, target_types)
        key = f"{triple.get('s')}|{triple.get('p')}|{triple.get('o')}"
        item = dict(triple)
        item["score"] = score
        scored.append((score, key, item))
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for _, key, triple in sorted(scored, key=lambda x: (x[0], x[1]), reverse=True):
        if key in seen:
            continue
        seen.add(key)
        out.append(triple)
        if len(out) >= top_k:
            break
    return out


def candidate_entities(
    question: str,
    triples: list[dict[str, Any]],
    subjects: list[str],
    explicit_limit: int = 20,
    fallback_limit: int = 10,
) -> list[str]:
    target_types = set(infer_target_types(question))
    ranked = rank_triples(question, triples, subjects, top_k=max(explicit_limit * 3, fallback_limit * 3))
    candidates: list[str] = []
    for triple in ranked:
        for name_key, type_key in (("s", "s_type"), ("o", "o_type")):
            name = str(triple.get(name_key) or "")
            entity_type = _short_label(triple.get(type_key))
            if not name or name in subjects or name in candidates:
                continue
            if target_types and entity_type not in target_types:
                continue
            candidates.append(name)
            if len(candidates) >= (explicit_limit if target_types else fallback_limit):
                return candidates
    return candidates
