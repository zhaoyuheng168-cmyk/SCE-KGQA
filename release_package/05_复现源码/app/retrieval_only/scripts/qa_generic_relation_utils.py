# -*- coding: utf-8 -*-
"""Pure query predicate and intent helpers for V8 generic relation routing."""

from typing import Any, Dict, List


GENERIC_QUERY_VERBALIZATION = {
    "RelationNeighborhoodQuery": {
        "description": "用户希望查看某个图谱主体的关系邻域、可核验对象或结构化相关结果。",
        "aliases": [
            "关系对象", "可核验对象", "可验证对象", "可核验结果", "可验证结果",
            "关系结果", "关联对象", "相关对象", "关联结果", "相关结果",
            "图谱关系", "结构化关系", "当前图谱", "知识库里", "只看图谱",
            "图谱能查到", "能查到哪些对象", "能关联到哪些对象", "有哪些对象",
            "有哪些答案项", "答案项", "查询入口", "作为主体", "关系邻域",
            "周边对象", "邻接对象", "直接关联", "直接关系", "直接连接",
        ],
    },
    "TypedRelationExpansionQuery": {
        "description": "用户希望查看某个主体关联到的某类对象，如相关政策、产品、机构、企业、地区、行业或特征。",
        "aliases": [
            "相关政策", "关联政策", "政策依据", "支持政策",
            "相关产品", "关联产品", "科技金融产品", "金融产品", "产品工具",
            "相关机构", "关联机构", "金融机构", "提供机构", "银行",
            "相关企业", "关联企业", "服务企业", "客户", "企业名单",
            "相关地区", "关联地区", "区域", "地域分布",
            "相关行业", "关联行业", "产业", "产业方向", "行业分布",
            "相关特征", "企业画像", "企业特征", "资质", "信用特征",
        ],
    },
}


GENERIC_TARGET_TYPE_VERBALIZATION = [
    ("QualificationCreditFeature", [
        "企业画像", "企业特征", "企业资质", "信用特征", "资质特征", "资质", "信用",
        "哪类企业", "企业类型", "支持对象", "适配对象", "服务对象特征",
    ]),
    ("IndustrySegment", [
        "行业", "产业", "产业方向", "重点产业", "行业分布", "产业分布", "赛道",
    ]),
    ("Region", [
        "地区", "区域", "地域", "地方", "城市", "地市", "所在地区", "区域分布", "地域分布",
    ]),
    ("FinancialProduct", [
        "科技金融产品", "金融产品", "产品或工具", "产品工具", "具体工具", "融资产品", "信贷产品", "产品",
    ]),
    ("Policy", [
        "政策文件", "政策依据", "支持政策", "支撑政策", "相关政策", "哪些政策", "政策",
    ]),
    ("FinancialInstitution", [
        "金融机构", "提供机构", "办理机构", "银行", "分行", "支行", "机构",
    ]),
    ("GovernmentAgency", [
        "发布部门", "制定部门", "主管部门", "政府部门", "部门", "单位",
    ]),
    ("Enterprise", [
        "相关企业", "关联企业", "服务企业", "支持企业", "客户企业", "客户", "企业名单",
        "具体企业", "企业列表", "哪些企业", "企业",
    ]),
    ("LoanEvent", [
        "贷款事件", "融资事件", "授信事件", "放款记录", "贷款", "融资", "授信",
    ]),
]


