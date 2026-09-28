# -*- coding: utf-8 -*-
"""CLI wrapper for entity embedding grounding.

This module only returns candidate entities. It must not generate final
answers and must not rewrite V8 subjects by itself.
"""

from __future__ import annotations

import argparse
import json

from embedding_config import get_embedding_config
from embedding_assist_wrapper import retrieve_entity_candidates_with_expansion


def ground_entities(query: str):
    cfg = get_embedding_config()
    return retrieve_entity_candidates_with_expansion(
        query,
        top_k=int(cfg["entity_top_k"]),
        min_score=float(cfg["entity_min_score"]),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    args = parser.parse_args()
    print(json.dumps(ground_entities(args.query), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
