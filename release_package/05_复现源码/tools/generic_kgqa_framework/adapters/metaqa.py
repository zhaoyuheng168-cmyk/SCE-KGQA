# -*- coding: utf-8 -*-
"""MetaQA-style public benchmark adapter example."""

from __future__ import annotations

from typing import Dict

from ..core import DomainAdapter, EntityTypeSpec, KGQASchema, PathStep, RelationSpec, RouteSpec


class MetaQAAdapter(DomainAdapter):
    """A small adapter sketch for MetaQA movie-domain KGQA.

    MetaQA variants differ in relation naming across releases. This adapter keeps
    the route metadata explicit so a loader can map aliases to dataset-specific
    relation labels later.
    """

    name = "metaqa"

    def schema(self) -> KGQASchema:
        entity_types: Dict[str, EntityTypeSpec] = {
            "Movie": EntityTypeSpec("Movie", ("电影", "movie", "film")),
            "Person": EntityTypeSpec("Person", ("演员", "导演", "person", "actor", "director")),
            "Genre": EntityTypeSpec("Genre", ("类型", "genre")),
            "Year": EntityTypeSpec("Year", ("年份", "year")),
        }
        relations: Dict[str, RelationSpec] = {
            "has_actor": RelationSpec("has_actor", "Movie", "Person", ("actor", "acted in")),
            "has_director": RelationSpec("has_director", "Movie", "Person", ("director", "directed by")),
            "has_genre": RelationSpec("has_genre", "Movie", "Genre", ("genre",)),
            "release_year": RelationSpec("release_year", "Movie", "Year", ("release year", "year")),
        }
        routes: Dict[str, RouteSpec] = {
            "movie_actors": RouteSpec(
                qtype="movie_actors",
                family="singlehop",
                subject_type="Movie",
                target_type="Person",
                path=[PathStep("Movie", "has_actor", "Person")],
                intent_aliases=("actors", "cast", "演员"),
                answer_template="The actors of {subject} include: {answers}.",
                priority=10,
            ),
            "movie_director": RouteSpec(
                qtype="movie_director",
                family="singlehop",
                subject_type="Movie",
                target_type="Person",
                path=[PathStep("Movie", "has_director", "Person")],
                intent_aliases=("director", "directed", "导演"),
                answer_template="The director of {subject} is: {answers}.",
                priority=20,
            ),
            "actor_coactors": RouteSpec(
                qtype="actor_coactors",
                family="twohop",
                subject_type="Person",
                target_type="Person",
                path=[
                    PathStep("Person", "has_actor", "Movie", direction="in"),
                    PathStep("Movie", "has_actor", "Person"),
                ],
                intent_aliases=("co-star", "coactor", "acted with", "合作演员"),
                answer_template="People who acted with {subject} include: {answers}.",
                priority=100,
            ),
            "movie_genre_directors": RouteSpec(
                qtype="movie_genre_directors",
                family="twohop",
                subject_type="Genre",
                target_type="Person",
                path=[
                    PathStep("Genre", "has_genre", "Movie", direction="in"),
                    PathStep("Movie", "has_director", "Person"),
                ],
                intent_aliases=("directors of genre", "genre directors", "类型导演"),
                answer_template="Directors for {subject} movies include: {answers}.",
                priority=120,
            ),
        }
        return KGQASchema(
            namespace=self.name,
            entity_types=entity_types,
            relations=relations,
            routes=routes,
        )

