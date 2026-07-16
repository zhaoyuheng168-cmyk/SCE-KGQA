# -*- coding: utf-8 -*-
"""Cypher template helpers for V8 graph-first query routing."""

from typing import Tuple


DEFAULT_NAMESPACE = "GansuTechFinanceDevV1Enhance"


def label(name: str, namespace: str = None) -> str:
    ns = namespace or DEFAULT_NAMESPACE
    return f"`{ns}.{name}`"


def cypher_for_from_templates(qtype: str, namespace: str = None) -> Tuple[str, str, str]:
    """
    Return cypher, answer_key, source_category.
    source_category: structured_graph / unstructured_graph / rule_reasoning
    """
    if qtype == "enterprise_loan_support":
        return f"""
MATCH (fi:{label("FinancialInstitution", namespace)})-[:issuesLoan]->(le:{label("LoanEvent", namespace)})-[:loanToEnterprise]->(e:{label("Enterprise", namespace)})
WHERE e.name CONTAINS $subject OR $subject CONTAINS e.name
RETURN DISTINCT fi.name AS answer
ORDER BY answer
""", "answer", "unstructured_graph"

    if qtype == "institution_loan_enterprise":
        return f"""
MATCH (fi:{label("FinancialInstitution", namespace)})-[:issuesLoan]->(le:{label("LoanEvent", namespace)})-[:loanToEnterprise]->(e:{label("Enterprise", namespace)})
WHERE fi.name CONTAINS $subject OR $subject CONTAINS fi.name
RETURN DISTINCT e.name AS answer
ORDER BY answer
""", "answer", "unstructured_graph"

    if qtype == "enterprise_located_region":
        return f"""
MATCH (e:{label("Enterprise", namespace)})-[:locatedIn]->(r:{label("Region", namespace)})
WHERE e.name CONTAINS $subject OR $subject CONTAINS e.name
RETURN DISTINCT r.name AS answer
UNION
MATCH (le:{label("LoanEvent", namespace)})-[:loanToEnterprise]->(e:{label("Enterprise", namespace)})-[:locatedIn]->(r:{label("Region", namespace)})
WHERE le.name CONTAINS $subject OR $subject CONTAINS le.name OR coalesce(le.remark, '') CONTAINS $subject
RETURN DISTINCT r.name AS answer
ORDER BY answer
""", "answer", "structured_graph"

    if qtype == "freeqa_institution_product_overview":
        return f"""
MATCH (fi:{label("FinancialInstitution", namespace)})-[:providesProduct]->(fp:{label("FinancialProduct", namespace)})
WHERE fi.name CONTAINS $subject OR $subject CONTAINS fi.name
RETURN DISTINCT fp.name AS answer
ORDER BY answer
""", "answer", "structured_graph"

    if qtype == "product_provider":
        return f"""
MATCH (fi:{label("FinancialInstitution", namespace)})-[:providesProduct]->(fp:{label("FinancialProduct", namespace)})
WHERE fp.name CONTAINS $subject OR $subject CONTAINS fp.name
RETURN DISTINCT fi.name AS answer
ORDER BY answer
""", "answer", "structured_graph"

    if qtype == "policy_supports_product":
        return f"""
MATCH (p:{label("Policy", namespace)})-[:supports]->(fp:{label("FinancialProduct", namespace)})
WHERE p.name CONTAINS $subject OR $subject CONTAINS p.name
RETURN DISTINCT fp.name AS answer
ORDER BY answer
""", "answer", "structured_graph"

    if qtype == "product_supported_by_policies":
        return f"""
MATCH (p:{label("Policy", namespace)})-[:supports]->(fp:{label("FinancialProduct", namespace)})
WHERE fp.name CONTAINS $subject OR $subject CONTAINS fp.name
RETURN DISTINCT p.name AS answer
ORDER BY answer
""", "answer", "structured_graph"

    if qtype == "agency_issues_policy":
        return f"""
MATCH (ga:{label("GovernmentAgency", namespace)})-[:issues]->(p:{label("Policy", namespace)})
WHERE ga.name CONTAINS $subject OR $subject CONTAINS ga.name
RETURN DISTINCT p.name AS answer
ORDER BY answer
""", "answer", "structured_graph"

    if qtype == "policy_issued_by_agency":
        return f"""
MATCH (ga:{label("GovernmentAgency", namespace)})-[:issues]->(p:{label("Policy", namespace)})
WHERE p.name CONTAINS $subject OR $subject CONTAINS p.name
RETURN DISTINCT ga.name AS answer
ORDER BY answer
""", "answer", "structured_graph"

    if qtype == "rule_enterprise_potential_policy":
        return f"""
MATCH (e:{label("Enterprise", namespace)})-[:potentiallyMatchesPolicy]->(p:{label("Policy", namespace)})
WHERE e.name CONTAINS $subject OR $subject CONTAINS e.name
RETURN DISTINCT p.name AS answer
ORDER BY answer
""", "answer", "rule_reasoning"

    if qtype == "rule_enterprise_potential_product":
        return f"""
MATCH (e:{label("Enterprise", namespace)})-[:potentiallyMatchesProduct]->(fp:{label("FinancialProduct", namespace)})
WHERE e.name CONTAINS $subject OR $subject CONTAINS e.name
RETURN DISTINCT fp.name AS answer
ORDER BY answer
""", "answer", "rule_reasoning"

    if qtype == "rule_policy_coverage_industry":
        return f"""
MATCH (p:{label("Policy", namespace)})-[:hasCoverageIndustry]->(i:{label("IndustrySegment", namespace)})
WHERE p.name CONTAINS $subject OR $subject CONTAINS p.name
RETURN DISTINCT i.name AS answer
ORDER BY answer
""", "answer", "rule_reasoning"

    if qtype == "rule_policy_coverage_region":
        return f"""
MATCH (p:{label("Policy", namespace)})-[:hasCoverageRegion]->(r:{label("Region", namespace)})
WHERE p.name CONTAINS $subject OR $subject CONTAINS p.name
RETURN DISTINCT r.name AS answer
ORDER BY answer
""", "answer", "rule_reasoning"

    if qtype == "rule_product_fit_enterprise_feature":
        return f"""
MATCH (fp:{label("FinancialProduct", namespace)})-[:fitsEnterpriseFeature]->(f:{label("QualificationCreditFeature", namespace)})
WHERE fp.name CONTAINS $subject OR $subject CONTAINS fp.name
RETURN DISTINCT f.name AS answer
ORDER BY answer
""", "answer", "rule_reasoning"

    return "", "answer", ""


__all__ = [
    "cypher_for_from_templates",
    "label",
]
