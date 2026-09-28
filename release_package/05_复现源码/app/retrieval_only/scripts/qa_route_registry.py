# -*- coding: utf-8 -*-
"""
Read-only qtype registry for the V8/V7 KGQA refactor.

This module mirrors the current V8 single-hop, event, and rule qtype metadata.
It deliberately does not import V8, build Cypher, connect Neo4j, or alter routing.
"""

from copy import deepcopy
from typing import Any, Dict, List, Optional


QTYPE_REGISTRY: Dict[str, Dict[str, Any]] = {
    "enterprise_loan_support": {
        "qtype": "enterprise_loan_support",
        "family": "event",
        "subject_type": "Enterprise",
        "target_type": "FinancialInstitution",
        "path": ["FinancialInstitution", "issuesLoan", "LoanEvent", "loanToEnterprise", "Enterprise"],
        "direction": "reverse",
        "graph_direction": "in",
        "source_category": "unstructured_graph",
        "answer_template": "从当前图谱看，{subject}的相关结果包括：{answers}。",
        "allow_kag_fallback": True,
        "allow_v7_fallback": True,
        "priority": 10,
    },
    "institution_loan_enterprise": {
        "qtype": "institution_loan_enterprise",
        "family": "event",
        "subject_type": "FinancialInstitution",
        "target_type": "Enterprise",
        "path": ["FinancialInstitution", "issuesLoan", "LoanEvent", "loanToEnterprise", "Enterprise"],
        "direction": "forward",
        "graph_direction": "out",
        "source_category": "unstructured_graph",
        "answer_template": "从当前图谱看，{subject}的相关结果包括：{answers}。",
        "allow_kag_fallback": True,
        "allow_v7_fallback": True,
        "priority": 20,
    },
    "freeqa_institution_product_overview": {
        "qtype": "freeqa_institution_product_overview",
        "family": "singlehop",
        "subject_type": "FinancialInstitution",
        "target_type": "FinancialProduct",
        "relation": "providesProduct",
        "direction": "forward",
        "graph_direction": "out",
        "source_category": "structured_graph",
        "answer_template": "从当前图谱看，{subject}的相关结果包括：{answers}。",
        "allow_kag_fallback": True,
        "allow_v7_fallback": True,
        "priority": 30,
    },
    "product_provider": {
        "qtype": "product_provider",
        "family": "singlehop",
        "subject_type": "FinancialProduct",
        "target_type": "FinancialInstitution",
        "relation": "providesProduct",
        "direction": "reverse",
        "graph_direction": "in",
        "source_category": "structured_graph",
        "answer_template": "从当前图谱看，{subject}的相关结果包括：{answers}。",
        "allow_kag_fallback": True,
        "allow_v7_fallback": True,
        "priority": 40,
    },
    "policy_supports_product": {
        "qtype": "policy_supports_product",
        "family": "singlehop",
        "subject_type": "Policy",
        "target_type": "FinancialProduct",
        "relation": "supports",
        "direction": "forward",
        "graph_direction": "out",
        "source_category": "structured_graph",
        "answer_template": "从当前图谱看，{subject}的相关结果包括：{answers}。",
        "allow_kag_fallback": True,
        "allow_v7_fallback": True,
        "priority": 50,
    },
    "product_supported_by_policies": {
        "qtype": "product_supported_by_policies",
        "family": "singlehop",
        "subject_type": "FinancialProduct",
        "target_type": "Policy",
        "relation": "supports",
        "direction": "reverse",
        "graph_direction": "in",
        "source_category": "structured_graph",
        "answer_template": "从当前图谱看，{subject}的相关结果包括：{answers}。",
        "allow_kag_fallback": True,
        "allow_v7_fallback": True,
        "priority": 60,
    },
    "agency_issues_policy": {
        "qtype": "agency_issues_policy",
        "family": "singlehop",
        "subject_type": "GovernmentAgency",
        "target_type": "Policy",
        "relation": "issues",
        "direction": "forward",
        "graph_direction": "out",
        "source_category": "structured_graph",
        "answer_template": "从当前图谱看，{subject}的相关结果包括：{answers}。",
        "allow_kag_fallback": True,
        "allow_v7_fallback": True,
        "priority": 70,
    },
    "policy_issued_by_agency": {
        "qtype": "policy_issued_by_agency",
        "family": "singlehop",
        "subject_type": "Policy",
        "target_type": "GovernmentAgency",
        "relation": "issues",
        "direction": "reverse",
        "graph_direction": "in",
        "source_category": "structured_graph",
        "answer_template": "从当前图谱看，{subject}的相关结果包括：{answers}。",
        "allow_kag_fallback": True,
        "allow_v7_fallback": True,
        "priority": 80,
    },
    "rule_enterprise_potential_policy": {
        "qtype": "rule_enterprise_potential_policy",
        "family": "rule",
        "subject_type": "Enterprise",
        "target_type": "Policy",
        "relation": "potentiallyMatchesPolicy",
        "direction": "forward",
        "graph_direction": "out",
        "source_category": "rule_reasoning",
        "answer_template": "根据当前图谱规则推理，{subject}的相关结果包括：{answers}。",
        "allow_kag_fallback": True,
        "allow_v7_fallback": True,
        "priority": 90,
    },
    "rule_enterprise_potential_product": {
        "qtype": "rule_enterprise_potential_product",
        "family": "rule",
        "subject_type": "Enterprise",
        "target_type": "FinancialProduct",
        "relation": "potentiallyMatchesProduct",
        "direction": "forward",
        "graph_direction": "out",
        "source_category": "rule_reasoning",
        "answer_template": "根据当前图谱规则推理，{subject}的相关结果包括：{answers}。",
        "allow_kag_fallback": True,
        "allow_v7_fallback": True,
        "priority": 100,
    },
    "rule_policy_coverage_industry": {
        "qtype": "rule_policy_coverage_industry",
        "family": "rule",
        "subject_type": "Policy",
        "target_type": "IndustrySegment",
        "relation": "hasCoverageIndustry",
        "direction": "forward",
        "graph_direction": "out",
        "source_category": "rule_reasoning",
        "answer_template": "根据当前图谱规则推理，{subject}的相关结果包括：{answers}。",
        "allow_kag_fallback": True,
        "allow_v7_fallback": True,
        "priority": 110,
    },
    "rule_policy_coverage_region": {
        "qtype": "rule_policy_coverage_region",
        "family": "rule",
        "subject_type": "Policy",
        "target_type": "Region",
        "relation": "hasCoverageRegion",
        "direction": "forward",
        "graph_direction": "out",
        "source_category": "rule_reasoning",
        "answer_template": "根据当前图谱规则推理，{subject}的相关结果包括：{answers}。",
        "allow_kag_fallback": True,
        "allow_v7_fallback": True,
        "priority": 120,
    },
    "rule_product_fit_enterprise_feature": {
        "qtype": "rule_product_fit_enterprise_feature",
        "family": "rule",
        "subject_type": "FinancialProduct",
        "target_type": "QualificationCreditFeature",
        "relation": "fitsEnterpriseFeature",
        "direction": "forward",
        "graph_direction": "out",
        "source_category": "rule_reasoning",
        "answer_template": "根据当前图谱规则推理，{subject}的相关结果包括：{answers}。",
        "allow_kag_fallback": True,
        "allow_v7_fallback": True,
        "priority": 130,
    },
}


