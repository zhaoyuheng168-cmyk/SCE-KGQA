"""Domain Schema used by the lightweight showcase."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SchemaRelation:
    source_type: str
    relation: str
    target_type: str


ALLOWED_RELATIONS = {
    SchemaRelation("FinancialInstitution", "providesProduct", "FinancialProduct"),
    SchemaRelation("FinancialProduct", "servesEnterprise", "Enterprise"),
    SchemaRelation("Enterprise", "hasFeature", "QualificationCreditFeature"),
    SchemaRelation("Enterprise", "locatedIn", "Region"),
    SchemaRelation("Enterprise", "belongsToIndustry", "IndustrySegment"),
}


TYPE_LABELS = {
    "FinancialInstitution": "金融机构",
    "FinancialProduct": "金融产品",
    "Enterprise": "企业",
    "QualificationCreditFeature": "资质/信用特征",
    "Region": "地区",
    "IndustrySegment": "产业",
    "EvidenceSnippet": "证据片段",
}


def is_allowed(source_type: str, relation: str, target_type: str) -> bool:
    """Return whether a directed relation is legal in the sample Schema."""

    return SchemaRelation(source_type, relation, target_type) in ALLOWED_RELATIONS
