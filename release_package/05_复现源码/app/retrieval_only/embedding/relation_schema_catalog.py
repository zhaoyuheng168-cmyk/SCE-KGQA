# -*- coding: utf-8 -*-
"""KG relation schema descriptions used for relation embedding grounding."""

from __future__ import annotations

from typing import Dict, List


RELATION_SCHEMA_ROWS: List[Dict[str, object]] = [
    {
        "relation": "issuesLoan",
        "source_type": "FinancialInstitution",
        "target_type": "LoanEvent",
        "question_type": "institution_loan_enterprise",
        "description": "金融机构发放、投放、办理、给予、提供贷款或授信，形成贷款事件。",
    },
    {
        "relation": "loanToEnterprise",
        "source_type": "LoanEvent",
        "target_type": "Enterprise",
        "question_type": "enterprise_loan_support",
        "description": "贷款事件指向获得贷款、获贷、得到融资支持或授信支持的企业。",
    },
    {
        "relation": "providesProduct",
        "source_type": "FinancialInstitution",
        "target_type": "FinancialProduct",
        "question_type": "product_provider",
        "description": "金融机构提供、推出、办理、承接某个科技金融产品或贷款产品。",
    },
    {
        "relation": "supports",
        "source_type": "Policy",
        "target_type": "FinancialProduct",
        "question_type": "product_supported_by_policies",
        "description": "政策、通知、方案、办法支持某个金融产品，或产品背后的政策依据。",
    },
    {
        "relation": "servesEnterprise",
        "source_type": "FinancialProduct",
        "target_type": "Enterprise",
        "question_type": "generic_relation_objects",
        "description": "金融产品服务、面向、覆盖、适用于企业客户或目标企业。",
    },
    {
        "relation": "fitsEnterpriseFeature",
        "source_type": "FinancialProduct",
        "target_type": "QualificationCreditFeature",
        "question_type": "rule_product_fit_enterprise_feature",
        "description": "金融产品适配、适合、面向某类企业特征、企业画像、企业资质或信用特征。",
    },
    {
        "relation": "belongsToIndustry",
        "source_type": "Enterprise",
        "target_type": "IndustrySegment",
        "question_type": "generic_relation_objects",
        "description": "企业、政策或对象属于、涉及、覆盖某个行业、产业方向、领域或赛道。",
    },
    {
        "relation": "locatedIn",
        "source_type": "Enterprise",
        "target_type": "Region",
        "question_type": "generic_relation_objects",
        "description": "企业、政策任务或对象位于、覆盖、涉及某个地区、区域、城市或地市。",
    },
    {
        "relation": "issues",
        "source_type": "GovernmentAgency",
        "target_type": "Policy",
        "question_type": "policy_issued_by_agency",
        "description": "政府部门、主管单位发布、出台、印发、制定某项政策、通知、方案或办法。",
    },
    {
        "relation": "targetsEnterprise",
        "source_type": "Policy",
        "target_type": "Enterprise",
        "question_type": "generic_relation_objects",
        "description": "政策面向、覆盖、服务、支持或作用于某些企业主体或目标企业。",
    },
    {
        "relation": "hasFeature",
        "source_type": "Enterprise",
        "target_type": "QualificationCreditFeature",
        "question_type": "generic_relation_objects",
        "description": "企业具有某类企业特征、企业画像、资质标签、信用特征或企业类型。",
    },
    {
        "relation": "potentiallyMatchesPolicy",
        "source_type": "Enterprise",
        "target_type": "Policy",
        "question_type": "rule_enterprise_potential_policy",
        "description": "规则推理认为企业可能匹配、适合、可申报或潜在适用某项政策。",
    },
    {
        "relation": "potentiallyMatchesProduct",
        "source_type": "Enterprise",
        "target_type": "FinancialProduct",
        "question_type": "rule_enterprise_potential_product",
        "description": "规则推理认为企业可能匹配、适合、可申请或潜在适用某个金融产品。",
    },
    {
        "relation": "hasCoverageIndustry",
        "source_type": "Policy",
        "target_type": "IndustrySegment",
        "question_type": "rule_policy_coverage_industry",
        "description": "政策覆盖、涉及、支持、面向某些产业方向、行业领域、赛道或产业链。",
    },
    {
        "relation": "hasCoverageRegion",
        "source_type": "Policy",
        "target_type": "Region",
        "question_type": "rule_policy_coverage_region",
        "description": "政策覆盖、涉及、适用于某些地区、区域、城市、地市或试点范围。",
    },
    {
        "relation": "benefitsEnterprise",
        "source_type": "SubsidyEvent",
        "target_type": "Enterprise",
        "question_type": "enterprise_reverse_subsidy_event",
        "description": "奖补事件、补贴事件、资助事件惠及、支持、补助或奖励某家企业。",
    },
    {
        "relation": "grantsSubsidy",
        "source_type": "GovernmentAgency",
        "target_type": "SubsidyEvent",
        "question_type": "generic_relation_objects",
        "description": "政府部门发放、给予、组织、发布或形成奖补事件、补贴事件、资助事件。",
    },
]


def relation_embedding_text(row: Dict[str, object]) -> str:
    return (
        f"图谱关系：{row.get('relation', '')}；"
        f"起点类型：{row.get('source_type', '')}；"
        f"终点类型：{row.get('target_type', '')}；"
        f"说明：{row.get('description', '')}；"
        "领域：甘肃科技金融知识图谱"
    )


__all__ = ["RELATION_SCHEMA_ROWS", "relation_embedding_text"]
