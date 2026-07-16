# -*- coding: utf-8 -*-
"""
Read-only multihop chain registry for the V8/V7 KGQA refactor.

This module mirrors V8 KAG multihop chains and V7 L9-L18 templates. It does
not import V8/V7, connect Neo4j, call LLMs, execute Cypher, or route queries.
"""

from copy import deepcopy
from typing import Any, Dict, List, Optional


def _step(src_type: str, relation: str, dst_type: str, direction: str = "out") -> Dict[str, str]:
    return {
        "src_type": src_type,
        "relation": relation,
        "dst_type": dst_type,
        "direction": direction,
    }


_POLICY_BASE_PATH = [
    _step("Policy", "supports", "FinancialProduct"),
    _step("FinancialProduct", "servesEnterprise", "Enterprise"),
]

_INSTITUTION_BASE_PATH = [
    _step("FinancialInstitution", "providesProduct", "FinancialProduct"),
    _step("FinancialProduct", "servesEnterprise", "Enterprise"),
]


MULTIHOP_CHAIN_REGISTRY: Dict[str, Dict[str, Any]] = {
    "multi_hop_policy_to_region_overview_3hop": {
        "question_type": "multi_hop_policy_to_region_overview_3hop",
        "chain_id": "policy_product_enterprise_region",
        "family": "multihop",
        "sources": ["v8_kag_registry", "v7_l9_l18"],
        "subject_family": "policy",
        "subject_type": "Policy",
        "path": _POLICY_BASE_PATH + [_step("Enterprise", "locatedIn", "Region")],
        "target_type": "Region",
        "target_kind": "overview",
        "required_constraints": [],
        "optional_constraints": [],
        "answer_template": "从当前图谱看，{subject}通过“政策→产品→企业→地区”链路最终主要覆盖到的地区包括：{answers}。",
        "return_aux": ["products", "enterprises"],
        "allow_kag_planner": True,
        "allow_v7_fallback": True,
        "priority": 300,
    },
    "multi_hop_policy_to_industry_overview_3hop": {
        "question_type": "multi_hop_policy_to_industry_overview_3hop",
        "chain_id": "policy_product_enterprise_industry",
        "family": "multihop",
        "sources": ["v8_kag_registry", "v7_l9_l18"],
        "subject_family": "policy",
        "subject_type": "Policy",
        "path": _POLICY_BASE_PATH + [_step("Enterprise", "belongsToIndustry", "IndustrySegment")],
        "target_type": "IndustrySegment",
        "target_kind": "overview",
        "required_constraints": [],
        "optional_constraints": [],
        "answer_template": "从当前图谱看，{subject}通过“政策→产品→企业→行业”链路最终主要覆盖到的行业包括：{answers}。",
        "return_aux": ["products", "enterprises"],
        "allow_kag_planner": True,
        "allow_v7_fallback": True,
        "priority": 300,
    },
    "multi_hop_policy_to_feature_overview_3hop": {
        "question_type": "multi_hop_policy_to_feature_overview_3hop",
        "chain_id": "policy_product_enterprise_feature",
        "family": "multihop",
        "sources": ["v8_kag_registry", "v7_l9_l18"],
        "subject_family": "policy",
        "subject_type": "Policy",
        "path": _POLICY_BASE_PATH + [_step("Enterprise", "hasFeature", "QualificationCreditFeature")],
        "target_type": "QualificationCreditFeature",
        "target_kind": "overview",
        "required_constraints": [],
        "optional_constraints": [],
        "answer_template": "从当前图谱看，{subject}通过“政策→产品→企业→特征”链路最终主要覆盖到的企业特征包括：{answers}。",
        "return_aux": ["products", "enterprises"],
        "allow_kag_planner": True,
        "allow_v7_fallback": True,
        "priority": 300,
    },
    "multi_hop_institution_to_region_overview_3hop": {
        "question_type": "multi_hop_institution_to_region_overview_3hop",
        "chain_id": "institution_product_enterprise_region",
        "family": "multihop",
        "sources": ["v8_kag_registry"],
        "subject_family": "institution",
        "subject_type": "FinancialInstitution",
        "path": _INSTITUTION_BASE_PATH + [_step("Enterprise", "locatedIn", "Region")],
        "target_type": "Region",
        "target_kind": "overview",
        "required_constraints": [],
        "optional_constraints": [],
        "answer_template": "从当前图谱看，{subject}通过“机构→产品→企业→地区”链路最终主要覆盖到的地区包括：{answers}。",
        "return_aux": ["products", "enterprises"],
        "allow_kag_planner": True,
        "allow_v7_fallback": False,
        "priority": 300,
    },
    "multi_hop_institution_to_industry_overview_3hop": {
        "question_type": "multi_hop_institution_to_industry_overview_3hop",
        "chain_id": "institution_product_enterprise_industry",
        "family": "multihop",
        "sources": ["v8_kag_registry", "v7_l9_l18"],
        "subject_family": "institution",
        "subject_type": "FinancialInstitution",
        "path": _INSTITUTION_BASE_PATH + [_step("Enterprise", "belongsToIndustry", "IndustrySegment")],
        "target_type": "IndustrySegment",
        "target_kind": "overview",
        "required_constraints": [],
        "optional_constraints": [],
        "answer_template": "从当前图谱看，{subject}通过“机构→产品→企业→行业”链路最终主要覆盖到的行业包括：{answers}。",
        "return_aux": ["products", "enterprises"],
        "allow_kag_planner": True,
        "allow_v7_fallback": True,
        "priority": 300,
    },
    "multi_hop_institution_to_feature_overview_3hop": {
        "question_type": "multi_hop_institution_to_feature_overview_3hop",
        "chain_id": "institution_product_enterprise_feature",
        "family": "multihop",
        "sources": ["v8_kag_registry", "v7_l9_l18"],
        "subject_family": "institution",
        "subject_type": "FinancialInstitution",
        "path": _INSTITUTION_BASE_PATH + [_step("Enterprise", "hasFeature", "QualificationCreditFeature")],
        "target_type": "QualificationCreditFeature",
        "target_kind": "overview",
        "required_constraints": [],
        "optional_constraints": [],
        "answer_template": "从当前图谱看，{subject}通过“机构→产品→企业→特征”链路最终主要覆盖到的企业特征包括：{answers}。",
        "return_aux": ["products", "enterprises"],
        "allow_kag_planner": True,
        "allow_v7_fallback": True,
        "priority": 300,
    },
    "multi_hop_policy_feature_region_enterprises_4hop": {
        "question_type": "multi_hop_policy_feature_region_enterprises_4hop",
        "chain_id": "policy_product_enterprise_feature_region_enterprises",
        "family": "multihop",
        "sources": ["v7_l9_l18"],
        "subject_family": "policy",
        "subject_type": "Policy",
        "path": _POLICY_BASE_PATH + [
            _step("Enterprise", "hasFeature", "QualificationCreditFeature"),
            _step("Enterprise", "locatedIn", "Region"),
        ],
        "target_type": "Enterprise",
        "target_kind": "enterprise_list",
        "required_constraints": ["constraint_feature", "constraint_region"],
        "optional_constraints": [],
        "answer_template": "从当前图谱看，{subject}通过“政策→产品→企业”链路，在{constraint_region}覆盖到的{constraint_feature}共有{count}家。",
        "return_aux": ["products"],
        "allow_kag_planner": False,
        "allow_v7_fallback": True,
        "priority": 100,
    },
    "multi_hop_institution_feature_region_enterprises_4hop": {
        "question_type": "multi_hop_institution_feature_region_enterprises_4hop",
        "chain_id": "institution_product_enterprise_feature_region_enterprises",
        "family": "multihop",
        "sources": ["v7_l9_l18"],
        "subject_family": "institution",
        "subject_type": "FinancialInstitution",
        "path": _INSTITUTION_BASE_PATH + [
            _step("Enterprise", "hasFeature", "QualificationCreditFeature"),
            _step("Enterprise", "locatedIn", "Region"),
        ],
        "target_type": "Enterprise",
        "target_kind": "enterprise_list",
        "required_constraints": ["constraint_feature", "constraint_region"],
        "optional_constraints": [],
        "answer_template": "从当前图谱看，{subject}通过“机构→产品→企业”链路，在{constraint_region}覆盖到的{constraint_feature}共有{count}家。",
        "return_aux": ["products"],
        "allow_kag_planner": False,
        "allow_v7_fallback": True,
        "priority": 100,
    },
    "multi_hop_policy_industry_region_enterprises_4hop": {
        "question_type": "multi_hop_policy_industry_region_enterprises_4hop",
        "chain_id": "policy_product_enterprise_industry_region_enterprises",
        "family": "multihop",
        "sources": ["v7_l9_l18"],
        "subject_family": "policy",
        "subject_type": "Policy",
        "path": _POLICY_BASE_PATH + [
            _step("Enterprise", "belongsToIndustry", "IndustrySegment"),
            _step("Enterprise", "locatedIn", "Region"),
        ],
        "target_type": "Enterprise",
        "target_kind": "enterprise_list",
        "required_constraints": ["constraint_industry", "constraint_region"],
        "optional_constraints": [],
        "answer_template": "从当前图谱看，{subject}通过“政策→产品→企业”链路，在{constraint_region}覆盖到的{constraint_industry}企业共有{count}家。",
        "return_aux": ["products"],
        "allow_kag_planner": False,
        "allow_v7_fallback": True,
        "priority": 100,
    },
    "multi_hop_institution_industry_region_enterprises_4hop": {
        "question_type": "multi_hop_institution_industry_region_enterprises_4hop",
        "chain_id": "institution_product_enterprise_industry_region_enterprises",
        "family": "multihop",
        "sources": ["v7_l9_l18"],
        "subject_family": "institution",
        "subject_type": "FinancialInstitution",
        "path": _INSTITUTION_BASE_PATH + [
            _step("Enterprise", "belongsToIndustry", "IndustrySegment"),
            _step("Enterprise", "locatedIn", "Region"),
        ],
        "target_type": "Enterprise",
        "target_kind": "enterprise_list",
        "required_constraints": ["constraint_industry", "constraint_region"],
        "optional_constraints": [],
        "answer_template": "从当前图谱看，{subject}通过“机构→产品→企业”链路，在{constraint_region}覆盖到的{constraint_industry}企业共有{count}家。",
        "return_aux": ["products"],
        "allow_kag_planner": False,
        "allow_v7_fallback": True,
        "priority": 100,
    },
    "multi_hop_policy_industry_to_region_overview_4hop": {
        "question_type": "multi_hop_policy_industry_to_region_overview_4hop",
        "chain_id": "policy_product_enterprise_industry_region_overview",
        "family": "multihop",
        "sources": ["v7_l9_l18"],
        "subject_family": "policy",
        "subject_type": "Policy",
        "path": _POLICY_BASE_PATH + [
            _step("Enterprise", "belongsToIndustry", "IndustrySegment"),
            _step("Enterprise", "locatedIn", "Region"),
        ],
        "target_type": "Region",
        "target_kind": "overview",
        "required_constraints": ["constraint_industry"],
        "optional_constraints": [],
        "answer_template": "从当前图谱看，{subject}通过“政策→产品→企业→地区”链路，在{constraint_industry}企业上主要覆盖到的地区包括：{answers}。",
        "return_aux": ["products", "enterprises"],
        "allow_kag_planner": False,
        "allow_v7_fallback": True,
        "priority": 200,
    },
}