GENERIC_RELATION_EXPANSION_REGISTRY = {
    "Policy": {
        "default_mode": "auto",
        "default_target_order": [
            "QualificationCreditFeature", "Region", "IndustrySegment", "FinancialProduct", "GovernmentAgency",
        ],
        "allowed_base_types": {
            "FinancialProduct", "GovernmentAgency", "QualificationCreditFeature", "Region", "IndustrySegment",
        },
        "max_total": 70,
        "allow_derived_default": True,
        "derived_first_default": True,
    },
    "FinancialProduct": {
        "default_mode": "auto",
        "default_target_order": [
            "QualificationCreditFeature", "Region", "IndustrySegment", "FinancialInstitution", "Policy",
        ],
        "allowed_base_types": {
            "FinancialInstitution", "Policy", "QualificationCreditFeature", "Region", "IndustrySegment",
        },
        "max_total": 70,
        "max_total_with_enterprise": 100,
        "allow_enterprise_only_if_requested": True,
        "allow_derived_default": True,
        "derived_first_default": True,
    },
    "FinancialInstitution": {
        "default_mode": "auto",
        "default_target_order": [
            "Enterprise", "FinancialProduct", "QualificationCreditFeature", "Region", "IndustrySegment", "LoanEvent",
        ],
        "allowed_base_types": {
            "Enterprise", "FinancialProduct", "QualificationCreditFeature", "Region", "IndustrySegment", "LoanEvent",
        },
        "max_total": 220,
        "allow_derived_default": True,
        "derived_first_default": True,
    },
    "Enterprise": {
        "default_mode": "auto",
        "default_target_order": [
            "FinancialInstitution", "Policy", "FinancialProduct", "QualificationCreditFeature", "Region", "IndustrySegment",
        ],
        "allowed_base_types": {
            "FinancialInstitution", "Policy", "FinancialProduct", "QualificationCreditFeature", "Region", "IndustrySegment",
        },
        "max_total": 90,
        "allow_derived_default": False,
        "derived_first_default": True,
    },
    "default": {
        "default_mode": "auto",
        "default_target_order": [
            "Policy", "FinancialProduct", "FinancialInstitution", "QualificationCreditFeature", "Region", "IndustrySegment", "Enterprise",
        ],
        "allowed_base_types": {
            "Policy", "FinancialProduct", "FinancialInstitution", "QualificationCreditFeature", "Region", "IndustrySegment", "Enterprise",
        },
        "max_total": 90,
        "allow_derived_default": False,
        "derived_first_default": True,
    },
}


def _generic_match_any(text: str, terms: List[str]) -> bool:
    return any(t and t in text for t in terms)


def _generic_relation_intent_alias_hit(query: str) -> bool:
    q = str(query or "")
    for spec in GENERIC_QUERY_VERBALIZATION.values():
        if _generic_match_any(q, spec.get("aliases") or []):
            return True
    return False


def is_generic_relation_query(query: Any) -> bool:
    q = str(query or "").strip()
    if not q:
        return False

    if _generic_relation_intent_alias_hit(q):
        return True

    graph_terms = ["图谱", "知识库", "科技金融生态", "结构化关系", "当前系统的数据", "现有图谱证据", "当前关系链"]
    object_terms = ["对象", "结果", "答案", "关联", "相关", "能查到", "检索", "周边", "邻域"]
    return _generic_match_any(q, graph_terms) and _generic_match_any(q, object_terms)


def _strip_namespace_label(value: str) -> str:
    value = str(value or "").strip().strip("`")
    if "." in value:
        return value.split(".")[-1]
    return value


def _has_type(types: set, *wanted: str) -> bool:
    return any(x in types for x in wanted)


def _generic_relation_primary_subject_type(subject_types: set) -> str:
    for t in [
        "Policy", "FinancialProduct", "FinancialInstitution", "Enterprise",
        "GovernmentAgency", "QualificationCreditFeature", "Region", "IndustrySegment",
        "LoanEvent", "SubsidyEvent", "ServicePlatform",
    ]:
        if _has_type(subject_types, t):
            return t
    for t in sorted(subject_types or []):
        if t:
            return _strip_namespace_label(t)
    return "default"


def _generic_relation_policy_for_subject(subject_types: set) -> Dict[str, Any]:
    primary = _generic_relation_primary_subject_type(subject_types)
    return dict(GENERIC_RELATION_EXPANSION_REGISTRY.get(primary) or GENERIC_RELATION_EXPANSION_REGISTRY["default"])


def _generic_query_need_enterprise(query: str) -> bool:
    q = str(query or "")
    return _generic_match_any(q, [
        "相关企业", "关联企业", "企业名单", "具体企业", "企业列表", "哪些企业",
        "客户", "客户名单", "服务对象", "贷款对象", "融资对象", "支持企业", "服务企业",
    ])


