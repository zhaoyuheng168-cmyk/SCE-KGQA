#!/usr/bin/env python3
"""Run explicit KQA Pro KoPL programs with the official rule semantics.

This adapter evaluates structured execution only. It consumes the gold KoPL
program supplied by KQA Pro, so its output must not be reported as end-to-end
question-answering accuracy.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


DEFAULT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OFFICIAL_REPO = DEFAULT_ROOT / "third_party" / "KQAPro_Baselines"
DEFAULT_KB = DEFAULT_ROOT / "data" / "kqapro" / "kb.json"
DEFAULT_VAL = DEFAULT_ROOT / "data" / "kqapro" / "val.json"
DEFAULT_SAMPLE = DEFAULT_ROOT / "work" / "kqapro_answer_level_sample_100.csv"


def normalize_answer(value: object) -> str:
    text = "" if value is None else str(value)
    date_match = re.fullmatch(r"\s*(\d{1,4})[/-](\d{1,2})[/-](\d{1,2})\s*", text)
    if date_match:
        year, month, day = date_match.groups()
        text = f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    text = re.sub(r"\s+", "", text.lower())
    return re.sub(r"""["'`.,;:!?\[\]{}()]""", "", text)


def load_official_executor(repo: Path, kb_path: Path) -> Any:
    if not (repo / "Program" / "executor_rule.py").is_file():
        raise FileNotFoundError(f"Official executor not found under: {repo}")
    sys.path.insert(0, str(repo))
    from Program.executor_rule import RuleExecutor  # type: ignore

    return RuleExecutor(vocab={}, kb_json=str(kb_path))


def result_size(result: Any) -> int:
    if isinstance(result, tuple) and result and isinstance(result[0], list):
        return len(result[0])
    return 0 if result is None else 1


def render_result(result: Any, executor: Any) -> list[str]:
    if result is None:
        return []
    if isinstance(result, tuple):
        entity_ids = result[0]
        rendered = []
        for entity_id in entity_ids:
            if entity_id in executor.entities:
                rendered.append(str(executor.entities[entity_id]["name"]))
            elif entity_id in executor.concepts:
                rendered.append(str(executor.concepts[entity_id]["name"]))
            else:
                rendered.append(str(entity_id))
        return rendered
    return [str(result)]


def execute_program(executor: Any, program: list[dict[str, Any]]) -> tuple[list[str], list[dict[str, Any]]]:
    memory: list[Any] = []
    trace: list[dict[str, Any]] = []
    for index, step in enumerate(program):
        function = str(step["function"])
        dependencies = [memory[int(dep)] for dep in step.get("dependencies", [])]
        inputs = [str(value) for value in step.get("inputs", [])]
        method = getattr(executor, function)
        started = time.perf_counter()
        result = method(dependencies, inputs)
        elapsed_ms = (time.perf_counter() - started) * 1000
        memory.append(result)
        trace.append(
            {
                "step": index,
                "function": function,
                "dependencies": step.get("dependencies", []),
                "result_size": result_size(result),
                "elapsed_ms": round(elapsed_ms, 3),
            }
        )
    return render_result(memory[-1] if memory else None, executor), trace


