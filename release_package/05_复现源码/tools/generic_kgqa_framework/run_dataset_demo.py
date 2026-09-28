# -*- coding: utf-8 -*-
"""Run a tiny local public-dataset style KGQA demo."""

from __future__ import annotations

import argparse

from .adapters import adapter_names, get_adapter
from .datasets import load_triples
from .graph import InMemoryKG


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter", choices=adapter_names(), default="metaqa")
    parser.add_argument("--triples", required=True)
    parser.add_argument("--question", required=True)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--subject-type", required=True)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    adapter = get_adapter(args.adapter)
    schema = adapter.schema()
    triples = load_triples(args.triples)
    graph = InMemoryKG(triples, schema)
    routes = adapter.route_candidates(question=args.question, subject_type=args.subject_type)

    print(f"adapter={adapter.name}")
    print(f"triples={len(triples)}")
    print(f"candidate_routes={len(routes)}")
    if not routes:
        print("answer=无可用 route")
        return 1

    route = routes[0]
    result = graph.execute_route(route, subject=args.subject, limit=args.limit)
    print(f"selected_route={route.qtype}")
    print(f"answers={'||'.join(result.answers)}")
    print(result.render_answer(route.answer_template))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