def _generic_query_allows_enterprise_derivation(query: str) -> bool:
    q = str(query or "")
    strong_terms = [
        "按规则",
        "按照规则",
        "根据规则",
        "基于规则",
        "规则推理",
        "规则匹配",
        "当前规则",
        "基于特征",
        "从特征",
        "从行业",
        "从地区",
        "从区域",
        "从资质",
        "行业地区资质",
        "行业、地区、资质",
        "行业/地区/资质",
        "可能匹配",
        "潜在匹配",
        "可能适合",
        "潜在适配",
    ]
    return any(x in q for x in strong_terms)


def _infer_generic_relation_target_types(query: str, subject: str = "") -> List[str]:
    q = str(query or "")
    intent_q = q.replace(str(subject or ""), "") if subject else q
    for noise in [
        "政策、产品、企业或机构关系", "政策、产品、企业或机构",
        "政策产品企业机构关系", "政策产品企业机构",
        "政策/产品/企业/机构", "政策、产品、企业、机构",
    ]:
        intent_q = intent_q.replace(noise, "")

    out = []
    feature_hit = _generic_match_any(intent_q, dict(GENERIC_TARGET_TYPE_VERBALIZATION).get("QualificationCreditFeature", []))
    for target_type, aliases in GENERIC_TARGET_TYPE_VERBALIZATION:
        if target_type == "Enterprise" and feature_hit:
            enterprise_specific = ["相关企业", "关联企业", "企业名单", "具体企业", "企业列表", "哪些企业", "客户", "服务企业"]
            if not _generic_match_any(intent_q, enterprise_specific):
                continue
        if _generic_match_any(intent_q, aliases):
            if target_type not in out:
                out.append(target_type)
    return out


def _infer_generic_relation_expansion_mode(query: str) -> str:
    q = str(query or "")
    hard_direct_terms = ["只看直接", "仅看直接", "不展开", "不要展开", "不需要扩展", "不要扩展", "一跳关系", "只要一跳"]
    derived_terms = ["扩展关系", "间接关联", "派生关系", "通过产品链", "沿关系链", "多跳关系"]
    if _generic_match_any(q, hard_direct_terms):
        return "direct"
    if _generic_match_any(q, derived_terms):
        return "derived"
    return "auto"


def _unique(values: List[str]) -> List[str]:
    out = []
    for value in values:
        value = str(value or "").strip()
        if value and value not in out:
            out.append(value)
    return out


def infer_generic_relation_intent(query: Any, subject_types: set, subject: str = "") -> Dict[str, Any]:
    q = str(query or "")
    subject_types = set(subject_types or [])
    policy = _generic_relation_policy_for_subject(subject_types)
    primary_type = _generic_relation_primary_subject_type(subject_types)
    mode = _infer_generic_relation_expansion_mode(q)
    target_types = _infer_generic_relation_target_types(q, subject)
    allow_enterprise_derivation = _generic_query_allows_enterprise_derivation(q)

    if mode == "direct":
        include_derived = False
    elif mode == "derived":
        include_derived = True
    elif target_types:
        include_derived = bool(policy.get("allow_derived_default", False))
        if primary_type == "Enterprise" and not allow_enterprise_derivation:
            include_derived = False
    else:
        include_derived = bool(policy.get("allow_derived_default", False))
        if primary_type == "Enterprise" and not allow_enterprise_derivation:
            include_derived = False

    if not target_types:
        target_types = list(policy.get("default_target_order") or GENERIC_RELATION_EXPANSION_REGISTRY["default"]["default_target_order"])

    if primary_type == "FinancialProduct" and "Enterprise" in target_types and not _generic_query_need_enterprise(q):
        target_types = [t for t in target_types if t != "Enterprise"]

    return {
        "mode": "typed" if _infer_generic_relation_target_types(q, subject) else ("direct" if mode == "direct" else "default"),
        "expansion_mode": mode,
        "target_types": _unique(target_types),
        "include_derived": include_derived,
        "direct_only": mode == "direct",
        "allow_enterprise_derivation": allow_enterprise_derivation,
        "subject_primary_type": primary_type,
        "registry_policy": {
            "max_total": policy.get("max_total"),
            "default_target_order": policy.get("default_target_order"),
            "allow_derived_default": policy.get("allow_derived_default"),
        },
    }


__all__ = [
    "infer_generic_relation_intent",
    "is_generic_relation_query",
]
