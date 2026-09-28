# -*- coding: utf-8 -*-
"""Assist-only embedding proposal boundaries for the KGQA pipeline.

The intended order is:

1. Pre-route entity candidate grounding.
2. Original V8/router relation detection.
3. Embedding relation candidates only as fallback proposals.
4. Graph validation confirms qtype/relation/answers.
5. Post-graph answer rerank.

This module does not confirm entities, relations, or final answers.
Evidence assist is intentionally excluded from the recommended main pipeline
and kept only for ablation/debug experiments.
"""

from __future__ import annotations

import argparse
import json
from typing import Dict, List, Optional

from embedding_assist_wrapper import (
    infer_preferred_labels,
    infer_relations,
    retrieve_entity_candidates_with_expansion,
)
from embedding_config import get_embedding_config
from embedding_retriever import retrieve_relations


def propose_pre_route_entity_candidates(
    query: str,
    top_k: int = 10,
    min_score: Optional[float] = None,
) -> Dict[str, object]:
    """Return entity candidates that the original router may validate later."""

    cfg = get_embedding_config()
    label_filters, label_reason = infer_preferred_labels(query)
    if not cfg["enable_embedding"] or not cfg["enable_embedding_entity_candidates"]:
        return {
            "stage": "pre_route_entity_candidates",
            "enabled": False,
            "is_confirmed": False,
            "requires_graph_validation": True,
            "candidates": [],
            "reason": "embedding_entity_candidates_disabled",
        }
    candidates = retrieve_entity_candidates_with_expansion(
        query,
        top_k=top_k,
        min_score=min_score if min_score is not None else float(cfg["entity_min_score"]),
        label_filter=label_filters or None,
    )
    return {
        "stage": "pre_route_entity_candidates",
        "enabled": True,
        "is_confirmed": False,
        "requires_graph_validation": True,
        "query": query,
        "preferred_labels": label_filters,
        "label_reason": label_reason,
        "candidates": candidates,
        "notes": [
            "这些只是实体候选，用于提高用户问法鲁棒性。",
            "最终 subject 仍需由原有 V8/Type Gate/图谱路径确认。",
        ],
    }


def propose_relation_candidates_after_router_miss(
    query: str,
    selected_entity_labels: Optional[List[str]] = None,
    relation_query: Optional[str] = None,
) -> Dict[str, object]:
    """Return relation candidates only after the original router misses."""

    cfg = get_embedding_config()
    if not cfg["enable_embedding"] or not cfg["enable_embedding_relation_fallback"]:
        return {
            "stage": "relation_candidates_after_router_miss",
            "enabled": False,
            "is_confirmed": False,
            "requires_graph_validation": True,
            "query": query,
            "selected_entity_labels": selected_entity_labels or [],
            "relation_candidates": [],
            "reason": "embedding_relation_fallback_disabled",
        }
    cfg = get_embedding_config()
    grounding_query = str(relation_query or query or "").strip()
    relation_rows = retrieve_relations(
        grounding_query,
        top_k=int(cfg.get("relation_top_k") or 5),
        min_score=float(cfg.get("relation_min_score") or 0.58),
        source_type_filter=selected_entity_labels or None,
    )
    relations = []
    for row in relation_rows:
        relation = str(row.get("relation", "")).strip()
        if relation and relation not in relations:
            relations.append(relation)
    relation_source = "relation_embedding"
    reason = "relation embedding schema grounding，根据图谱关系语义描述召回候选关系。"
    if not relations:
        relations, reason = infer_relations(grounding_query, selected_entity_labels or [])
        relation_source = "static_relation_fallback" if relations else "none"
    return {
        "stage": "relation_candidates_after_router_miss",
        "enabled": True,
        "is_confirmed": False,
        "requires_graph_validation": True,
        "query": query,
        "relation_grounding_query": grounding_query,
        "selected_entity_labels": selected_entity_labels or [],
        "relation_candidates": relations,
        "relation_candidate_source": relation_source,
        "relation_embedding_rows": relation_rows,
        "proposal_reason": reason,
        "notes": [
            "关系识别优先使用原有 V8/router 链路。",
            "embedding 只在原链路失败、低置信或路径验证失败时提供候选关系。",
            "所有候选关系必须再经过 Type Gate 和图谱路径验证。",
        ],
    }


def propose_pipeline_assist(query: str) -> Dict[str, object]:
    """Return a combined assist-only proposal for inspection and smoke tests."""

    entity_proposal = propose_pre_route_entity_candidates(query)
    labels: List[str] = []
    for row in entity_proposal.get("candidates", [])[:3]:
        for label in row.get("labels", []) or []:
            if str(label) not in labels:
                labels.append(str(label))
    relation_proposal = propose_relation_candidates_after_router_miss(query, labels)
    return {
        "query": query,
        "is_final_answer": False,
        "is_confirmed": False,
        "requires_graph_validation": True,
        "policy": "entity_candidates_pre_route_relation_candidates_only_after_original_router_miss",
        "entity_proposal": entity_proposal,
        "relation_proposal_after_router_miss": relation_proposal,
    }


