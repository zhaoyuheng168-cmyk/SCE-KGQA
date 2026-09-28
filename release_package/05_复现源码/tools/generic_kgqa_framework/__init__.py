# -*- coding: utf-8 -*-
"""Domain-adaptive KGQA framework prototype.

The package is intentionally side-effect free: importing it does not connect to
Neo4j, load local runtime data, or mutate the existing Gansu finance KGQA app.
"""

from .core import (
    DomainAdapter,
    EntityTypeSpec,
    KGQASchema,
    PathConstraints,
    PathStep,
    RelationSpec,
    RouteSpec,
    build_match_cypher,
    list_candidate_routes,
)
from .datasets import Triple, load_triples, parse_triple_line
from .graph import ExecutionResult, InMemoryKG
from .validation import (
    SchemaValidationError,
    ValidationIssue,
    assert_valid_route,
    assert_valid_schema,
    validate_route,
    validate_schema,
)

__all__ = [
    "DomainAdapter",
    "EntityTypeSpec",
    "KGQASchema",
    "PathConstraints",
    "PathStep",
    "RelationSpec",
    "RouteSpec",
    "build_match_cypher",
    "list_candidate_routes",
    "Triple",
    "load_triples",
    "parse_triple_line",
    "ExecutionResult",
    "InMemoryKG",
    "SchemaValidationError",
    "ValidationIssue",
    "assert_valid_route",
    "assert_valid_schema",
    "validate_route",
    "validate_schema",
]
