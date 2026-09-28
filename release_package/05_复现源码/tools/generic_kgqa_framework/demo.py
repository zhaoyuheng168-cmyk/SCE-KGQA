# -*- coding: utf-8 -*-
"""Small CLI demo for the domain-adaptive KGQA framework prototype."""

from __future__ import annotations

import argparse

from .adapters import adapter_names, get_adapter
from .core import build_match_cypher


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter", choices=adapter_names(), default="gansu_finance")
    parser.add_argument("--question", required=True)
    parser.add_argument("--subject-type", default="")
    args = parser.parse_args()

    adapter = get_adapter(args.adapter)
    schema = adapter.schema()
    routes = adapter.route_candidates(question=args.question, subject_type=args.subject_type)

    print(f"adapter={adapter.name}")
    print(f"routes={len(routes)}")
    for route in routes[:5]:
        print(f"- {route.qtype} family={route.family} {route.subject_type}->{route.target_type}")
        print(build_match_cypher(schema, route))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
