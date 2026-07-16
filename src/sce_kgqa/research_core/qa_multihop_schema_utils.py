"""
Pure schema-level helpers for V8 multihop candidate routing.

This module must not import V8 runtime code, Neo4j, LLM clients, filesystem
helpers, or environment configuration. V8 wrappers pass the current schema
constants in, then compare module results with legacy results before use.
"""

from typing import Any, Dict, List, Tuple

__all__ = [
    "multihop_answer_type_alias_hits",
    "infer_multihop_answer_types_by_schema",
    "schema_multihop_score",
    "rule_reasoning_query_hint",
]


def multihop_answer_type_alias_hits(
    query: str,
    target_type: str,
    schema_verbalization: Dict[str, Dict[str, Any]],
) -> List[str]:
    """Return schema answer_type aliases hit by query."""
    q = str(query or "")
    spec = schema_verbalization.get(target_type, {})
    hits = []
    for a in spec.get("aliases", []) or []:
        a = str(a or "").strip()
        if a and a in q and a not in hits:
            hits.append(a)
    return hits


def infer_multihop_answer_types_by_schema(
    query: str,
    schema_verbalization: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Map natural-language target expressions to graph schema answer types.
    This does not output chain_id or select a final route.
    """
    q = str(query or "").strip()
    if not q:
        return []

    out = []
    for target_type in ["QualificationCreditFeature", "IndustrySegment", "Region", "Enterprise"]:
        hits = multihop_answer_type_alias_hits(q, target_type, schema_verbalization)
        if hits:
            out.append({
                "target_type": target_type,
                "canonical": schema_verbalization.get(target_type, {}).get("canonical", target_type),
                "alias_hits": hits,
            })
    return out


def schema_multihop_score(
    query: str,
    answer_info: Dict[str, Any],
    action_weak_hints: List[str],
    bridge_hints: List[str],
) -> Tuple[float, Dict[str, Any]]:
    """Lightweight confidence score for schema-driven multihop candidates."""
    q = str(query or "")
    action_hits = [x for x in action_weak_hints if x in q]
    bridge_hits = [x for x in bridge_hints if x in q]
    alias_hits = list(answer_info.get("alias_hits") or [])

    score = 0.35
    if alias_hits:
        score += 0.15
    if action_hits:
        score += 0.20
    if bridge_hits:
        score += 0.15
    if any(x in q for x in ["哪些", "什么", "哪类", "分布", "集中", "范围", "画像"]):
        score += 0.10
    if "产品" in q and "企业" in q:
        score += 0.05

    evidence = {
        "alias_hits": alias_hits,
        "action_hits": action_hits[:8],
        "bridge_hits": bridge_hits[:8],
    }
    return min(score, 0.99), evidence


def rule_reasoning_query_hint(query: str, relation_hints: List[str] = None) -> bool:
    """
    Return whether query clearly asks for rule reasoning or rule coverage.
    This is a pure predicate and does not route or answer the query.
    """
    q = str(query or "").strip()
    if not q:
        return False

    strong_hints = [
        "规则推理",
        "规则覆盖",
        "规则匹配",
        "规则判断",
        "当前规则",
        "按照规则",
        "按规则",
        "根据规则",
        "规则结果",
        "规则覆盖结果",
        "规则推理结果",
        "最终主要覆盖到哪些地区",
        "最终主要覆盖哪些地区",
        "最终主要覆盖到哪些区域",
        "最终主要覆盖哪些区域",
        "最终主要覆盖到哪些行业",
        "最终主要覆盖哪些行业",
        "最终主要覆盖哪些产业",
        "潜在匹配",
        "可能匹配",
        "匹配哪些政策",
        "匹配哪些科技金融产品",
        "适合哪些科技金融产品",
        "适合哪类企业",
        "适合哪些企业",
        "对应哪些资质",
        "信用特征",
        "资质或信用特征",
    ]

    if relation_hints is None:
        relation_hints = [
            "potentiallyMatchesPolicy",
            "potentiallyMatchesProduct",
            "fitsEnterpriseFeature",
            "hasCoverageIndustry",
            "hasCoverageRegion",
        ]

    return any(x in q for x in strong_hints + list(relation_hints))
