# -*- coding: utf-8 -*-
"""Schema-driven route guard that is independent from the production V8 runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Sequence

from tools.generic_kgqa_framework import KGQASchema, RouteSpec


@dataclass(frozen=True)
class GuardDecision:
    action: str
    selected_route: str
    subject_type: str
    target_type: str
    reason: str


def infer_goal_type(question: str, schema: KGQASchema) -> str:
    """Infer the requested answer type from the rightmost schema verbalization."""

    text = str(question or "")
    scored = []
    for type_name, spec in schema.entity_types.items():
        terms = [type_name, *spec.aliases]
        positions = [text.rfind(term) for term in terms if term and term in text]
        if positions:
            scored.append((max(positions), type_name))
    scored.sort(reverse=True)
    return scored[0][1] if scored else ""


def select_route(
    schema: KGQASchema,
    *,
    subject_types: Sequence[str],
    target_type: str,
) -> Optional[RouteSpec]:
    """Select a unique typed route for a subject-type and target-type pair."""

    subject_set = set(subject_types)
    candidates = [
        route
        for route in schema.routes.values()
        if route.subject_type in subject_set and route.target_type == target_type
    ]
    if len(candidates) != 1:
        return None
    return candidates[0]


def decide_guard(
    schema: KGQASchema,
    *,
    question: str,
    subject_types: Sequence[str],
    v8_qtype: str,
    v8_answers: Sequence[str],
    answer_types: Mapping[str, Sequence[str]],
    allowed_v8_qtypes: Mapping[str, Sequence[str]],
) -> GuardDecision:
    """Decide whether a typed Core path should replace the V8 result."""

    target_type = infer_goal_type(question, schema)
    route = select_route(schema, subject_types=subject_types, target_type=target_type)
    subject_type = route.subject_type if route else ""
    if route is None:
        return GuardDecision("pass", "", subject_type, target_type, "no_unique_core_route")

    allowed = set(allowed_v8_qtypes.get(route.qtype, ()))
    route_compatible = str(v8_qtype or "") in allowed
    answers = [str(item or "").strip() for item in v8_answers if str(item or "").strip()]
    answer_type_compatible = bool(answers) and all(
        target_type in set(answer_types.get(answer, ()))
        for answer in answers
    )

    if route_compatible and answer_type_compatible:
        return GuardDecision("pass", route.qtype, subject_type, target_type, "route_and_answer_type_compatible")
    if answer_type_compatible:
        return GuardDecision("pass", route.qtype, subject_type, target_type, "generic_answer_type_compatible")
    if not answers:
        reason = "empty_answer_for_unique_typed_route"
    else:
        reason = "answer_target_type_conflict"
    return GuardDecision("replace_with_core", route.qtype, subject_type, target_type, reason)