def get_chain_spec(question_type: str) -> Optional[Dict[str, Any]]:
    spec = MULTIHOP_CHAIN_REGISTRY.get(str(question_type or "").strip())
    return deepcopy(spec) if spec else None


def is_registered_chain(question_type: str) -> bool:
    return str(question_type or "").strip() in MULTIHOP_CHAIN_REGISTRY


def list_registered_chains() -> List[Dict[str, Any]]:
    return deepcopy(list(MULTIHOP_CHAIN_REGISTRY.values()))


def list_multihop_qtypes() -> List[str]:
    return list(MULTIHOP_CHAIN_REGISTRY.keys())


def get_chain_path(question_type: str) -> List[Dict[str, str]]:
    spec = MULTIHOP_CHAIN_REGISTRY.get(str(question_type or "").strip())
    return deepcopy(spec.get("path", [])) if spec else []


def get_required_constraints(question_type: str) -> List[str]:
    spec = MULTIHOP_CHAIN_REGISTRY.get(str(question_type or "").strip())
    return deepcopy(spec.get("required_constraints", [])) if spec else []


def get_subject_type(question_type: str) -> str:
    spec = MULTIHOP_CHAIN_REGISTRY.get(str(question_type or "").strip())
    return str(spec.get("subject_type", "") or "") if spec else ""


def get_target_type(question_type: str) -> str:
    spec = MULTIHOP_CHAIN_REGISTRY.get(str(question_type or "").strip())
    return str(spec.get("target_type", "") or "") if spec else ""


def build_chain_id_map() -> Dict[str, str]:
    return {
        str(spec.get("chain_id", "") or ""): qtype
        for qtype, spec in MULTIHOP_CHAIN_REGISTRY.items()
        if str(spec.get("chain_id", "") or "").strip()
    }


def list_chains_by_source(source: str) -> List[Dict[str, Any]]:
    source = str(source or "").strip()
    if not source:
        return []
    return deepcopy([
        spec
        for spec in MULTIHOP_CHAIN_REGISTRY.values()
        if source in (spec.get("sources") or [])
    ])
