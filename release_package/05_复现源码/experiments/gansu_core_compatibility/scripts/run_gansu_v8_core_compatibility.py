# -*- coding: utf-8 -*-
"""Read-only compatibility evaluation between production Gansu V8 and shared Core."""

from __future__ import annotations

import argparse
import csv
import importlib
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

from neo4j import GraphDatabase


WORKSPACE = Path(__file__).resolve().parents[3]
RUNTIME = Path("/root/work/GansuTechFinance_KGQA_RELEASE_RUNTIME")
APP_DIR = RUNTIME / "app"
V8_MODULE = "retrieval_only.scripts.answer_hybrid_v8_graph_kag_fallback"
CONFIRM_TOKEN = "RUN_GANSU_V8_CORE_COMPATIBILITY_16"

if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from tools.generic_kgqa_framework import build_match_cypher  # noqa: E402
from tools.generic_kgqa_framework.adapters import GansuFinanceAdapter  # noqa: E402


def load_jsonl(path: Path) -> List[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def unique(values: Iterable[object]) -> List[str]:
    seen = set()
    out = []
    for value in values:
        item = str(value or "").strip()
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def split_answers(value: object) -> List[str]:
    if isinstance(value, (list, tuple, set)):
        return unique(value)
    text = str(value or "").strip()
    return unique(text.split("||")) if text else []


def score_sets(predicted: Sequence[str], reference: Sequence[str]) -> Dict[str, float]:
    pred = set(predicted)
    ref = set(reference)
    tp = len(pred & ref)
    precision = tp / len(pred) if pred else (1.0 if not ref else 0.0)
    recall = tp / len(ref) if ref else (1.0 if not pred else 0.0)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "exact": float(pred == ref),
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


class CoreNeo4jExecutor:
    """Execute shared Core RouteSpec-generated Cypher against the production graph."""

    def __init__(self):
        required = ["GTF_NEO4J_URI", "GTF_NEO4J_USER", "GTF_NEO4J_PASSWORD", "GTF_NEO4J_DATABASE"]
        missing = [name for name in required if not os.environ.get(name)]
        if missing:
            raise RuntimeError(f"Missing runtime environment variables: {', '.join(missing)}")
        self.schema = GansuFinanceAdapter().schema()
        self.driver = GraphDatabase.driver(
            os.environ["GTF_NEO4J_URI"],
            auth=(os.environ["GTF_NEO4J_USER"], os.environ["GTF_NEO4J_PASSWORD"]),
        )
        self.database = os.environ["GTF_NEO4J_DATABASE"]

    def close(self) -> None:
        self.driver.close()

    def execute(self, route_name: str, subject: str) -> dict:
        route = self.schema.routes[route_name]
        cypher = build_match_cypher(self.schema, route, limit=500)
        start = time.perf_counter()
        with self.driver.session(database=self.database) as session:
            rows = list(session.run(cypher, {"subject": subject}))
        return {
            "route": route.qtype,
            "answers": unique(row.get("answer") for row in rows),
            "cypher": cypher,
            "latency_ms": round((time.perf_counter() - start) * 1000, 3),
        }


def load_v8():
    if str(APP_DIR) not in sys.path:
        sys.path.insert(0, str(APP_DIR))
    return importlib.import_module(V8_MODULE).answer_hybrid_v8


def extract_v8_answers(result: dict) -> List[str]:
    graph_answers = split_answers(result.get("graph_answers"))
    if graph_answers:
        return graph_answers
    return split_answers(result.get("kag_answers"))


def mean(rows: Sequence[dict], field: str) -> float:
    return sum(float(row[field]) for row in rows) / len(rows) if rows else 0.0


def summarize(rows: Sequence[dict], mode: str) -> dict:
    groups = defaultdict(list)
    for row in rows:
        groups[row["core_route"]].append(row)

    if mode == "core":
        def validation_metrics(items: Sequence[dict]) -> dict:
            return {
                "count": len(items),
                "core_nonempty": mean(items, "core_nonempty"),
                "mean_core_answer_count": mean(items, "core_answer_count"),
                "mean_core_latency_ms": mean(items, "core_latency_ms"),
            }

        return {
            "protocol": "gansu_shared_core_path_validation_v1",
            "mode": mode,
            "reference": "shared Core RouteSpec-generated typed path over the same read-only Neo4j graph",
            "overall": validation_metrics(rows),
            "by_route": {
                name: validation_metrics(items)
                for name, items in sorted(groups.items())
            },
        }

    def metrics(items: Sequence[dict]) -> dict:
        return {
            "count": len(items),
            "route_agreement": mean(items, "route_agreement"),
            "answer_exact": mean(items, "answer_exact"),
            "precision": mean(items, "precision"),
            "recall": mean(items, "recall"),
            "f1": mean(items, "f1"),
            "core_nonempty": mean(items, "core_nonempty"),
            "v8_nonempty": mean(items, "v8_nonempty"),
        }

    return {
        "protocol": "gansu_v8_shared_core_compatibility_v1",
        "mode": mode,
        "reference": "shared Core RouteSpec-generated typed path over the same read-only Neo4j graph",
        "overall": metrics(rows),
        "by_route": {name: metrics(items) for name, items in sorted(groups.items())},
    }


def write_outputs(out_dir: Path, rows: Sequence[dict], summary: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "results.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    with (out_dir / "metrics.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "qid", "core_route", "v8_qtype", "route_agreement", "answer_exact",
            "precision", "recall", "f1", "core_answer_count", "v8_answer_count",
            "core_latency_ms", "v8_latency_ms",
        ])
        writer.writeheader()
        writer.writerows({key: row[key] for key in writer.fieldnames} for row in rows)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--questions",
        type=Path,
        default=WORKSPACE / "experiments/gansu_core_compatibility/data/frozen_questions_16.jsonl",
    )
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--mode", choices=["core", "both"], default="core")
    parser.add_argument("--limit", type=int, default=0, help="0 means all frozen questions")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()

    items = load_jsonl(args.questions)
    if args.limit > 0:
        items = items[: args.limit]
    if args.mode == "both" and args.confirm != CONFIRM_TOKEN:
        raise SystemExit(f"--mode both requires --confirm {CONFIRM_TOKEN}")

    core = CoreNeo4jExecutor()
    v8_answer = load_v8() if args.mode == "both" else None
    rows = []
    try:
        for index, item in enumerate(items, start=1):
            core_result = core.execute(item["route"], item["subject"])
            v8_result = {}
            v8_latency_ms = 0.0
            if v8_answer is not None:
                start = time.perf_counter()
                v8_result = dict(v8_answer(item["question"]) or {})
                v8_latency_ms = round((time.perf_counter() - start) * 1000, 3)
            v8_answers = extract_v8_answers(v8_result)
            scores = score_sets(v8_answers, core_result["answers"]) if v8_answer else {
                "exact": 0.0, "precision": 0.0, "recall": 0.0, "f1": 0.0,
            }
            expected_qtypes = set(item.get("expected_v8_qtypes") or [])
            v8_qtype = str(v8_result.get("question_type", "") or "")
            row = {
                **item,
                "core_route": core_result["route"],
                "core_answers": core_result["answers"],
                "core_answer_count": len(core_result["answers"]),
                "core_nonempty": float(bool(core_result["answers"])),
                "core_latency_ms": core_result["latency_ms"],
                "core_cypher": core_result["cypher"],
                "v8_qtype": v8_qtype,
                "v8_route": str(v8_result.get("route", "") or ""),
                "v8_final_route": str(v8_result.get("final_route", "") or ""),
                "v8_answer_source": str(v8_result.get("answer_source", "") or ""),
                "v8_answers": v8_answers,
                "v8_answer_count": len(v8_answers),
                "v8_nonempty": float(bool(v8_answers)),
                "v8_latency_ms": v8_latency_ms,
                "route_agreement": float(v8_qtype in expected_qtypes) if v8_answer else 0.0,
                "answer_exact": scores["exact"],
                "precision": scores["precision"],
                "recall": scores["recall"],
                "f1": scores["f1"],
            }
            rows.append(row)
            print(
                f"[{index:02d}/{len(items):02d}] {item['qid']} route={item['route']} "
                f"core={len(core_result['answers'])} v8={len(v8_answers)} f1={scores['f1']:.4f}"
            )
    finally:
        core.close()

    summary = summarize(rows, args.mode)
    write_outputs(args.out_dir, rows, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
