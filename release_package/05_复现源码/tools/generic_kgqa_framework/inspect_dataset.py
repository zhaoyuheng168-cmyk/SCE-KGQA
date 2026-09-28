# -*- coding: utf-8 -*-
"""Inspect triple relation coverage before integrating a public KGQA dataset."""

from __future__ import annotations

import argparse
from collections import Counter

from .adapters import adapter_names, get_adapter
from .datasets import load_triples
from .validation import assert_valid_schema


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter", choices=adapter_names(), required=True)
    parser.add_argument("--triples", required=True)
    parser.add_argument("--top", type=int, default=50)
    args = parser.parse_args()

    adapter = get_adapter(args.adapter)
    schema = adapter.schema()
    assert_valid_schema(schema)
    triples = load_triples(args.triples)
    counts = Counter(triple.relation for triple in triples)
    registered = set(schema.relations)
    observed = set(counts)
    unknown = sorted(observed - registered)
    unused = sorted(registered - observed)

    print(f"adapter={adapter.name}")
    print(f"triples={len(triples)}")
    print(f"observed_relations={len(observed)}")
    print(f"registered_relations={len(registered)}")
    print(f"unknown_relations={len(unknown)}")
    print(f"unused_registered_relations={len(unused)}")
    print("relation_counts:")
    for relation, count in counts.most_common(max(int(args.top), 0)):
        marker = "registered" if relation in registered else "UNKNOWN"
        print(f"{relation}\t{count}\t{marker}")
    if unknown:
        print("unknown_relation_names=" + "||".join(unknown))
    if unused:
        print("unused_registered_relation_names=" + "||".join(unused))
    return 2 if unknown else 0


if __name__ == "__main__":
    raise SystemExit(main())

