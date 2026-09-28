# -*- coding: utf-8 -*-
"""Domain-independent schema and typed-route validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .core import KGQASchema, RouteSpec


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    route: str = ""


class SchemaValidationError(ValueError):
    """Raised when an adapter supplies an invalid KGQA schema."""


def validate_route(schema: KGQASchema, route: RouteSpec) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    qtype = str(route.qtype or "")

    if route.subject_type not in schema.entity_types:
        issues.append(ValidationIssue("unknown_route_subject_type", route.subject_type, qtype))
    if route.target_type not in schema.entity_types:
        issues.append(ValidationIssue("unknown_route_target_type", route.target_type, qtype))
    if not route.path:
        issues.append(ValidationIssue("empty_route_path", "route.path must not be empty", qtype))
        return issues

    if route.path[0].src_type != route.subject_type:
        issues.append(
            ValidationIssue(
                "route_start_type_mismatch",
                f"{route.path[0].src_type} != {route.subject_type}",
                qtype,
            )
        )
    if route.path[-1].dst_type != route.target_type:
        issues.append(
            ValidationIssue(
                "route_target_type_mismatch",
                f"{route.path[-1].dst_type} != {route.target_type}",
                qtype,
            )
        )

    for step_number in route.path_constraints.exclude_start_at_steps:
        if not isinstance(step_number, int) or isinstance(step_number, bool):
            issues.append(
                ValidationIssue(
                    "invalid_constraint_step_type",
                    f"exclude_start_at_steps contains {step_number!r}",
                    qtype,
                )
            )
        elif step_number < 1 or step_number > len(route.path):
            issues.append(
                ValidationIssue(
                    "constraint_step_out_of_range",
                    f"exclude_start_at_steps contains {step_number}; path length={len(route.path)}",
                    qtype,
                )
            )

    if not isinstance(route.path_constraints.allow_start_as_answer, bool):
        issues.append(
            ValidationIssue(
                "invalid_allow_start_as_answer",
                repr(route.path_constraints.allow_start_as_answer),
                qtype,
            )
        )

    previous_dst = ""
    for index, step in enumerate(route.path):
        if step.direction not in {"out", "in"}:
            issues.append(
                ValidationIssue(
                    "invalid_path_direction",
                    f"step {index}: {step.direction}",
                    qtype,
                )
            )

        if previous_dst and step.src_type != previous_dst:
            issues.append(
                ValidationIssue(
                    "discontinuous_path_types",
                    f"step {index}: {previous_dst} -> {step.src_type}",
                    qtype,
                )
            )
        previous_dst = step.dst_type

        relation = schema.relations.get(step.relation)
        if relation is None:
            issues.append(
                ValidationIssue(
                    "unknown_path_relation",
                    f"step {index}: {step.relation}",
                    qtype,
                )
            )
            continue

        if step.direction == "in":
            expected_src, expected_dst = relation.dst_type, relation.src_type
        else:
            expected_src, expected_dst = relation.src_type, relation.dst_type
        if step.src_type != expected_src or step.dst_type != expected_dst:
            issues.append(
                ValidationIssue(
                    "relation_type_mismatch",
                    (
                        f"step {index}: {step.src_type}-[{step.relation}/{step.direction}]->"
                        f"{step.dst_type}; expected {expected_src}->{expected_dst}"
                    ),
                    qtype,
                )
            )

    return issues


def validate_schema(schema: KGQASchema) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []

    if schema.entity_linking_policy not in {"exact_typed", "fuzzy_typed"}:
        issues.append(
            ValidationIssue(
                "invalid_entity_linking_policy",
                str(schema.entity_linking_policy),
            )
        )

    for key, spec in schema.entity_types.items():
        if key != spec.name:
            issues.append(
                ValidationIssue(
                    "entity_type_key_mismatch",
                    f"{key} != {spec.name}",
                )
            )

    for key, relation in schema.relations.items():
        if key != relation.name:
            issues.append(
                ValidationIssue(
                    "relation_key_mismatch",
                    f"{key} != {relation.name}",
                )
            )
        if relation.src_type not in schema.entity_types:
            issues.append(
                ValidationIssue(
                    "unknown_relation_source_type",
                    f"{key}: {relation.src_type}",
                )
            )
        if relation.dst_type not in schema.entity_types:
            issues.append(
                ValidationIssue(
                    "unknown_relation_destination_type",
                    f"{key}: {relation.dst_type}",
                )
            )

    for key, route in schema.routes.items():
        if key != route.qtype:
            issues.append(
                ValidationIssue(
                    "route_key_mismatch",
                    f"{key} != {route.qtype}",
                    route.qtype,
                )
            )
        issues.extend(validate_route(schema, route))

    return issues


def assert_valid_schema(schema: KGQASchema) -> None:
    issues = validate_schema(schema)
    if issues:
        summary = "; ".join(
            f"{issue.code}[{issue.route or '-'}]: {issue.message}" for issue in issues
        )
        raise SchemaValidationError(summary)


def assert_valid_route(schema: KGQASchema, route: RouteSpec) -> None:
    issues = validate_route(schema, route)
    if issues:
        summary = "; ".join(
            f"{issue.code}[{issue.route or '-'}]: {issue.message}" for issue in issues
        )
        raise SchemaValidationError(summary)
