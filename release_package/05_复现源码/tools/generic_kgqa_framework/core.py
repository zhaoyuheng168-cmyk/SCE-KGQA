# -*- coding: utf-8 -*-
"""Core abstractions for a domain-adaptive KGQA framework prototype."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional, Sequence


def _clean(value: object) -> str:
    return str(value or "").strip()


def _unique(values: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for value in values:
        item = _clean(value)
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


@dataclass(frozen=True)
class EntityTypeSpec:
    """Domain-level entity type metadata."""

    name: str
    aliases: Sequence[str] = field(default_factory=tuple)
    description: str = ""


@dataclass(frozen=True)
class RelationSpec:
    """Domain-level relation metadata."""

    name: str
    src_type: str
    dst_type: str
    aliases: Sequence[str] = field(default_factory=tuple)
    description: str = ""


@dataclass(frozen=True)
class PathStep:
    """One typed graph edge in a KGQA route."""

    src_type: str
    relation: str
    dst_type: str
    direction: str = "out"


@dataclass(frozen=True)
class PathConstraints:
    """Domain-independent constraints applied while executing a typed path."""

    exclude_start_at_steps: Sequence[int] = field(default_factory=tuple)
    allow_start_as_answer: bool = False


@dataclass(frozen=True)
class RouteSpec:
    """A reusable route/question-type specification."""

    qtype: str
    family: str
    subject_type: str
    target_type: str
    path: Sequence[PathStep]
    answer_template: str
    priority: int = 100
    intent_aliases: Sequence[str] = field(default_factory=tuple)
    allow_text_evidence: bool = True
    path_constraints: PathConstraints = field(default_factory=PathConstraints)
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class KGQASchema:
    """Portable schema object consumed by the framework core."""

    namespace: str
    entity_types: Mapping[str, EntityTypeSpec]
    relations: Mapping[str, RelationSpec]
    routes: Mapping[str, RouteSpec]
    label_prefix: str = ""
    entity_linking_policy: str = "fuzzy_typed"

    def label(self, entity_type: str) -> str:
        name = _clean(entity_type)
        if not name:
            return ""
        if "." in name or not self.label_prefix:
            return name
        return f"{self.label_prefix}.{name}"


class DomainAdapter:
    """Base adapter interface for domain-specific KGQA configuration."""

    name = "base"

    def schema(self) -> KGQASchema:
        raise NotImplementedError

    def normalize_question(self, question: str) -> str:
        return _clean(question)

    def infer_target_types(self, question: str) -> List[str]:
        q = self.normalize_question(question)
        schema = self.schema()
        hits: List[str] = []
        for type_name, spec in schema.entity_types.items():
            terms = [spec.name] + list(spec.aliases)
            if any(term and term in q for term in terms):
                hits.append(type_name)
        return _unique(hits)

    def route_candidates(
        self,
        *,
        question: str,
        subject_type: str = "",
        target_types: Optional[Sequence[str]] = None,
    ) -> List[RouteSpec]:
        return list_candidate_routes(
            self.schema(),
            question=question,
            subject_type=subject_type,
            target_types=target_types or self.infer_target_types(question),
        )


def list_candidate_routes(
    schema: KGQASchema,
    *,
    question: str,
    subject_type: str = "",
    target_types: Optional[Sequence[str]] = None,
) -> List[RouteSpec]:
    """Return schema-compatible routes ranked by simple type and alias signals."""

    q = _clean(question)
    stype = _clean(subject_type)
    target_set = set(_unique(target_types or []))
    scored = []

    for route in schema.routes.values():
        score = 0
        if stype and route.subject_type == stype:
            score += 1000
        elif stype:
            continue

        if target_set and route.target_type in target_set:
            score += 200
        elif target_set:
            continue

        if any(alias and alias in q for alias in route.intent_aliases):
            score += 50

        score -= int(route.priority)
        scored.append((score, route.qtype, route))

    scored.sort(reverse=True)
    return [route for _, _, route in scored]


def _node(alias: str, schema: KGQASchema, entity_type: str) -> str:
    label = schema.label(entity_type)
    return f"({alias}:`{label}`)"


def build_match_cypher(
    schema: KGQASchema,
    route: RouteSpec,
    *,
    subject_param: str = "subject",
    limit: int = 100,
) -> str:
    """Build a parameterized Cypher skeleton for a typed route.

    The generated query is intentionally conservative. It matches the route path,
    filters the first node by name, and returns distinct target names.
    """

    from .validation import assert_valid_route

    assert_valid_route(schema, route)
    if not route.path:
        raise ValueError("route.path must not be empty")

    aliases = ["n0"]
    first = route.path[0]
    pattern = _node("n0", schema, first.src_type)

    for idx, step in enumerate(route.path, start=1):
        dst_alias = f"n{idx}"
        aliases.append(dst_alias)
        rel = f"`{step.relation}`"
        dst_node = _node(dst_alias, schema, step.dst_type)
        if step.direction == "in":
            pattern += f"<-[:{rel}]-{dst_node}"
        else:
            pattern += f"-[:{rel}]->{dst_node}"

    target_alias = aliases[-1]
    match_clause = "MATCH p=" + pattern
    where_parts = [f"coalesce(n0.name, '') CONTAINS ${subject_param}"]
    for step_number in sorted(set(route.path_constraints.exclude_start_at_steps)):
        where_parts.append(f"n{step_number} <> n0")
    if not route.path_constraints.allow_start_as_answer:
        where_parts.append(f"{target_alias} <> n0")
    return "\n".join(
        [
            match_clause,
            "WHERE " + "\n  AND ".join(where_parts),
            f"RETURN DISTINCT coalesce({target_alias}.name, {target_alias}.id, '') AS answer",
            f"LIMIT {int(limit)}",
        ]
    )
