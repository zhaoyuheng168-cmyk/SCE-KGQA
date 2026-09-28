# -*- coding: utf-8 -*-
"""Cross-domain acceptance tests for the shared KGQA core."""

from __future__ import annotations

import unittest
from pathlib import Path

from tools.generic_kgqa_framework.adapters import GansuFinanceAdapter, MetaQAAdapter, MetaQARealAdapter
from tools.generic_kgqa_framework.core import (
    DomainAdapter,
    EntityTypeSpec,
    KGQASchema,
    PathConstraints,
    PathStep,
    RelationSpec,
    RouteSpec,
    build_match_cypher,
)
from tools.generic_kgqa_framework.datasets import Triple
from tools.generic_kgqa_framework.graph import InMemoryKG
from tools.generic_kgqa_framework.validation import SchemaValidationError, assert_valid_schema


class LibraryAdapter(DomainAdapter):
    """Third-domain fixture that must run without changing the shared core."""

    name = "library"

    def schema(self) -> KGQASchema:
        return KGQASchema(
            namespace=self.name,
            entity_types={
                "Book": EntityTypeSpec("Book", ("book",)),
                "Author": EntityTypeSpec("Author", ("author",)),
            },
            relations={
                "written_by": RelationSpec("written_by", "Book", "Author", ("written by",)),
            },
            routes={
                "book_author": RouteSpec(
                    qtype="book_author",
                    family="singlehop",
                    subject_type="Book",
                    target_type="Author",
                    path=[PathStep("Book", "written_by", "Author")],
                    answer_template="{subject}: {answers}",
                    intent_aliases=("author", "written"),
                ),
            },
        )


