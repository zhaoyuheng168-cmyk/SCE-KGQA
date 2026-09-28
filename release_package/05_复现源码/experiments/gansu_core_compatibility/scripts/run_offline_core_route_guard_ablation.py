# -*- coding: utf-8 -*-
"""Offline Core route-guard ablation over frozen V8-original compatibility results."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable, List, Sequence

from neo4j import GraphDatabase


WORKSPACE = Path(__file__).resolve().parents[3]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from core_route_guard import decide_guard  # noqa: E402
from tools.generic_kgqa_framework import build_match_cypher  # noqa: E402
from tools.generic_kgqa_framework.adapters import GansuFinanceAdapter  # noqa: E402
from run_gansu_v8_core_compatibility import score_sets, unique  # noqa: E402


ALLOWED_V8_QTYPES = {
    "institution_products": ("freeqa_institution_product_overview", "generic_relation_objects"),
    "product_provider": ("product_provider",),
    "policy_products": ("policy_supports_product",),
    "policy_region_overview": ("multi_hop_policy_to_region_overview_3hop",),
}


def load_jsonl(path: Path) -> List[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def mean(rows: Sequence[dict], field: str) -> float:
    return sum(float(row[field]) for row in rows) / len(rows) if rows else 0.0


class ReadOnlyGraph:
    def __init__(self):
        self.schema = GansuFinanceAdapter().schema()
        self.driver = GraphDatabase.driver(
            os.environ["GTF_NEO4J_URI"],
            auth=(os.environ["GTF_NEO4J_USER"], os.environ["GTF_NEO4J_PASSWORD"]),
        )
        self.database = os.environ["GTF_NEO4J_DATABASE"]

    def close(self) -> None:
        self.driver.close()

    def node_types(self, names: Iterable[str]) -> dict:
        selected = unique(names)
        if not selected:
            return {}
        cypher = """
MATCH (n)
WHERE coalesce(n.name, '') IN $names
RETURN n.name AS name,
       collect(DISTINCT replace(head(labels(n)), 'GansuTechFinanceDevV1Enhance.', '')) AS types
""".strip()
        with self.driver.session(database=self.database) as session:
            rows = list(session.run(cypher, {"names": selected}))
        return {str(row["name"]): unique(row["types"]) for row in rows}

    def execute_route(self, route_name: str, subject: str) -> List[str]:
        route = self.schema.routes[route_name]
        cypher = build_match_cypher(self.schema, route, limit=500)
        with self.driver.session(database=self.database) as session:
            rows = list(session.run(cypher, {"subject": subject}))
        return unique(row.get("answer") for row in rows)


def summarize(rows: Sequence[dict]) -> dict:
    groups = defaultdict(list)
    for row in rows:
        groups[row["core_route"]].append(row)

    def metrics(items: Sequence[dict]) -> dict:
        return {
            "count": len(items),
            "original_exact": mean(items, "original_exact"),
            "guarded_exact": mean(items, "guarded_exact"),
            "original_f1": mean(items, "original_f1"),
            "guarded_f1": mean(items, "guarded_f1"),
            "guard_trigger_rate": mean(items, "guard_triggered"),
            "corrected_error_rate": mean(items, "corrected_error"),
            "introduced_error_rate": mean(items, "introduced_error"),
            "guard_route_selection_accuracy": mean(items, "guard_route_selection_correct"),
        }

    return {
        "protocol": "gansu_offline_core_route_guard_ablation_v1",
        "guard_inputs": ["question", "V8 subject", "V8 qtype", "V8 answers", "shared Core schema", "read-only node types"],
        "guard_does_not_use": ["frozen expected route during decision", "gold answer during decision", "production V8 source modification"],
        "overall": metrics(rows),
        "by_route": {name: metrics(items) for name, items in sorted(groups.items())},
    }


def write_outputs(out_dir: Path, rows: Sequence[dict], summary: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "results.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    fields = [
        "qid", "core_route", "v8_qtype", "guard_action", "guard_reason",
        "guard_selected_route", "guard_target_type", "guard_triggered",
        "guard_route_selection_correct", "original_exact", "guarded_exact",
        "original_f1", "guarded_f1", "corrected_error", "introduced_error",
    ]
    with (out_dir / "metrics.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row[field] for field in fields} for row in rows)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=WORKSPACE / "experiments/gansu_core_compatibility/results/formal_16/results.jsonl",
    )
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    required = ["GTF_NEO4J_URI", "GTF_NEO4J_USER", "GTF_NEO4J_PASSWORD", "GTF_NEO4J_DATABASE"]
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise SystemExit(f"Missing runtime environment variables: {', '.join(missing)}")

    source_rows = load_jsonl(args.input)
    graph = ReadOnlyGraph()
    rows = []
    try:
        for index, source in enumerate(source_rows, start=1):
            names = [source["subject"], *source["v8_answers"]]
            type_map = graph.node_types(names)
            decision = decide_guard(
                graph.schema,
                question=source["question"],
                subject_types=type_map.get(source["subject"], ()),
                v8_qtype=source["v8_qtype"],
                v8_answers=source["v8_answers"],
                answer_types=type_map,
                allowed_v8_qtypes=ALLOWED_V8_QTYPES,
            )
            guarded_answers = list(source["v8_answers"])
            if decision.action == "replace_with_core":
                guarded_answers = graph.execute_route(decision.selected_route, source["subject"])

            original = score_sets(source["v8_answers"], source["core_answers"])
            guarded = score_sets(guarded_answers, source["core_answers"])
            row = {
                **source,
                "guard_action": decision.action,
                "guard_reason": decision.reason,
                "guard_selected_route": decision.selected_route,
                "guard_subject_type": decision.subject_type,
                "guard_target_type": decision.target_type,
                "guarded_answers": guarded_answers,
                "guarded_answer_count": len(guarded_answers),
                "guard_triggered": float(decision.action == "replace_with_core"),
                "guard_route_selection_correct": float(decision.selected_route == source["core_route"]),
                "original_exact": original["exact"],
                "guarded_exact": guarded["exact"],
                "original_f1": original["f1"],
                "guarded_f1": guarded["f1"],
                "corrected_error": float(original["exact"] == 0.0 and guarded["exact"] == 1.0),
                "introduced_error": float(original["exact"] == 1.0 and guarded["exact"] == 0.0),
            }
            rows.append(row)
            print(
                f"[{index:02d}/{len(source_rows):02d}] {source['qid']} "
                f"guard={decision.action} route={decision.selected_route or '-'} "
                f"exact={original['exact']:.0f}->{guarded['exact']:.0f}"
            )
    finally:
        graph.close()

    summary = summarize(rows)
    write_outputs(args.out_dir, rows, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

