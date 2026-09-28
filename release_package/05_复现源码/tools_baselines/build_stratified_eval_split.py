#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a deterministic stratified evaluation split for baseline staging."""

from __future__ import annotations

import argparse
import csv
import random
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def allocate(groups: dict[str, list[dict[str, str]]], total: int) -> dict[str, int]:
    n_all = sum(len(rows) for rows in groups.values())
    raw = {key: len(rows) * total / max(1, n_all) for key, rows in groups.items()}
    counts = {key: min(len(groups[key]), int(value)) for key, value in raw.items()}

    for key in groups:
        if counts[key] == 0 and groups[key] and sum(counts.values()) < total:
            counts[key] = 1

    while sum(counts.values()) < total:
        candidates = [
            key for key in groups
            if counts[key] < len(groups[key])
        ]
        if not candidates:
            break
        candidates.sort(key=lambda key: (raw[key] - counts[key], len(groups[key])), reverse=True)
        counts[candidates[0]] += 1

    while sum(counts.values()) > total:
        candidates = [key for key, value in counts.items() if value > 0]
        candidates.sort(key=lambda key: (counts[key] - raw[key], counts[key]), reverse=True)
        counts[candidates[0]] -= 1

    return counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        type=Path,
        default=ROOT / "experiments/baselines/datasets/gtf_kgqa_1300_formal_expanded_gold.csv",
    )
    parser.add_argument("--exclude", type=Path, default=ROOT / "experiments/baselines/datasets/dev_120.csv")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "experiments/baselines/datasets/gtf_kgqa_300_stratified_seed20260605.csv",
    )
    parser.add_argument("--size", type=int, default=300)
    parser.add_argument("--seed", type=int, default=20260605)
    parser.add_argument("--stratify-by", default="category")
    args = parser.parse_args()

    source_rows = read_rows(args.source)
    fieldnames = list(source_rows[0].keys()) if source_rows else []
    excluded_ids = {row.get("question_id", "") for row in read_rows(args.exclude)} if args.exclude.exists() else set()
    eligible = [row for row in source_rows if row.get("question_id", "") not in excluded_ids]

    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in eligible:
        key = row.get(args.stratify_by, "") or "<EMPTY>"
        groups[key].append(row)

    rng = random.Random(args.seed)
    for rows in groups.values():
        rows.sort(key=lambda row: row.get("question_id", ""))
        rng.shuffle(rows)

    counts = allocate(groups, args.size)
    selected: list[dict[str, str]] = []
    for key in sorted(groups):
        selected.extend(groups[key][: counts.get(key, 0)])
    selected.sort(key=lambda row: (row.get(args.stratify_by, ""), row.get("question_id", "")))

    write_rows(args.output, fieldnames, selected)

    print(f"source={args.source}")
    print(f"exclude={args.exclude} excluded={len(excluded_ids)}")
    print(f"eligible={len(eligible)} selected={len(selected)} output={args.output}")
    for key in sorted(counts):
        print(f"{key}\t{counts[key]}")


if __name__ == "__main__":
    main()
