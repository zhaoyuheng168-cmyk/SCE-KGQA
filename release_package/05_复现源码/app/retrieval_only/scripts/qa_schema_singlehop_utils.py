"""
Pure helpers for V8 schema single-hop routing.

This module must not import V8 runtime code, Neo4j, LLM clients, filesystem
helpers, or environment configuration. V8 wrappers pass current constants in
and compare module results with legacy results before use.
"""

from typing import Any, Dict, List

__all__ = [
    "infer_schema_target_types_unified",
    "schema_singlehop_should_skip",
]


def infer_schema_target_types_unified(
    query: str,
    schema_target_type_verbalization: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Translate natural-language target mentions into schema target types.
    This does not decide qtype, subject, route, or answer.
    """
    q = str(query or "")
    hits = []
    for target_type, cfg in schema_target_type_verbalization.items():
        aliases = cfg.get("aliases") or []
        alias_hits = [a for a in aliases if a and a in q]
        if alias_hits:
            hits.append({
                "target_type": target_type,
                "alias_hits": alias_hits,
            })

    priority = {
        "QualificationCreditFeature": 100,
        "IndustrySegment": 90,
        "Region": 80,
        "FinancialInstitution": 70,
        "FinancialProduct": 60,
        "Policy": 50,
        "Enterprise": 40,
    }
    hits.sort(key=lambda x: priority.get(x.get("target_type"), 0), reverse=True)
    return hits


def schema_singlehop_should_skip(query: str, subjects: List[str]) -> bool:
    """
    Return whether schema single-hop routing should yield to multihop/generic flows.
    This is a pure predicate and does not build candidates or choose routes.
    """
    q = str(query or "").strip()
    if not q:
        return True

    multihop_terms = [
        "政策→产品", "政策-产品", "政策—产品",
        "机构→产品", "机构-产品", "机构—产品",
        "产品→企业", "产品-企业", "产品—企业",
        "企业→地区", "企业-地区", "企业—地区",
        "企业→行业", "企业-行业", "企业—行业",
        "企业→特征", "企业-特征", "企业—特征",
        "通过产品链", "通过产品服务链", "通过金融产品链",
        "顺着", "链路", "路径", "最终覆盖", "最终触达", "最终落到",
        "主要覆盖到哪些地区", "主要服务哪些行业", "通过其产品链",
    ]
    if any(x in q for x in multihop_terms):
        return True

    if len(subjects) >= 2:
        link_terms = [
            "支持的", "对应的", "关联的", "通过", "进一步", "最后", "最终", "再由",
        ]
        if any(x in q for x in link_terms):
            return True

    generic_overview_terms = [
        "关系对象", "可核验结果", "可验证答案项", "当前图谱里", "当前知识图谱里",
        "图谱中能关联到哪些对象", "作为查询入口", "周边对象",
        "能查到什么相关结果", "有哪些相关对象",
    ]
    if any(x in q for x in generic_overview_terms):
        return True

    return False