def get_qtype_spec(qtype: str) -> Optional[Dict[str, Any]]:
    spec = QTYPE_REGISTRY.get(str(qtype or "").strip())
    return deepcopy(spec) if spec else None


def is_registered_qtype(qtype: str) -> bool:
    return str(qtype or "").strip() in QTYPE_REGISTRY


def get_expected_subject_types(qtype: str) -> List[str]:
    spec = QTYPE_REGISTRY.get(str(qtype or "").strip())
    if not spec:
        return []
    value = spec.get("subject_type")
    if isinstance(value, list):
        return [str(v) for v in value if str(v or "").strip()]
    if isinstance(value, tuple):
        return [str(v) for v in value if str(v or "").strip()]
    if isinstance(value, set):
        return sorted(str(v) for v in value if str(v or "").strip())
    return [str(value)] if str(value or "").strip() else []


def get_source_category(qtype: str) -> str:
    spec = QTYPE_REGISTRY.get(str(qtype or "").strip())
    return str(spec.get("source_category", "") or "") if spec else ""


def get_graph_direction(qtype: str) -> str:
    spec = QTYPE_REGISTRY.get(str(qtype or "").strip())
    return str(spec.get("graph_direction", "") or "") if spec else ""


def list_registered_qtypes() -> List[str]:
    return list(QTYPE_REGISTRY.keys())


def build_expected_subject_type_map() -> Dict[str, List[str]]:
    return {qtype: get_expected_subject_types(qtype) for qtype in list_registered_qtypes()}