class FrameworkBoundaryTest(unittest.TestCase):
    def test_registered_domain_schemas_are_valid(self):
        assert_valid_schema(GansuFinanceAdapter().schema())
        assert_valid_schema(MetaQAAdapter().schema())
        assert_valid_schema(MetaQARealAdapter().schema())

    def test_real_metaqa_adapter_has_complete_generated_routes(self):
        schema = MetaQARealAdapter().schema()
        self.assertEqual(49, len(schema.routes))
        self.assertEqual(9, len(schema.relations))
        constrained = {
            qtype: tuple(route.path_constraints.exclude_start_at_steps)
            for qtype, route in schema.routes.items()
            if route.path_constraints.exclude_start_at_steps
        }
        self.assertEqual(15, len(constrained))
        self.assertTrue(all(steps == (2,) for steps in constrained.values()))
        allow_start_as_answer = {
            qtype
            for qtype, route in schema.routes.items()
            if route.path_constraints.allow_start_as_answer
        }
        self.assertEqual(13, len(allow_start_as_answer))
        self.assertTrue(
            all(schema.routes[qtype].metadata["hop"] == 1 for qtype in allow_start_as_answer)
        )

    def test_third_domain_runs_without_core_changes(self):
        adapter = LibraryAdapter()
        schema = adapter.schema()
        graph = InMemoryKG(
            [
                Triple("The Left Hand of Darkness", "written_by", "Ursula K. Le Guin"),
                Triple("A Wizard of Earthsea", "written_by", "Ursula K. Le Guin"),
            ],
            schema,
        )
        routes = adapter.route_candidates(
            question="Who is the author of The Left Hand of Darkness?",
            subject_type="Book",
        )
        result = graph.execute_route(routes[0], subject="The Left Hand of Darkness")
        self.assertEqual(["Ursula K. Le Guin"], result.answers)

    def test_invalid_relation_direction_is_rejected(self):
        schema = LibraryAdapter().schema()
        invalid_route = RouteSpec(
            qtype="invalid",
            family="singlehop",
            subject_type="Author",
            target_type="Book",
            path=[PathStep("Author", "written_by", "Book", direction="out")],
            answer_template="{answers}",
        )
        with self.assertRaises(SchemaValidationError):
            build_match_cypher(schema, invalid_route)

    def test_start_revisit_constraint_is_domain_independent(self):
        schema = KGQASchema(
            namespace="library_cycle",
            entity_types={
                "Book": EntityTypeSpec("Book"),
                "Author": EntityTypeSpec("Author"),
                "Genre": EntityTypeSpec("Genre"),
            },
            relations={
                "written_by": RelationSpec("written_by", "Book", "Author"),
                "has_genre": RelationSpec("has_genre", "Book", "Genre"),
            },
            routes={},
        )
        graph = InMemoryKG(
            [
                Triple("Start Book", "written_by", "Shared Author"),
                Triple("Other Book", "written_by", "Shared Author"),
                Triple("Start Book", "has_genre", "Start Genre"),
                Triple("Other Book", "has_genre", "Other Genre"),
            ],
            schema,
        )
        unconstrained = RouteSpec(
            qtype="shared_author_genres_unconstrained",
            family="threehop",
            subject_type="Book",
            target_type="Genre",
            path=[
                PathStep("Book", "written_by", "Author"),
                PathStep("Author", "written_by", "Book", direction="in"),
                PathStep("Book", "has_genre", "Genre"),
            ],
            answer_template="{answers}",
        )
        constrained = RouteSpec(
            qtype="shared_author_genres_constrained",
            family="threehop",
            subject_type="Book",
            target_type="Genre",
            path=unconstrained.path,
            answer_template="{answers}",
            path_constraints=PathConstraints(exclude_start_at_steps=(2,)),
        )

        without_constraint = graph.execute_route(unconstrained, subject="Start Book")
        with_constraint = graph.execute_route(constrained, subject="Start Book")

        self.assertEqual({"Start Genre", "Other Genre"}, set(without_constraint.answers))
        self.assertEqual(["Other Genre"], with_constraint.answers)
        self.assertEqual([0, 1, 0], with_constraint.excluded_start_revisit_counts)
        self.assertIn("n2 <> n0", build_match_cypher(schema, constrained))

    def test_invalid_constraint_step_is_rejected(self):
        schema = LibraryAdapter().schema()
        invalid_route = RouteSpec(
            qtype="invalid_constraint",
            family="singlehop",
            subject_type="Book",
            target_type="Author",
            path=[PathStep("Book", "written_by", "Author")],
            answer_template="{answers}",
            path_constraints=PathConstraints(exclude_start_at_steps=(2,)),
        )
        with self.assertRaises(SchemaValidationError):
            build_match_cypher(schema, invalid_route)

    def test_start_entity_answer_policy_is_route_configurable(self):
        schema = KGQASchema(
            namespace="self_answer_library",
            entity_types={
                "Book": EntityTypeSpec("Book"),
                "Author": EntityTypeSpec("Author"),
            },
            relations={
                "written_by": RelationSpec("written_by", "Book", "Author"),
            },
            routes={},
        )
        graph = InMemoryKG([Triple("Memoir", "written_by", "Memoir")], schema)
        excluded = RouteSpec(
            qtype="excluded",
            family="singlehop",
            subject_type="Book",
            target_type="Author",
            path=[PathStep("Book", "written_by", "Author")],
            answer_template="{answers}",
        )
        allowed = RouteSpec(
            qtype="allowed",
            family="singlehop",
            subject_type="Book",
            target_type="Author",
            path=excluded.path,
            answer_template="{answers}",
            path_constraints=PathConstraints(allow_start_as_answer=True),
        )

        self.assertEqual([], graph.execute_route(excluded, subject="Memoir").answers)
        self.assertEqual(["Memoir"], graph.execute_route(allowed, subject="Memoir").answers)
        self.assertIn("n1 <> n0", build_match_cypher(schema, excluded))
        self.assertNotIn("n1 <> n0", build_match_cypher(schema, allowed))

    def test_invalid_start_entity_answer_policy_is_rejected(self):
        schema = LibraryAdapter().schema()
        invalid_route = RouteSpec(
            qtype="invalid_self_answer_policy",
            family="singlehop",
            subject_type="Book",
            target_type="Author",
            path=[PathStep("Book", "written_by", "Author")],
            answer_template="{answers}",
            path_constraints=PathConstraints(allow_start_as_answer="yes"),
        )
        with self.assertRaises(SchemaValidationError):
            build_match_cypher(schema, invalid_route)

    def test_entity_linking_policy_is_domain_configurable(self):
        entity_types = {
            "Book": EntityTypeSpec("Book"),
            "Author": EntityTypeSpec("Author"),
        }
        relations = {
            "written_by": RelationSpec("written_by", "Book", "Author"),
        }
        route = RouteSpec(
            qtype="book_author",
            family="singlehop",
            subject_type="Book",
            target_type="Author",
            path=[PathStep("Book", "written_by", "Author")],
            answer_template="{answers}",
        )
        triples = [
            Triple("She", "written_by", "Exact Author"),
            Triple("Shelter", "written_by", "Fuzzy Author"),
        ]
        exact_graph = InMemoryKG(
            triples,
            KGQASchema(
                namespace="exact_library",
                entity_types=entity_types,
                relations=relations,
                routes={"book_author": route},
                entity_linking_policy="exact_typed",
            ),
        )
        fuzzy_graph = InMemoryKG(
            triples,
            KGQASchema(
                namespace="fuzzy_library",
                entity_types=entity_types,
                relations=relations,
                routes={"book_author": route},
                entity_linking_policy="fuzzy_typed",
            ),
        )

        self.assertEqual(["Exact Author"], exact_graph.execute_route(route, subject="She").answers)
        self.assertEqual(
            {"Exact Author", "Fuzzy Author"},
            set(fuzzy_graph.execute_route(route, subject="She").answers),
        )

    def test_invalid_entity_linking_policy_is_rejected(self):
        schema = LibraryAdapter().schema()
        invalid_schema = KGQASchema(
            namespace=schema.namespace,
            entity_types=schema.entity_types,
            relations=schema.relations,
            routes=schema.routes,
            entity_linking_policy="unknown_policy",
        )
        with self.assertRaises(SchemaValidationError):
            InMemoryKG([], invalid_schema)

    def test_shared_core_has_no_known_domain_labels(self):
        package = Path(__file__).resolve().parents[1]
        shared_files = [
            package / "core.py",
            package / "graph.py",
            package / "validation.py",
        ]
        forbidden = {
            "FinancialInstitution",
            "FinancialProduct",
            "Policy",
            "Enterprise",
            "Movie",
            "Person",
            "has_actor",
            "providesProduct",
        }
        for source in shared_files:
            text = source.read_text(encoding="utf-8")
            for token in forbidden:
                self.assertNotIn(token, text, f"{token} leaked into {source.name}")


if __name__ == "__main__":
    unittest.main()