def read_selection(sample_csv: Path | None, val_count: int, limit: int) -> list[dict[str, Any]]:
    if sample_csv is None:
        count = val_count if limit <= 0 else min(limit, val_count)
        return [
            {
                "sample_id": f"KQAPRO_VAL_{index:05d}",
                "source_index": index,
                "complexity_bucket": "full_validation",
            }
            for index in range(count)
        ]

    with sample_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if limit > 0:
        rows = rows[:limit]
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str], overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing result: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--official-repo", type=Path, default=DEFAULT_OFFICIAL_REPO)
    parser.add_argument("--kb", type=Path, default=DEFAULT_KB)
    parser.add_argument("--val", type=Path, default=DEFAULT_VAL)
    parser.add_argument("--sample-csv", type=Path, default=DEFAULT_SAMPLE)
    parser.add_argument("--full-validation", action="store_true")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_ROOT / "work" / "kqapro_official_semantics_sample_100_results.csv",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=DEFAULT_ROOT / "work" / "kqapro_official_semantics_sample_100_summary.csv",
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    val_rows = json.loads(args.val.read_text(encoding="utf-8"))
    sample_csv = None if args.full_validation else args.sample_csv
    selection = read_selection(sample_csv, len(val_rows), args.limit)
    executor = load_official_executor(args.official_repo, args.kb)

    result_rows: list[dict[str, Any]] = []
    bucket_counts: dict[str, Counter[str]] = defaultdict(Counter)
    function_counts: dict[str, Counter[str]] = defaultdict(Counter)
    started_all = time.perf_counter()

    for selected in selection:
        source_index = int(selected["source_index"])
        source = val_rows[source_index]
        bucket = str(selected.get("complexity_bucket") or "unclassified")
        error = ""
        status = "ok"
        trace: list[dict[str, Any]] = []
        try:
            predicted, trace = execute_program(executor, source["program"])
        except Exception as exc:
            predicted = []
            status = "error"
            error = f"{type(exc).__name__}: {exc}"

        exact = any(normalize_answer(item) == normalize_answer(source.get("answer")) for item in predicted)
        bucket_counts[bucket]["total"] += 1
        bucket_counts[bucket]["correct"] += int(exact)
        for step in source.get("program", []):
            function = str(step.get("function") or "")
            function_counts[function]["total"] += 1
            function_counts[function]["correct_questions"] += int(exact)

        result_rows.append(
            {
                "sample_id": selected.get("sample_id", f"KQAPRO_VAL_{source_index:05d}"),
                "source_index": source_index,
                "complexity_bucket": bucket,
                "question": source.get("question", ""),
                "gold_answer": source.get("answer", ""),
                "predicted_answer": "||".join(predicted),
                "exact_match": str(exact).lower(),
                "status": status,
                "error": error,
                "program_functions": "||".join(step.get("function", "") for step in source.get("program", [])),
                "trace": json.dumps(trace, ensure_ascii=False),
            }
        )

    elapsed_seconds = time.perf_counter() - started_all
    correct = sum(row["exact_match"] == "true" for row in result_rows)
    errors = sum(row["status"] == "error" for row in result_rows)
    summary_rows: list[dict[str, Any]] = [
        {"dimension": "overall", "value": "total", "count": len(result_rows)},
        {"dimension": "overall", "value": "correct", "count": correct},
        {
            "dimension": "overall",
            "value": "exact_match",
            "count": f"{correct / len(result_rows):.6f}" if result_rows else "0.000000",
        },
        {"dimension": "overall", "value": "runtime_errors", "count": errors},
        {"dimension": "runtime", "value": "elapsed_seconds", "count": f"{elapsed_seconds:.3f}"},
        {
            "dimension": "protocol",
            "value": "scope",
            "count": "gold_KoPL_oracle_program_execution_not_end_to_end_QA",
        },
        {
            "dimension": "protocol",
            "value": "official_executor_commit",
            "count": "14d87cd22eb79f702fd4ad5c09240bef126d9dce",
        },
    ]
    for bucket, counts in sorted(bucket_counts.items()):
        total = counts["total"]
        summary_rows.append(
            {
                "dimension": "complexity_bucket",
                "value": bucket,
                "count": f"{counts['correct']}/{total} ({counts['correct'] / total:.6f})",
            }
        )
    for function, counts in sorted(function_counts.items()):
        summary_rows.append(
            {
                "dimension": "function_coverage",
                "value": function,
                "count": counts["total"],
            }
        )

    write_csv(
        args.output,
        result_rows,
        [
            "sample_id",
            "source_index",
            "complexity_bucket",
            "question",
            "gold_answer",
            "predicted_answer",
            "exact_match",
            "status",
            "error",
            "program_functions",
            "trace",
        ],
        args.overwrite,
    )
    write_csv(args.summary, summary_rows, ["dimension", "value", "count"], args.overwrite)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "summary": str(args.summary),
                "correct": correct,
                "total": len(result_rows),
                "runtime_errors": errors,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