def _infer_target_types_from_relations(
    query: str,
    subject_types: Optional[List[str]],
    relation_candidates: List[str],
) -> List[str]:
    q = str(query or "")
    subject_type_set = set(subject_types or [])
    out: List[str] = []

    def add(tp: str) -> None:
        if tp and tp not in out:
            out.append(tp)

    if "FinancialProduct" in subject_type_set and "servesEnterprise" in relation_candidates:
        if any(item in q for item in ("企业特征", "企业画像", "资质", "适合哪类", "服务对象")):
            add("QualificationCreditFeature")
        if any(item in q for item in ("哪些企业", "企业名单", "具体企业", "企业列表", "获贷企业")):
            add("Enterprise")
    if "FinancialProduct" in subject_type_set and "providesProduct" in relation_candidates:
        if any(item in q for item in ("由哪家", "哪家金融机构", "提供机构")):
            add("FinancialInstitution")
    if "supports" in relation_candidates and any(item in q for item in ("政策依据", "背后政策", "政策文件")):
        add("Policy")
    if "Enterprise" in subject_type_set and any(item in q for item in ("获得贷款", "获贷", "贷款支持", "融资支持")):
        add("FinancialInstitution")
    if "Policy" in subject_type_set and any(item in q for item in ("产业方向", "产业", "行业", "领域")):
        add("IndustrySegment")
    if "Policy" in subject_type_set and any(item in q for item in ("地区", "区域", "地市", "城市", "试点任务")):
        add("Region")
    if "belongsToIndustry" in relation_candidates and any(item in q for item in ("产业方向", "产业", "行业", "领域")):
        add("IndustrySegment")
    if "locatedIn" in relation_candidates and any(item in q for item in ("地区", "区域", "地市", "城市", "地方")):
        add("Region")
    if "loanToEnterprise" in relation_candidates and any(item in q for item in ("哪些企业", "哪家企业", "企业名单", "具体企业", "获贷企业")):
        add("Enterprise")
    return out


def propose_unified_route_assist(
    query: str,
    confirmed_subject: str = "",
    confirmed_subject_types: Optional[List[str]] = None,
) -> Dict[str, object]:
    """Return a V8-facing assist proposal, not an answer.

    When V8 already has an exact graph subject, entity embedding candidates are
    intentionally skipped. Relation and target-type candidates are still only
    proposals and must be graph validated by V8.
    """

    subject = str(confirmed_subject or "").strip()
    subject_types = [str(item).strip() for item in (confirmed_subject_types or []) if str(item).strip()]

    entity_proposal: Dict[str, object]
    if subject:
        entity_proposal = {
            "stage": "entity_candidates_skipped",
            "enabled": False,
            "is_confirmed": True,
            "confirmed_subject": subject,
            "confirmed_subject_types": subject_types,
            "reason": "exact_graph_subject_already_available",
            "candidates": [],
        }
    else:
        entity_proposal = propose_pre_route_entity_candidates(query)
        subject_types = []
        for row in entity_proposal.get("candidates", [])[:3]:
            for label in row.get("labels", []) or []:
                if str(label) not in subject_types:
                    subject_types.append(str(label))

    relation_query = query
    if subject:
        relation_query = str(query or "").replace(subject, " ")
    relation_proposal = propose_relation_candidates_after_router_miss(query, subject_types, relation_query=relation_query)
    relation_candidates = [
        str(item).strip()
        for item in relation_proposal.get("relation_candidates", [])
        if str(item).strip()
    ]
    target_type_candidates = _infer_target_types_from_relations(query, subject_types, relation_candidates)
    return {
        "stage": "unified_embedding_assist_proposal",
        "query": query,
        "is_final_answer": False,
        "is_confirmed": False,
        "requires_graph_validation": True,
        "policy": "embedding_assist_only_v8_must_route_and_validate",
        "confirmed_subject": subject,
        "confirmed_subject_types": subject_types,
        "entity_proposal": entity_proposal,
        "relation_candidates": relation_candidates,
        "target_type_candidates": target_type_candidates,
        "relation_proposal": relation_proposal,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    parser.add_argument("--mode", choices=["entity", "relation", "pipeline", "unified"], default="pipeline")
    parser.add_argument("--confirmed-subject", default="")
    parser.add_argument("--confirmed-subject-type", action="append", default=[])
    args = parser.parse_args()
    if args.mode == "entity":
        result = propose_pre_route_entity_candidates(args.query)
    elif args.mode == "relation":
        result = propose_relation_candidates_after_router_miss(args.query)
    elif args.mode == "unified":
        result = propose_unified_route_assist(
            args.query,
            confirmed_subject=args.confirmed_subject,
            confirmed_subject_types=args.confirmed_subject_type,
        )
    else:
        result = propose_pipeline_assist(args.query)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
