# -*- coding: utf-8 -*-
"""Conservative embedding assist wrapper for KGQA experiments.

This module only produces entity/relation-constrained assist candidates.
It does not decide final answers, does not replace graph_answers, and is not
wired into V8/V7 by default.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Optional

from embedding_config import get_embedding_config
from embedding_backend import read_jsonl, warn
from embedding_retriever import retrieve_entities, retrieve_evidence


ENTITY_QUERY_ALIASES: Dict[str, List[str]] = {
    "护航计划实施方案": ["天水市科技型企业成长金融护航计划实施方案"],
    "成长金融护航计划": ["天水市科技型企业成长金融护航计划实施方案"],
    "科技型企业成长金融护航计划": ["天水市科技型企业成长金融护航计划实施方案"],
    "科创e贷": ["科技e贷", "科创贷"],
    "科创贷": ["科技e贷", "科创e贷"],
    "中银科创算力贷": ["科创算力贷"],
    "创业担保贷": ["创业担保贷款"],
    "科技创新再贷款": ["科技创新和技术改造再贷款"],
    "科技创新政策改革试点任务": ["甘肃省2025年度第二批科技创新政策改革试点任务"],
}

GENERIC_EXACT_ENTITY_NAMES = {"甘肃省", "中国人民银行", "科技金融"}


def expand_entity_queries(query: str) -> List[str]:
    """Return conservative query variants for entity candidate recall."""

    variants = [query]
    for alias, expansions in ENTITY_QUERY_ALIASES.items():
        if alias not in query:
            continue
        for expansion in expansions:
            variants.append(query.replace(alias, expansion))
            variants.append(f"{query} {expansion}")

    quoted = re.findall(r"[“\"]([^”\"]{4,120})[”\"]", query)
    variants.extend(quoted)

    deduped: List[str] = []
    seen = set()
    for item in variants:
        normalized = re.sub(r"\s+", " ", str(item or "").strip())
        if normalized and normalized not in seen:
            seen.add(normalized)
            deduped.append(normalized)
    return deduped[:8]


def retrieve_entity_candidates_with_expansion(
    query: str,
    top_k: int,
    min_score: float,
    label_filter: Optional[List[str]] = None,
) -> List[Dict[str, object]]:
    """Merge entity candidates from original and expanded query variants."""

    merged: Dict[str, Dict[str, object]] = {}
    variants = expand_entity_queries(query)
    filters = {str(label).split(".")[-1] for label in (label_filter or [])}
    cfg = get_embedding_config()

    metadata_path = Path(str(cfg["entity_index_dir"])) / "metadata.jsonl"
    try:
        metadata = read_jsonl(metadata_path) if metadata_path.exists() else []
    except Exception as exc:
        warn(f"entity metadata exact-match lookup failed: {exc}")
        metadata = []
    for row in metadata:
        name = str(row.get("name", "")).strip()
        if len(name) < 3 or name in GENERIC_EXACT_ENTITY_NAMES:
            continue
        labels = [str(label).split(".")[-1] for label in row.get("labels", [])]
        if filters and not any(label in filters for label in labels):
            continue
        aliases = [str(item).strip() for item in (row.get("aliases", []) or []) if str(item).strip()]
        matched_alias = ""
        matched_name = any(name in variant or variant in name for variant in variants)
        if not matched_name:
            for alias in aliases:
                if len(alias) >= 2 and any(alias in variant for variant in variants):
                    matched_alias = alias
                    break
        if not matched_name and not matched_alias:
            continue
        match_score = 1.0 if matched_name else 0.985
        merged[name] = {
            "rank": 0,
            "score": match_score,
            "entity_id": row.get("entity_id", ""),
            "name": name,
            "labels": labels,
            "metadata": row,
            "matched_query": "exact_entity_name_substring" if matched_name else "exact_entity_alias_substring",
            "matched_alias": matched_alias,
        }

    for variant in variants:
        rows = retrieve_entities(
            variant,
            top_k=top_k,
            min_score=min_score,
            label_filter=label_filter,
        )
        for row in rows:
            name = str(row.get("name", "")).strip()
            if not name:
                continue
            candidate = dict(row)
            candidate["matched_query"] = variant
            previous = merged.get(name)
            if previous is None or float(candidate.get("score", 0.0)) > float(previous.get("score", 0.0)):
                merged[name] = candidate

    results = sorted(merged.values(), key=lambda row: float(row.get("score", 0.0)), reverse=True)[:top_k]
    for rank, row in enumerate(results, start=1):
        row["rank"] = rank
    return results


def _labels(row: Dict[str, object]) -> List[str]:
    return [str(label).split(".")[-1] for label in row.get("labels", [])]


def infer_preferred_labels(query: str) -> tuple[List[str], str]:
    """Infer preferred KG entity labels from the question text."""

    if any(item in query for item in ("有限公司", "有限责任公司", "股份有限公司", "集团有限公司")):
        return ["Enterprise"], "企业名称问法，优先选择 Enterprise 实体。"
    if "实施方案" in query and any(item in query for item in ("支持哪些产品", "覆盖哪些", "对应哪些", "匹配政策", "适合政策")):
        return ["Policy"], "实施方案作为 subject，优先选择 Policy 实体。"
    if "政策" in query and any(item in query for item in ("匹配政策", "适合政策", "这项政策", "政策名称", "政策依据", "政策覆盖")):
        return ["Policy"], "政策约束问法，优先选择 Policy 实体。"
    if any(item in query for item in ("属于什么产业", "属于哪个产业", "产业细分", "行业", "产业", "产业方向", "领域")):
        return ["IndustrySegment"], "产业/行业问法，优先选择 IndustrySegment 实体。"
    if any(item in query for item in ("由哪家金融机构提供", "哪家金融机构提供", "背后的金融机构")):
        return ["FinancialProduct"], "询问产品由谁提供，优先选择 FinancialProduct 实体。"
    if "银行" in query and any(item in query for item in ("产品", "提供", "支持哪些企业", "服务哪些企业")):
        return ["FinancialInstitution"], "银行/金融机构问法，优先选择 FinancialInstitution 实体。"
    if any(item in query for item in ("再贷款", "金融产品", "产品", "融资产品")):
        return ["FinancialProduct"], "产品问法，优先选择 FinancialProduct 实体。"
    if "政策" in query:
        return ["Policy"], "政策问法，优先选择 Policy 实体。"
    if any(item in query for item in ("哪些企业", "哪家企业", "企业名单", "具体企业", "获贷企业")):
        return [], "企业是答案目标，不按 Enterprise 过滤 subject 候选。"
    if "企业" in query:
        return ["Enterprise"], "企业问法，优先选择 Enterprise 实体。"
    return [], "未识别出明确实体类型，不按 label 过滤。"


def infer_relations(query: str, entity_labels: Optional[List[str]] = None) -> tuple[List[str], str]:
    """Infer KG relation names from question text and selected entity labels."""

    labels = set(entity_labels or [])
    if any(item in query for item in ("属于什么产业", "属于哪个产业", "产业细分", "行业", "产业", "产业方向", "领域")):
        return ["belongsToIndustry"], "产业归属问法，选择 belongsToIndustry。"
    if any(item in query for item in ("地区", "区域", "地方", "落在哪些地方", "覆盖哪些甘肃地区")):
        return ["locatedIn"], "地区/区域覆盖问法，选择 locatedIn。"
    if any(item in query for item in ("奖补事件", "奖补", "补贴事件", "补贴")):
        return ["supports"], "奖补/补贴事件问法，选择 supports。"
    if any(item in query for item in ("政策依据", "背后政策", "政策和同类产品")):
        return ["supports"], "政策依据问法，选择 supports。"
    if any(item in query for item in ("支持哪些企业", "服务哪些企业", "服务对象", "企业特征", "企业画像", "企业资质", "覆盖哪些企业", "适用哪些企业", "目标企业", "匹配政策", "适合政策")):
        if "FinancialProduct" in labels:
            return ["servesEnterprise"], "产品到企业问法，选择 servesEnterprise。"
        if "FinancialInstitution" in labels:
            return ["issuesLoan"], "金融机构支持企业问法，选择 issuesLoan 作为贷款事件证据入口。"
        return ["servesEnterprise"], "企业覆盖问法，默认选择 servesEnterprise。"
    if any(item in query for item in ("发放贷款", "授信", "贷款事件", "提供贷款", "放款", "融资支持")):
        return ["issuesLoan"], "贷款/授信事件问法，选择 issuesLoan。"
    if any(item in query for item in ("贷款给哪家企业", "授信给哪家企业", "获得贷款", "获得授信", "获贷企业", "哪些获贷企业")):
        return ["loanToEnterprise"], "贷款指向企业问法，选择 loanToEnterprise。"
    if any(item in query for item in ("产品", "金融产品", "融资产品", "提供什么", "提供哪些", "由哪家", "哪家金融机构提供")):
        return ["providesProduct"], "产品/提供问法，选择 providesProduct。"
    if any(item in query for item in ("关联结果", "相关关系", "核心对象", "可返回结果", "关系边", "关联对象")):
        return ["providesProduct", "supports", "belongsToIndustry", "servesEnterprise", "loanToEnterprise"], "泛关联问法，返回受控候选关系集合，后续必须图谱验证。"
    if any(item in query for item in ("支持", "政策支持", "被哪些政策", "再贷款", "政策工具")):
        return ["supports"], "政策支持/再贷款问法，选择 supports。"
    return [], "未识别出明确 KG 关系，不执行自动 evidence 检索。"


def _dedup_by_name(rows: List[Dict[str, object]]) -> List[Dict[str, object]]:
    seen = set()
    deduped = []
    for row in rows:
        name = str(row.get("name", "")).strip()
        if not name or name in seen:
            continue
        seen.add(name)
        deduped.append(row)
    return deduped


def assist_retrieve(
    query: str,
    entity_filters: Optional[List[str]] = None,
    relation_filters: Optional[List[str]] = None,
    graph_answers: Optional[List[str]] = None,
    entity_top_k: int = 5,
    max_entity_filters: int = 3,
    entity_score_margin: float = 0.05,
    evidence_top_k: int = 5,
    entity_min_score: float = 0.60,
    evidence_min_score: float = 0.60,
) -> Dict[str, object]:
    """Return constrained assist candidates for a question.

    The wrapper uses entity embedding grounding only to propose entity strings
    and evidence retrieval only to propose supporting evidence. Final answer
    entities must still come from the KG/V8/V7 controlled path.
    """

    cfg = get_embedding_config()
    manual_entities = [item.strip() for item in (entity_filters or []) if item.strip()]
    manual_relations = [item.strip() for item in (relation_filters or []) if item.strip()]
    confirmed_answers = [item.strip() for item in (graph_answers or []) if item.strip()]
    kg_confirmed_mode = bool(manual_entities and manual_relations and confirmed_answers)

    entity_candidates = []
    selected_entities: List[Dict[str, object]] = []
    label_filters: List[str] = []
    if kg_confirmed_mode:
        label_reason = "KG-confirmed mode，使用图谱已确认的 subject/relation/graph_answers，不自动选择实体类型。"
    else:
        label_reason = "手动实体模式，不自动选择实体类型。"
    if manual_entities:
        entity_names = manual_entities
    else:
        label_filters, label_reason = infer_preferred_labels(query)
        entity_candidates = retrieve_entity_candidates_with_expansion(
            query,
            top_k=max(entity_top_k, max_entity_filters * 5, 20),
            min_score=entity_min_score,
            label_filter=label_filters or None,
        )
        entity_candidates = _dedup_by_name(entity_candidates)
        if entity_candidates:
            best_score = float(entity_candidates[0].get("score", 0.0))
            selected_entities = [
                row
                for row in entity_candidates
                if float(row.get("score", 0.0)) >= best_score - entity_score_margin
            ][:max(1, max_entity_filters)]
        else:
            selected_entities = []
        entity_names = [str(row.get("name", "")).strip() for row in selected_entities if row.get("name")]

    selected_labels: List[str] = []
    for row in selected_entities:
        for label in _labels(row):
            if label not in selected_labels:
                selected_labels.append(label)
    if manual_relations:
        relations = manual_relations
        relation_reason = "手动关系模式，直接使用用户提供的 KG 关系名。"
    else:
        relations, relation_reason = infer_relations(query, selected_labels)
        if relations == ["servesEnterprise"] and "FinancialProduct" in selected_labels and len(entity_names) > 1:
            entity_names = entity_names[:1]
            relation_reason += " 为避免相邻产品误扩，产品到企业问法只保留 top1 产品实体。"
    evidence_groups = []
    if cfg["enable_embedding"] and cfg["enable_embedding_evidence"]:
        for entity_name in entity_names:
            for relation in relations:
                answer_filters = confirmed_answers or [""]
                for answer in answer_filters:
                    filters = [entity_name]
                    if answer:
                        filters.append(answer)
                    assist_query = query
                    if kg_confirmed_mode and answer:
                        assist_query = f"{query} {entity_name} {relation} {answer}"
                    chunks = retrieve_evidence(
                        assist_query,
                        top_k=evidence_top_k,
                        min_score=evidence_min_score,
                        entity_filter=filters,
                        source_relation_filter=[relation],
                        strict_entity_filter=True,
                    )
                    evidence_groups.append(
                        {
                            "entity_filter": entity_name,
                            "graph_answer_filter": answer,
                            "source_relation_filter": relation,
                            "chunks": chunks,
                        }
                    )

    return {
        "query": query,
        "used_as_assist": bool(evidence_groups),
        "is_final_answer": False,
        "answer_policy": "embedding_assist_only_kgqa_final_answer_must_come_from_graph_or_controlled_pipeline",
        "kg_confirmed_mode": kg_confirmed_mode,
        "entity_candidates": entity_candidates,
        "entity_filters": entity_names,
        "relation_filters": relations,
        "graph_answer_filters": confirmed_answers,
        "selection_reason": {
            "entity_label_filters": label_filters,
            "entity_label_reason": label_reason,
            "selected_entity_labels": selected_labels,
            "relation_reason": relation_reason,
        },
        "evidence_groups": evidence_groups,
        "notes": [
            "本模块只返回 assist/evidence candidates，不生成最终答案。",
            "graph_answers 或受控 KGQA 主流程仍然负责最终答案实体枚举。",
            "实体过滤应来自 KG 实体或实体别名；关系过滤应来自 KG 关系名。",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    parser.add_argument("--entity", action="append", default=None, help="KG entity name or alias. Can be repeated.")
    parser.add_argument("--relation", action="append", default=None, help="KG relation name. Can be repeated.")
    parser.add_argument(
        "--graph-answer",
        action="append",
        default=None,
        help="Graph-confirmed answer entity/value. Can be repeated. Enables KG-confirmed evidence assist mode with --entity and --relation.",
    )
    parser.add_argument("--entity-top-k", type=int, default=5)
    parser.add_argument("--max-entity-filters", type=int, default=3)
    parser.add_argument("--entity-score-margin", type=float, default=0.05)
    parser.add_argument("--evidence-top-k", type=int, default=5)
    parser.add_argument("--entity-min-score", type=float, default=0.60)
    parser.add_argument("--evidence-min-score", type=float, default=0.60)
    args = parser.parse_args()
    result = assist_retrieve(
        args.query,
        entity_filters=args.entity,
        relation_filters=args.relation,
        graph_answers=args.graph_answer,
        entity_top_k=args.entity_top_k,
        max_entity_filters=args.max_entity_filters,
        entity_score_margin=args.entity_score_margin,
        evidence_top_k=args.evidence_top_k,
        entity_min_score=args.entity_min_score,
        evidence_min_score=args.evidence_min_score,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
