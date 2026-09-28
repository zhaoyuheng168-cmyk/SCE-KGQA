# -*- coding: utf-8 -*-
"""In-memory typed graph executor for framework smoke tests and small datasets."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import DefaultDict, Dict, Iterable, List, Sequence, Set, Tuple

from .core import KGQASchema, RouteSpec
from .datasets import Triple
from .validation import assert_valid_route, assert_valid_schema


@dataclass(frozen=True)
class ExecutionResult:
    route: str
    subject: str
    answers: List[str]
    evidence_paths: List[List[Triple]]
    step_frontier_sizes: List[int] = field(default_factory=list)
    excluded_start_revisit_counts: List[int] = field(default_factory=list)

    def render_answer(self, template: str) -> str:
        text = "、".join(self.answers) if self.answers else "无结果"
        return template.format(subject=self.subject, answers=text, count=len(self.answers))


class InMemoryKG:
    """Small graph executor driven by RouteSpec paths.

    It is meant for public dataset prototyping and unit-scale verification. Large
    benchmark runs should use a database-backed executor with the same RouteSpec
    interface.
    """

    def __init__(self, triples: Iterable[Triple], schema: KGQASchema):
        assert_valid_schema(schema)
        self.schema = schema
        self.triples = list(triples)
        self.by_subject: DefaultDict[Tuple[str, str], List[Triple]] = defaultdict(list)
        self.by_object: DefaultDict[Tuple[str, str], List[Triple]] = defaultdict(list)
        self.node_types: DefaultDict[str, Set[str]] = defaultdict(set)
        self._subject_cache: Dict[Tuple[str, str, str], Tuple[str, ...]] = {}
        self._build_indexes()

    def _build_indexes(self) -> None:
        relation_specs = self.schema.relations
        for triple in self.triples:
            self.by_subject[(triple.subject, triple.relation)].append(triple)
            self.by_object[(triple.object, triple.relation)].append(triple)
            spec = relation_specs.get(triple.relation)
            if spec is not None:
                self.node_types[triple.subject].add(spec.src_type)
                self.node_types[triple.object].add(spec.dst_type)

    def find_subjects(
        self,
        subject_text: str,
        subject_type: str = "",
        policy: str = "",
    ) -> List[str]:
        text = str(subject_text or "").strip()
        if not text:
            return []

        selected_policy = str(policy or self.schema.entity_linking_policy or "fuzzy_typed")
        cache_key = (text, subject_type, selected_policy)
        cached = self._subject_cache.get(cache_key)
        if cached is not None:
            return list(cached)

        if selected_policy == "exact_typed":
            types = self.node_types.get(text, set())
            candidates = [text] if not subject_type or subject_type in types else []
            self._subject_cache[cache_key] = tuple(candidates)
            return candidates

        candidates = []
        for node, types in self.node_types.items():
            if subject_type and subject_type not in types:
                continue
            if selected_policy == "fuzzy_typed" and (node == text or text in node or node in text):
                candidates.append(node)
        candidates = sorted(candidates, key=lambda item: (item != text, len(item), item))
        self._subject_cache[cache_key] = tuple(candidates)
        return candidates

    def execute_route(
        self,
        route: RouteSpec,
        *,
        subject: str,
        limit: int = 100,
    ) -> ExecutionResult:
        assert_valid_route(self.schema, route)
        starts = self.find_subjects(subject, route.subject_type)
        frontier: List[Tuple[str, List[Triple]]] = [(node, []) for node in starts]
        start_set = set(starts)
        exclude_steps = set(route.path_constraints.exclude_start_at_steps)
        step_frontier_sizes: List[int] = []
        excluded_start_revisit_counts: List[int] = []

        for step_number, step in enumerate(route.path, start=1):
            next_frontier: List[Tuple[str, List[Triple]]] = []
            excluded_revisits = 0
            for node, path in frontier:
                if step.direction == "in":
                    edges = self.by_object.get((node, step.relation), [])
                    for edge in edges:
                        if step_number in exclude_steps and edge.subject in start_set:
                            excluded_revisits += 1
                            continue
                        next_frontier.append((edge.subject, path + [edge]))
                else:
                    edges = self.by_subject.get((node, step.relation), [])
                    for edge in edges:
                        if step_number in exclude_steps and edge.object in start_set:
                            excluded_revisits += 1
                            continue
                        next_frontier.append((edge.object, path + [edge]))
            frontier = next_frontier
            step_frontier_sizes.append(len(frontier))
            excluded_start_revisit_counts.append(excluded_revisits)
            if not frontier:
                break

        answers: List[str] = []
        seen = set()
        evidence_paths: List[List[Triple]] = []
        for node, path in frontier:
            if not route.path_constraints.allow_start_as_answer and node in start_set:
                continue
            if node in seen:
                continue
            seen.add(node)
            answers.append(node)
            evidence_paths.append(path)
            if len(answers) >= int(limit):
                break

        return ExecutionResult(
            route=route.qtype,
            subject=starts[0] if starts else str(subject or ""),
            answers=answers,
            evidence_paths=evidence_paths,
            step_frontier_sizes=step_frontier_sizes,
            excluded_start_revisit_counts=excluded_start_revisit_counts,
        )


def execute_first_route(
    graph: InMemoryKG,
    routes: Sequence[RouteSpec],
    *,
    subject: str,
    limit: int = 100,
) -> ExecutionResult:
    if not routes:
        return ExecutionResult(
            route="",
            subject=subject,
            answers=[],
            evidence_paths=[],
            step_frontier_sizes=[],
            excluded_start_revisit_counts=[],
        )
    return graph.execute_route(routes[0], subject=subject, limit=limit)
