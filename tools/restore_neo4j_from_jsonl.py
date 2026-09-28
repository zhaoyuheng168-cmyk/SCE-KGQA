#!/usr/bin/env python3
"""Restore the SCE-KGQA Neo4j graph from bundled JSONL exports.

This script is intended for public reproduction. It imports the graph exported
under ``release_package/04_数据与知识资源/runtime_data/neo4j_export`` and keeps
Neo4j labels exactly as stored in ``nodes.jsonl``. In particular, labels such as
``GansuTechFinanceDevV1Enhance.FinancialInstitution`` and ``Entity`` are created
as separate labels, which is required by the SCE-KGQA routing/type-gate logic.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXPORT_DIR = (
    ROOT
    / "release_package"
    / "04_数据与知识资源"
    / "runtime_data"
    / "neo4j_export"
)


def read_jsonl(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def quote_label(label: str) -> str:
    return "`" + str(label).replace("`", "``") + "`"


def label_expression(labels: Iterable[str]) -> str:
    labels = list(labels)
    if not labels:
        return quote_label("Entity")
    return ":".join(quote_label(label) for label in labels)


def validate_rel_type(rel_type: str) -> str:
    rel_type = str(rel_type)
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", rel_type):
        raise ValueError(f"Unsupported relationship type: {rel_type!r}")
    return rel_type


def chunked(rows: list[dict], size: int) -> Iterable[list[dict]]:
    for idx in range(0, len(rows), size):
        yield rows[idx : idx + size]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--export-dir", type=Path, default=DEFAULT_EXPORT_DIR)
    parser.add_argument("--uri", default=os.getenv("GTF_NEO4J_URI", "bolt://127.0.0.1:7688"))
    parser.add_argument("--user", default=os.getenv("GTF_NEO4J_USER", "neo4j"))
    parser.add_argument(
        "--password",
        default=os.getenv("GTF_NEO4J_PASSWORD", "CHANGE_ME"),
        help="Neo4j password. Defaults to GTF_NEO4J_PASSWORD or CHANGE_ME.",
    )
    parser.add_argument("--database", default=os.getenv("GTF_NEO4J_DATABASE", "neo4j"))
    parser.add_argument("--clear", action="store_true", help="Delete existing graph before import.")
    parser.add_argument("--batch-size", type=int, default=1000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.batch_size < 1:
        raise SystemExit('--batch-size must be positive')
    nodes_path = args.export_dir / "nodes.jsonl"
    rels_path = args.export_dir / "relationships.jsonl"
    meta_path = args.export_dir / "metadata.json"

    missing = [str(path) for path in [nodes_path, rels_path] if not path.exists()]
    if missing:
        raise SystemExit(f"Missing Neo4j export file(s): {missing}")

    nodes_by_labels: dict[tuple[str, ...], list[dict]] = defaultdict(list)
    for row in read_jsonl(nodes_path):
        labels = tuple(row.get("labels") or ["Entity"])
        props = dict(row.get("props") or {})
        props["__orig_id"] = row["id"]
        nodes_by_labels[labels].append(props)

    rels_by_type: dict[str, list[dict]] = defaultdict(list)
    for row in read_jsonl(rels_path):
        rel_type = validate_rel_type(row["type"])
        rels_by_type[rel_type].append(
            {
                "start_id": row["start_id"],
                "end_id": row["end_id"],
                "props": dict(row.get("props") or {}),
            }
        )

    driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password))
    imported_nodes = 0
    imported_rels = 0

    with driver.session(database=args.database) as session:
        if not args.clear:
            existing = session.run("MATCH (n) RETURN count(n) AS count").single()["count"]
            if existing:
                driver.close()
                raise SystemExit('Database is not empty. Choose a new database, or explicitly use --clear to replace its graph.')
        if args.clear:
            session.run("MATCH (n) DETACH DELETE n").consume()

        for labels, rows in nodes_by_labels.items():
            cypher = f"UNWIND $rows AS row CREATE (n:{label_expression(labels)}) SET n = row"
            for chunk in chunked(rows, args.batch_size):
                session.run(cypher, rows=chunk).consume()
                imported_nodes += len(chunk)

        for rel_type, rows in rels_by_type.items():
            cypher = f"""
            UNWIND $rows AS row
            MATCH (a {{__orig_id: row.start_id}})
            MATCH (b {{__orig_id: row.end_id}})
            CREATE (a)-[r:{rel_type}]->(b)
            SET r = row.props
            RETURN count(r) AS created
            """
            for chunk in chunked(rows, args.batch_size):
                created = session.run(cypher, rows=chunk).single()["created"]
                if created != len(chunk):
                    raise RuntimeError(
                        f"Relationship import mismatch for {rel_type}: "
                        f"expected {len(chunk)}, created {created}"
                    )
                imported_rels += created

        node_count = session.run("MATCH (n) RETURN count(n) AS count").single()["count"]
        rel_count = session.run("MATCH ()-[r]->() RETURN count(r) AS count").single()["count"]

    driver.close()

    result = {
        "export_dir": str(args.export_dir),
        "metadata": str(meta_path) if meta_path.exists() else None,
        "nodes_imported": imported_nodes,
        "relationships_imported": imported_rels,
        "nodes_in_neo4j": node_count,
        "relationships_in_neo4j": rel_count,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
