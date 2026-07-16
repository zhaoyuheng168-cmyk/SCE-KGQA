"""Small, dependency-free SCE-KGQA demonstration engine.

This module is intentionally limited to the curated sample graph. It exposes
the same ideas as the research system without claiming to reproduce the full
1300-question evaluation runtime.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .schema import is_allowed


@dataclass(frozen=True)
class Entity:
    id: str
    name: str
    type: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class Relation:
    source: str
    type: str
    target: str
    layer: str
    support: str


@dataclass
class AnswerResult:
    question: str
    answers: list[str]
    answer_type: str
    route: str
    normalized_entities: list[dict[str, str]] = field(default_factory=list)
    paths: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    checks: dict[str, bool] = field(default_factory=dict)
    refused: bool = False
    refusal_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SampleGraph:
    def __init__(self, payload: dict[str, Any]):
        self.metadata = dict(payload.get("metadata") or {})
        self.entities = {
            row["id"]: Entity(
                id=row["id"],
                name=row["name"],
                type=row["type"],
                aliases=tuple(row.get("aliases") or ()),
            )
            for row in payload.get("entities") or []
        }
        self.relations = [Relation(**row) for row in payload.get("relations") or []]
        self.evidence = list(payload.get("evidence") or [])

    @classmethod
    def from_path(cls, path: Path) -> "SampleGraph":
        with path.open("r", encoding="utf-8") as handle:
            return cls(json.load(handle))

    @staticmethod
    def _normalize_text(text: str) -> str:
        return re.sub(r"\s+", "", str(text or "")).replace("“", "").replace("”", "")

    def ground_entities(self, question: str) -> list[Entity]:
        normalized = self._normalize_text(question)
        candidates: list[tuple[int, Entity]] = []
        for entity in self.entities.values():
            mentions = (entity.name,) + entity.aliases
            matched = max((len(item) for item in mentions if item and item in normalized), default=0)
            if matched:
                candidates.append((matched, entity))
        candidates.sort(key=lambda item: (-item[0], item[1].id))
        grounded: list[Entity] = []
        for _, entity in candidates:
            if entity.id not in {item.id for item in grounded}:
                grounded.append(entity)
        return grounded

    def outgoing(self, entity_id: str, relation_type: str) -> list[tuple[Relation, Entity]]:
        rows = []
        for relation in self.relations:
            if relation.source == entity_id and relation.type == relation_type:
                rows.append((relation, self.entities[relation.target]))
        return rows

    def incoming(self, entity_id: str, relation_type: str) -> list[tuple[Relation, Entity]]:
        rows = []
        for relation in self.relations:
            if relation.target == entity_id and relation.type == relation_type:
                rows.append((relation, self.entities[relation.source]))
        return rows


class SCEKGQADemo:
    """Route sample questions through grounding, Schema checks and execution."""

    def __init__(self, graph: SampleGraph):
        self.graph = graph

    @classmethod
    def from_path(cls, path: Path) -> "SCEKGQADemo":
        return cls(SampleGraph.from_path(path))

    def answer(self, question: str) -> AnswerResult:
        question = str(question or "").strip()
        grounded = self.graph.ground_entities(question)
        normalized = [
            {"mention": self._matched_mention(question, entity), "entity": entity.name, "type": entity.type}
            for entity in grounded
        ]
        if not question:
            return self._refuse(question, normalized, "问题为空。")
        if not grounded:
            return self._refuse(question, normalized, "主体实体未能落到公开样例图谱。")

        products = self._of_type(grounded, "FinancialProduct")
        institutions = self._of_type(grounded, "FinancialInstitution")
        enterprises = self._of_type(grounded, "Enterprise")
        features = self._of_type(grounded, "QualificationCreditFeature")

        if products and any(token in question for token in ("依据", "证据", "来源")):
            return self._evidence_answer(question, normalized, products[0])
        if products and features and "企业" in question:
            return self._rule_filter(question, normalized, products[0], features[0])
        if products and institutions and "特征" in question:
            return self._institution_product_features(
                question, normalized, institutions[0], products[0]
            )
        if products and any(token in question for token in ("哪家", "哪个机构", "谁提供", "由谁")):
            return self._reverse_provider(question, normalized, products[0])
        if institutions and "产品" in question and "企业" not in question:
            return self._institution_products(question, normalized, institutions[0])
        if products and any(token in question for token in ("企业", "服务")):
            return self._product_enterprises(question, normalized, products[0])
        if enterprises and any(token in question for token in ("哪里", "地区", "位于")):
            return self._enterprise_attribute(
                question, normalized, enterprises[0], "locatedIn", "Region", "direct_graph"
            )
        if enterprises and any(token in question for token in ("产业", "行业")):
            return self._enterprise_attribute(
                question,
                normalized,
                enterprises[0],
                "belongsToIndustry",
                "IndustrySegment",
                "direct_graph",
            )
        return self._refuse(
            question,
            normalized,
            "样例图谱未配置与该问法对应的合法执行计划。",
        )

    @staticmethod
    def _of_type(entities: Iterable[Entity], entity_type: str) -> list[Entity]:
        return [entity for entity in entities if entity.type == entity_type]

    @staticmethod
    def _matched_mention(question: str, entity: Entity) -> str:
        for mention in sorted((entity.name,) + entity.aliases, key=len, reverse=True):
            if mention and mention in question:
                return mention
        return entity.name

    def _institution_products(
        self, question: str, normalized: list[dict[str, str]], institution: Entity
    ) -> AnswerResult:
        rows = self.graph.outgoing(institution.id, "providesProduct")
        chains = [[(institution, relation, product)] for relation, product in rows]
        return self._success(question, normalized, "direct_graph", "FinancialProduct", chains)

    def _reverse_provider(
        self, question: str, normalized: list[dict[str, str]], product: Entity
    ) -> AnswerResult:
        rows = self.graph.incoming(product.id, "providesProduct")
        chains = [[(institution, relation, product)] for relation, institution in rows]
        providers = [institution for _, institution in rows]
        return self._success(
            question,
            normalized,
            "reverse_relation",
            "FinancialInstitution",
            chains,
            answer_entities=providers,
        )

    def _product_enterprises(
        self, question: str, normalized: list[dict[str, str]], product: Entity
    ) -> AnswerResult:
        rows = self.graph.outgoing(product.id, "servesEnterprise")
        chains = [[(product, relation, enterprise)] for relation, enterprise in rows]
        return self._success(question, normalized, "schema_multihop", "Enterprise", chains)

    def _enterprise_attribute(
        self,
        question: str,
        normalized: list[dict[str, str]],
        enterprise: Entity,
        relation_type: str,
        answer_type: str,
        route: str,
    ) -> AnswerResult:
        rows = self.graph.outgoing(enterprise.id, relation_type)
        chains = [[(enterprise, relation, target)] for relation, target in rows]
        return self._success(question, normalized, route, answer_type, chains)

    def _rule_filter(
        self,
        question: str,
        normalized: list[dict[str, str]],
        product: Entity,
        feature: Entity,
    ) -> AnswerResult:
        chains = []
        for serves_relation, enterprise in self.graph.outgoing(product.id, "servesEnterprise"):
            for feature_relation, candidate_feature in self.graph.outgoing(enterprise.id, "hasFeature"):
                if candidate_feature.id == feature.id:
                    chains.append(
                        [
                            (product, serves_relation, enterprise),
                            (enterprise, feature_relation, candidate_feature),
                        ]
                    )
        return self._success(
            question,
            normalized,
            "rule_filter",
            "Enterprise",
            chains,
            answer_position=-2,
        )

    def _institution_product_features(
        self,
        question: str,
        normalized: list[dict[str, str]],
        institution: Entity,
        product: Entity,
    ) -> AnswerResult:
        provider_edges = [
            relation
            for relation, candidate in self.graph.outgoing(institution.id, "providesProduct")
            if candidate.id == product.id
        ]
        if not provider_edges:
            return self._refuse(question, normalized, "机构与产品之间不存在合法提供关系。")
        chains = []
        for serves_relation, enterprise in self.graph.outgoing(product.id, "servesEnterprise"):
            for feature_relation, feature in self.graph.outgoing(enterprise.id, "hasFeature"):
                chains.append(
                    [
                        (institution, provider_edges[0], product),
                        (product, serves_relation, enterprise),
                        (enterprise, feature_relation, feature),
                    ]
                )
        return self._success(
            question, normalized, "schema_multihop", "QualificationCreditFeature", chains
        )

    def _evidence_answer(
        self, question: str, normalized: list[dict[str, str]], entity: Entity
    ) -> AnswerResult:
        snippets = [
            row["text"]
            for row in self.graph.evidence
            if row.get("entity_id") == entity.id and row.get("text")
        ]
        if not snippets:
            return self._refuse(question, normalized, "公开样例中没有可返回的证据片段。")
        return AnswerResult(
            question=question,
            answers=snippets,
            answer_type="EvidenceSnippet",
            route="evidence_lookup",
            normalized_entities=normalized,
            evidence=snippets,
            checks={"schema_valid": True, "task_valid": True, "support_valid": True},
        )

    def _success(
        self,
        question: str,
        normalized: list[dict[str, str]],
        route: str,
        answer_type: str,
        chains: list[list[tuple[Entity, Relation, Entity]]],
        answer_position: int = -1,
        answer_entities: list[Entity] | None = None,
    ) -> AnswerResult:
        if not chains:
            return self._refuse(question, normalized, "合法路径执行后未得到样例答案。")
        schema_valid = all(
            is_allowed(source.type, relation.type, target.type)
            for chain in chains
            for source, relation, target in chain
        )
        if answer_entities is None:
            answer_entities = [chain[answer_position][2] for chain in chains]
        task_valid = all(entity.type == answer_type for entity in answer_entities)
        evidence = self._collect_support(chains)
        if not schema_valid or not task_valid:
            return self._refuse(question, normalized, "候选结果未通过 Schema 或目标类型校验。")
        answers = list(dict.fromkeys(entity.name for entity in answer_entities))
        paths = list(dict.fromkeys(self._format_chain(chain) for chain in chains))
        return AnswerResult(
            question=question,
            answers=answers,
            answer_type=answer_type,
            route=route,
            normalized_entities=normalized,
            paths=paths,
            evidence=evidence,
            checks={
                "schema_valid": schema_valid,
                "task_valid": task_valid,
                "support_valid": bool(evidence),
            },
        )

    @staticmethod
    def _format_chain(chain: list[tuple[Entity, Relation, Entity]]) -> str:
        if not chain:
            return ""
        text = chain[0][0].name
        for _, relation, target in chain:
            text += f" -[{relation.type}]-> {target.name}"
        return text

    @staticmethod
    def _collect_support(chains: list[list[tuple[Entity, Relation, Entity]]]) -> list[str]:
        evidence = []
        for chain in chains:
            for _, relation, _ in chain:
                note = f"{relation.type} ({relation.layer}): {relation.support}"
                if note not in evidence:
                    evidence.append(note)
        return evidence

    @staticmethod
    def _refuse(
        question: str, normalized: list[dict[str, str]], reason: str
    ) -> AnswerResult:
        return AnswerResult(
            question=question,
            answers=[],
            answer_type="",
            route="boundary_refusal",
            normalized_entities=normalized,
            checks={"schema_valid": False, "task_valid": False, "support_valid": False},
            refused=True,
            refusal_reason=reason,
        )


def load_default_engine() -> SCEKGQADemo:
    repo_root = Path(__file__).resolve().parents[2]
    raw_path = os.getenv("SCE_KGQA_SAMPLE_DATA", "data/samples/graph_sample.json")
    data_path = Path(raw_path)
    if not data_path.is_absolute():
        data_path = repo_root / data_path
    return SCEKGQADemo.from_path(data_path)
