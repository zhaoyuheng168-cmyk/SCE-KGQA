# -*- coding: utf-8 -*-
"""Adapter for the original MetaQA text benchmark and its real relation names."""

from __future__ import annotations

from typing import Dict, List, Sequence

from ..core import (
    DomainAdapter,
    EntityTypeSpec,
    KGQASchema,
    PathConstraints,
    PathStep,
    RelationSpec,
    RouteSpec,
)


QTYPE_GROUPS = {
    1: (
        "actor_to_movie",
        "director_to_movie",
        "movie_to_actor",
        "movie_to_director",
        "movie_to_genre",
        "movie_to_imdbrating",
        "movie_to_imdbvotes",
        "movie_to_language",
        "movie_to_tags",
        "movie_to_writer",
        "movie_to_year",
        "tag_to_movie",
        "writer_to_movie",
    ),
    2: (
        "actor_to_movie_to_actor",
        "actor_to_movie_to_director",
        "actor_to_movie_to_genre",
        "actor_to_movie_to_language",
        "actor_to_movie_to_writer",
        "actor_to_movie_to_year",
        "director_to_movie_to_actor",
        "director_to_movie_to_director",
        "director_to_movie_to_genre",
        "director_to_movie_to_language",
        "director_to_movie_to_writer",
        "director_to_movie_to_year",
        "movie_to_actor_to_movie",
        "movie_to_director_to_movie",
        "movie_to_writer_to_movie",
        "writer_to_movie_to_actor",
        "writer_to_movie_to_director",
        "writer_to_movie_to_genre",
        "writer_to_movie_to_language",
        "writer_to_movie_to_writer",
        "writer_to_movie_to_year",
    ),
    3: (
        "movie_to_actor_to_movie_to_director",
        "movie_to_actor_to_movie_to_genre",
        "movie_to_actor_to_movie_to_language",
        "movie_to_actor_to_movie_to_writer",
        "movie_to_actor_to_movie_to_year",
        "movie_to_director_to_movie_to_actor",
        "movie_to_director_to_movie_to_genre",
        "movie_to_director_to_movie_to_language",
        "movie_to_director_to_movie_to_writer",
        "movie_to_director_to_movie_to_year",
        "movie_to_writer_to_movie_to_actor",
        "movie_to_writer_to_movie_to_director",
        "movie_to_writer_to_movie_to_genre",
        "movie_to_writer_to_movie_to_language",
        "movie_to_writer_to_movie_to_year",
    ),
}


ROLE_TYPES = {
    "movie": "Movie",
    "actor": "Actor",
    "director": "Director",
    "writer": "Writer",
    "genre": "Genre",
    "year": "Year",
    "language": "Language",
    "tag": "Tag",
    "tags": "Tag",
    "imdbrating": "IMDbRating",
    "imdbvotes": "IMDbVotes",
}


ROLE_RELATIONS = {
    "actor": "starred_actors",
    "director": "directed_by",
    "writer": "written_by",
    "genre": "has_genre",
    "year": "release_year",
    "language": "in_language",
    "tag": "has_tags",
    "tags": "has_tags",
    "imdbrating": "has_imdb_rating",
    "imdbvotes": "has_imdb_votes",
}


def qtype_roles(qtype: str) -> List[str]:
    roles = [part.strip() for part in str(qtype or "").split("_to_") if part.strip()]
    if len(roles) < 2:
        raise ValueError(f"Invalid MetaQA qtype: {qtype}")
    return roles


def path_for_qtype(qtype: str) -> List[PathStep]:
    roles = qtype_roles(qtype)
    steps: List[PathStep] = []
    for source_role, target_role in zip(roles, roles[1:]):
        source_type = ROLE_TYPES[source_role]
        target_type = ROLE_TYPES[target_role]
        if source_role == "movie" and target_role in ROLE_RELATIONS:
            steps.append(PathStep(source_type, ROLE_RELATIONS[target_role], target_type))
        elif target_role == "movie" and source_role in ROLE_RELATIONS:
            steps.append(
                PathStep(source_type, ROLE_RELATIONS[source_role], target_type, direction="in")
            )
        else:
            raise ValueError(f"Unsupported MetaQA role transition: {source_role} -> {target_role}")
    return steps


def constraints_for_qtype(qtype: str) -> PathConstraints:
    roles = qtype_roles(qtype)
    start_role = roles[0]
    intermediate_revisit_steps = tuple(
        step_number
        for step_number, role in enumerate(roles[1:], start=1)
        if role == start_role and step_number < len(roles) - 1
    )
    return PathConstraints(
        exclude_start_at_steps=intermediate_revisit_steps,
        allow_start_as_answer=len(roles) == 2,
    )


def route_for_qtype(qtype: str, hop: int) -> RouteSpec:
    roles = qtype_roles(qtype)
    path = path_for_qtype(qtype)
    if len(path) != hop:
        raise ValueError(f"{qtype} generated {len(path)} steps, expected {hop}")
    return RouteSpec(
        qtype=qtype,
        family=f"{hop}hop",
        subject_type=ROLE_TYPES[roles[0]],
        target_type=ROLE_TYPES[roles[-1]],
        path=path,
        path_constraints=constraints_for_qtype(qtype),
        answer_template="{answers}",
        priority=hop * 100,
        metadata={"dataset": "MetaQA", "hop": hop, "roles": tuple(roles)},
    )


def build_routes() -> Dict[str, RouteSpec]:
    return {
        qtype: route_for_qtype(qtype, hop)
        for hop, qtypes in QTYPE_GROUPS.items()
        for qtype in qtypes
    }


class MetaQARealAdapter(DomainAdapter):
    """Original MetaQA adapter with all 49 official qtype routes."""

    name = "metaqa_real"

    def schema(self) -> KGQASchema:
        entity_types = {
            name: EntityTypeSpec(name)
            for name in sorted(set(ROLE_TYPES.values()))
        }
        relations = {
            "starred_actors": RelationSpec("starred_actors", "Movie", "Actor"),
            "directed_by": RelationSpec("directed_by", "Movie", "Director"),
            "written_by": RelationSpec("written_by", "Movie", "Writer"),
            "has_genre": RelationSpec("has_genre", "Movie", "Genre"),
            "release_year": RelationSpec("release_year", "Movie", "Year"),
            "in_language": RelationSpec("in_language", "Movie", "Language"),
            "has_tags": RelationSpec("has_tags", "Movie", "Tag"),
            "has_imdb_rating": RelationSpec("has_imdb_rating", "Movie", "IMDbRating"),
            "has_imdb_votes": RelationSpec("has_imdb_votes", "Movie", "IMDbVotes"),
        }
        return KGQASchema(
            namespace=self.name,
            entity_types=entity_types,
            relations=relations,
            routes=build_routes(),
            entity_linking_policy="exact_typed",
        )
