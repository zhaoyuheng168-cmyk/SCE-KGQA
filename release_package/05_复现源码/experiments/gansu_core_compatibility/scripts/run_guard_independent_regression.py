# -*- coding: utf-8 -*-
"""Build and evaluate an independent stratified Core route-guard regression set."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable, List, Mapping, Sequence

from neo4j import GraphDatabase


WORKSPACE = Path(__file__).resolve().parents[3]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from core_route_guard import decide_guard, infer_goal_type, select_route  # noqa: E402
from run_gansu_v8_core_compatibility import score_sets, split_answers, unique  # noqa: E402
from run_offline_core_route_guard_ablation import ALLOWED_V8_QTYPES, ReadOnlyGraph  # noqa: E402


DEFAULT_FORMAL = WORKSPACE / "experiments/baselines/results/formal1300_protocol_v2/sce_kgqa_full_formal1300.jsonl"
DEFAULT_GOLD = WORKSPACE / "experiments/baselines/reports/unified_formal1300_20260607/sce_kgqa_full/task_aware_metrics/paper_corrected_metrics_rows.csv"
DEFAULT_DEV = WORKSPACE / "experiments/gansu_core_compatibility/data/frozen_questions_16.jsonl"


def load_jsonl(path: Path) -> List[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def load_gold(path: Path) -> dict:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {
        str(row.get("question_id") or row.get("\ufeffquestion_id") or ""): row
        for row in rows
    }


def raw_answers(row: dict) -> List[str]:
    raw = row.get("raw") or {}
    graph = split_answers(raw.get("graph_answers"))
    if graph:
        return graph
    answer = row.get("answer")
    return unique(answer if isinstance(answer, list) else [])


def chunked(values: Sequence[str], size: int = 1000):
    for index in range(0, len(values), size):
        yield values[index:index + size]


def load_type_map(driver, database: str, names: Iterable[str]) -> dict:
    selected = sorted(set(unique(names)))
    result = defaultdict(list)
    cypher = """
