#!/usr/bin/env python3
"""Shared real-MetaQA schema mapping for bounded audit and smoke scripts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class RelationBinding:
    relation: str
    source_role: str
    target_role: str


ROLE_BINDINGS: Dict[str, RelationBinding] = {
    "actor": RelationBinding("starred_actors", "movie", "actor"),
    "director": RelationBinding("directed_by", "movie", "director"),
    "writer": RelationBinding("written_by", "movie", "writer"),
    "genre": RelationBinding("has_genre", "movie", "genre"),
    "year": RelationBinding("release_year", "movie", "year"),
    "language": RelationBinding("in_language", "movie", "language"),
    "tags": RelationBinding("has_tags", "movie", "tags"),
    "tag": RelationBinding("has_tags", "movie", "tag"),
    "imdbrating": RelationBinding("has_imdb_rating", "movie", "imdbrating"),
    "imdbvotes": RelationBinding("has_imdb_votes", "movie", "imdbvotes"),
}


def parse_qtype_path(qtype: str) -> List[dict]:
    """Convert a qtype such as actor_to_movie_to_director into typed steps."""

    roles = [part.strip() for part in str(qtype or "").split("_to_") if part.strip()]
    if len(roles) < 2:
        raise ValueError(f"Invalid qtype path: {qtype}")

    steps = []
    for source, target in zip(roles, roles[1:]):
        if source == "movie" and target in ROLE_BINDINGS:
            binding = ROLE_BINDINGS[target]
            steps.append(
                {
                    "source_role": source,
                    "relation": binding.relation,
                    "target_role": target,
                    "direction": "out",
                }
            )
        elif target == "movie" and source in ROLE_BINDINGS:
            binding = ROLE_BINDINGS[source]
            steps.append(
                {
                    "source_role": source,
                    "relation": binding.relation,
                    "target_role": target,
                    "direction": "in",
                }
            )
        else:
            raise ValueError(f"Unsupported adjacent roles in {qtype}: {source} -> {target}")
    return steps

