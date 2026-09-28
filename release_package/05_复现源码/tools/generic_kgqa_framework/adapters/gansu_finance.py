# -*- coding: utf-8 -*-
"""Gansu technology-finance adapter expressed as portable KGQA metadata."""

from __future__ import annotations

from typing import Dict

from ..core import DomainAdapter, EntityTypeSpec, KGQASchema, PathStep, RelationSpec, RouteSpec


def _etype(name: str, aliases=(), description: str = "") -> EntityTypeSpec:
    return EntityTypeSpec(name=name, aliases=tuple(aliases), description=description)


def _rel(name: str, src: str, dst: str, aliases=(), description: str = "") -> RelationSpec:
    return RelationSpec(name=name, src_type=src, dst_type=dst, aliases=tuple(aliases), description=description)


class GansuFinanceAdapter(DomainAdapter):
    """Adapter for the current GansuTechFinance KGQA schema."""

    name = "gansu_finance"

    def schema(self) -> KGQASchema:
        entity_types: Dict[str, EntityTypeSpec] = {
            "FinancialInstitution": _etype("FinancialInstitution", ["金融机构", "银行", "机构"]),
            "FinancialProduct": _etype("FinancialProduct", ["金融产品", "科技金融产品", "产品", "信贷产品"]),
            "Policy": _etype("Policy", ["政策", "政策文件", "方案", "通知"]),
            "Enterprise": _etype("Enterprise", ["企业", "公司", "客户企业"]),
            "GovernmentAgency": _etype("GovernmentAgency", ["政府部门", "发布部门", "主管部门"]),
            "Region": _etype("Region", ["地区", "区域", "城市", "地市"]),
            "IndustrySegment": _etype("IndustrySegment", ["行业", "产业", "赛道"]),
            "QualificationCreditFeature": _etype("QualificationCreditFeature", ["企业特征", "资质", "信用特征"]),
            "LoanEvent": _etype("LoanEvent", ["贷款事件", "融资事件", "授信事件"]),
        }
        relations: Dict[str, RelationSpec] = {
            "providesProduct": _rel("providesProduct", "FinancialInstitution", "FinancialProduct", ["提供", "推出"]),
            "supports": _rel("supports", "Policy", "FinancialProduct", ["支持", "支撑"]),
            "issues": _rel("issues", "GovernmentAgency", "Policy", ["发布", "制定"]),
            "issuesLoan": _rel("issuesLoan", "FinancialInstitution", "LoanEvent", ["发放贷款", "授信"]),
            "loanToEnterprise": _rel("loanToEnterprise", "LoanEvent", "Enterprise", ["贷款给", "支持企业"]),
            "servesEnterprise": _rel("servesEnterprise", "FinancialProduct", "Enterprise", ["服务企业", "支持企业"]),
            "locatedIn": _rel("locatedIn", "Enterprise", "Region", ["位于", "所在地区"]),
            "belongsToIndustry": _rel("belongsToIndustry", "Enterprise", "IndustrySegment", ["所属行业"]),
            "hasFeature": _rel("hasFeature", "Enterprise", "QualificationCreditFeature", ["具有特征"]),
            "fitsEnterpriseFeature": _rel("fitsEnterpriseFeature", "FinancialProduct", "QualificationCreditFeature", ["适配特征"]),
        }
        routes: Dict[str, RouteSpec] = {
            "institution_products": RouteSpec(
                qtype="institution_products",
                family="singlehop",
                subject_type="FinancialInstitution",
                target_type="FinancialProduct",
                path=[PathStep("FinancialInstitution", "providesProduct", "FinancialProduct")],
                intent_aliases=("提供哪些金融产品", "有哪些产品", "金融产品"),
                answer_template="从当前图谱看，{subject}提供的金融产品包括：{answers}。",
                priority=30,
            ),
            "product_provider": RouteSpec(
                qtype="product_provider",
                family="singlehop",
                subject_type="FinancialProduct",
                target_type="FinancialInstitution",
                path=[PathStep("FinancialProduct", "providesProduct", "FinancialInstitution", direction="in")],
                intent_aliases=("由谁提供", "提供机构", "办理机构"),
                answer_template="从当前图谱看，{subject}的提供机构包括：{answers}。",
                priority=40,
            ),
            "policy_products": RouteSpec(
                qtype="policy_products",
                family="singlehop",
                subject_type="Policy",
                target_type="FinancialProduct",
                path=[PathStep("Policy", "supports", "FinancialProduct")],
                intent_aliases=("支持哪些产品", "对应哪些产品", "金融产品"),
                answer_template="从当前图谱看，{subject}支持的金融产品包括：{answers}。",
                priority=50,
            ),
            "policy_region_overview": RouteSpec(
                qtype="policy_region_overview",
                family="multihop",
                subject_type="Policy",
                target_type="Region",
                path=[
                    PathStep("Policy", "supports", "FinancialProduct"),
                    PathStep("FinancialProduct", "servesEnterprise", "Enterprise"),
                    PathStep("Enterprise", "locatedIn", "Region"),
                ],
                intent_aliases=("覆盖哪些地区", "地区分布", "区域"),
                answer_template="从当前图谱看，{subject}通过政策-产品-企业链路覆盖到的地区包括：{answers}。",
                priority=300,
            ),
        }
        return KGQASchema(
            namespace=self.name,
            entity_types=entity_types,
            relations=relations,
            routes=routes,
            label_prefix="GansuTechFinanceDevV1Enhance",
        )