MATCH (n)
WHERE coalesce(n.name, '') IN $names
UNWIND labels(n) AS label
RETURN n.name AS name, collect(DISTINCT replace(label, 'GansuTechFinanceDevV1Enhance.', '')) AS types
""".strip()
    with driver.session(database=database) as session:
        for batch in chunked(selected):
            for row in session.run(cypher, {"names": batch}):
                result[str(row["name"])] = unique(row["types"])
    return dict(result)


def deterministic_stratified_sample(rows: Sequence[dict], candidate_count: int, bypass_count: int) -> List[dict]:
    candidates = defaultdict(list)
    bypass = defaultdict(list)
    for row in sorted(rows, key=lambda item: str(item["qid"])):
        if row["guard_selected_route"]:
            candidates[row["guard_selected_route"]].append(row)
        else:
            bypass[row["v8_qtype"] or "unknown"].append(row)

    selected = []
    route_names = sorted(candidates)
    while len([row for row in selected if row["sample_stratum"] == "guard_candidate"]) < candidate_count:
        progressed = False
        for name in route_names:
            bucket = candidates[name]
            if bucket:
                row = bucket.pop(0)
                row["sample_stratum"] = "guard_candidate"
                selected.append(row)
                progressed = True
                if len([item for item in selected if item["sample_stratum"] == "guard_candidate"]) >= candidate_count:
                    break
        if not progressed:
            break

    bypass_selected = 0
    bypass_names = sorted(bypass)
    while bypass_selected < bypass_count:
        progressed = False
        for name in bypass_names:
            bucket = bypass[name]
            if bucket:
                row = bucket.pop(0)
                row["sample_stratum"] = "core_bypass"
                selected.append(row)
                bypass_selected += 1
                progressed = True
                if bypass_selected >= bypass_count:
                    break
        if not progressed:
            break
    return selected


def mean(rows: Sequence[dict], field: str) -> float:
    return sum(float(row[field]) for row in rows) / len(rows) if rows else 0.0


def summarize(rows: Sequence[dict]) -> dict:
    groups = defaultdict(list)
    for row in rows:
        groups[row["sample_stratum"]].append(row)

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
            "unchanged_rate": mean(items, "unchanged"),
        }

    return {
        "protocol": "gansu_core_route_guard_independent_regression_v1",
        "sample_is_independent_from_frozen_16": True,
        "reference": "existing formal1300 task-aware gold_items",
        "overall": metrics(rows),
        "by_stratum": {name: metrics(items) for name, items in sorted(groups.items())},
        "sample_core_route_counts": dict(Counter(row["guard_selected_route"] or "bypass" for row in rows)),
        "sample_v8_qtype_counts": dict(Counter(row["v8_qtype"] or "unknown" for row in rows)),
    }


def write_outputs(out_dir: Path, rows: Sequence[dict], summary: Mapping[str, object]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "frozen_regression_80.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    fields = [
        "qid", "sample_stratum", "v8_qtype", "guard_action", "guard_reason",
        "guard_selected_route", "guard_target_type", "guard_triggered",
        "original_exact", "guarded_exact", "original_f1", "guarded_f1",
        "corrected_error", "introduced_error", "unchanged",
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
    parser.add_argument("--formal", type=Path, default=DEFAULT_FORMAL)
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--dev-set", type=Path, default=DEFAULT_DEV)
    parser.add_argument("--candidate-count", type=int, default=40)
    parser.add_argument("--bypass-count", type=int, default=40)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    formal = load_jsonl(args.formal)
    gold_map = load_gold(args.gold)
    dev_questions = {row["question"] for row in load_jsonl(args.dev_set)}
    graph = ReadOnlyGraph()
    all_names = []
    prepared = []
    try:
        for source in formal:
            qid = str(source.get("qid") or "")
            question = str(source.get("question") or "")
            raw = source.get("raw") or {}
            subject = str(raw.get("subject") or "").strip()
            answers = raw_answers(source)
            if not qid or question in dev_questions or qid not in gold_map:
                continue
            all_names.extend([subject, *answers])
            prepared.append({
                "qid": qid,
                "question": question,
                "subject": subject,
                "v8_qtype": str(raw.get("question_type") or ""),
                "v8_route": str(raw.get("route") or ""),
                "v8_answer_source": str(raw.get("answer_source") or ""),
                "v8_answers": answers,
                "gold_answers": split_answers(gold_map[qid].get("gold_items")),
            })

        type_map = load_type_map(graph.driver, graph.database, all_names)
        classified = []
        for row in prepared:
            target_type = infer_goal_type(row["question"], graph.schema)
            route = select_route(
                graph.schema,
                subject_types=type_map.get(row["subject"], ()),
                target_type=target_type,
            )
            row["guard_selected_route"] = route.qtype if route else ""
            row["guard_target_type"] = target_type
            classified.append(row)

        selected = deterministic_stratified_sample(
            classified,
            candidate_count=args.candidate_count,
            bypass_count=args.bypass_count,
        )
        evaluated = []
        for index, row in enumerate(selected, start=1):
            names = [row["subject"], *row["v8_answers"]]
            decision = decide_guard(
                graph.schema,
                question=row["question"],
                subject_types=type_map.get(row["subject"], ()),
                v8_qtype=row["v8_qtype"],
                v8_answers=row["v8_answers"],
                answer_types={name: type_map.get(name, ()) for name in names},
                allowed_v8_qtypes=ALLOWED_V8_QTYPES,
            )
            guarded_answers = list(row["v8_answers"])
            if decision.action == "replace_with_core":
                guarded_answers = graph.execute_route(decision.selected_route, row["subject"])
            original = score_sets(row["v8_answers"], row["gold_answers"])
            guarded = score_sets(guarded_answers, row["gold_answers"])
            evaluated_row = {
                **row,
                "guard_action": decision.action,
                "guard_reason": decision.reason,
                "guard_selected_route": decision.selected_route,
                "guard_target_type": decision.target_type,
                "guarded_answers": guarded_answers,
                "guard_triggered": float(decision.action == "replace_with_core"),
                "original_exact": original["exact"],
                "guarded_exact": guarded["exact"],
                "original_f1": original["f1"],
                "guarded_f1": guarded["f1"],
                "corrected_error": float(original["exact"] == 0.0 and guarded["exact"] == 1.0),
                "introduced_error": float(original["exact"] == 1.0 and guarded["exact"] == 0.0),
                "unchanged": float(set(row["v8_answers"]) == set(guarded_answers)),
            }
            evaluated.append(evaluated_row)
            print(
                f"[{index:02d}/{len(selected):02d}] {row['qid']} {row['sample_stratum']} "
                f"guard={decision.action} exact={original['exact']:.0f}->{guarded['exact']:.0f}"
            )
    finally:
        graph.close()

    summary = summarize(evaluated)
    write_outputs(args.out_dir, evaluated, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
