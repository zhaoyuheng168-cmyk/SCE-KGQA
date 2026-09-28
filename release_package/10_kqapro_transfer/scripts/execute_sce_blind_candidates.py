#!/usr/bin/env python3
"""Execute and select KoPL candidates without reading validation labels."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_REPO = ROOT / "third_party" / "KQAPro_Baselines"

BINARY_FUNCTIONS = {"And", "Or", "SelectBetween", "QueryRelation", "QueryRelationQualifier"}
LOCATOR_FUNCTIONS = {"Find", "FindAll"}


def load_executor(repo: Path, kb_path: Path) -> Any:
    sys.path.insert(0, str(repo))
    from Program.executor_rule import RuleExecutor  # type: ignore

    return RuleExecutor(vocab={}, kb_json=str(kb_path))


def infer_dependencies(functions: list[str]) -> list[list[int]]:
    dependencies: list[list[int]] = []
    branch_stack: list[int] = []
    for index, function in enumerate(functions):
        if function in LOCATOR_FUNCTIONS:
            dependencies.append([])
            branch_stack.append(index - 1)
        elif function in BINARY_FUNCTIONS:
            if not branch_stack:
                raise ValueError(f"Missing branch for binary function at step {index}: {function}")
            dependencies.append([branch_stack[-1], index - 1])
            branch_stack.pop()
        else:
            if index == 0:
                raise ValueError(f"Program starts with non-locator: {function}")
            dependencies.append([index - 1])
    return dependencies


def render_result(result: Any, executor: Any) -> list[str]:
    if result is None:
        return []
    if isinstance(result, tuple):
        entity_ids = result[0] or []
        output = []
        for entity_id in entity_ids:
            if entity_id in executor.entities:
                output.append(str(executor.entities[entity_id]["name"]))
            elif entity_id in executor.concepts:
                output.append(str(executor.concepts[entity_id]["name"]))
            else:
                output.append(str(entity_id))
        return output
    return [str(result)]


def execute_program(executor: Any, program: list[dict[str, Any]]) -> dict[str, Any]:
    functions = [str(step.get("function") or "") for step in program]
    dependencies = infer_dependencies(functions)
    memory: list[Any] = []
    trace = []
    started = time.perf_counter()

    for index, (step, deps) in enumerate(zip(program, dependencies)):
        function = functions[index]
        inputs = [str(value) for value in step.get("inputs", [])]
        method = getattr(executor, function)
        dep_results = [memory[dep] for dep in deps]
        step_started = time.perf_counter()
        result = method(dep_results, inputs)
        memory.append(result)
        entity_count = 0
        fact_count = 0
        if isinstance(result, tuple):
            entity_count = len(result[0] or [])
            fact_count = len(result[1] or []) if len(result) > 1 and result[1] is not None else 0
        trace.append(
            {
                "step": index,
                "function": function,
                "dependencies": deps,
                "entity_count": entity_count,
                "fact_count": fact_count,
                "elapsed_ms": round((time.perf_counter() - step_started) * 1000, 3),
            }
        )

    answers = render_result(memory[-1] if memory else None, executor)
    return {
        "status": "ok",
        "answers": answers,
        "nonempty": bool(answers),
        "evidence_fact_steps": sum(item["fact_count"] > 0 for item in trace),
        "trace": trace,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        "error": "",
    }


def content_tokens(text: str) -> set[str]:
    stop = {
        "a", "an", "and", "are", "as", "at", "be", "by", "did", "do", "does",
        "for", "from", "has", "have", "how", "in", "is", "it", "of", "on",
        "or", "that", "the", "this", "to", "was", "were", "what", "when",
        "where", "which", "who", "whose", "with",
    }
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if len(token) > 1 and token not in stop
    }


def program_question_relevance(question: str, program: list[dict[str, Any]]) -> float:
    question_tokens = content_tokens(question)
    if not question_tokens:
        return 0.0
    program_tokens: set[str] = set()
    for step in program:
        function = str(step.get("function") or "")
        if function == "Find":
            continue
        for value in step.get("inputs", []):
            program_tokens.update(content_tokens(str(value)))
    if not program_tokens:
        return 0.0
    overlap = len(question_tokens & program_tokens)
    return overlap / len(program_tokens)


def execute_candidate(executor: Any, question: str, candidate: dict[str, Any]) -> dict[str, Any]:
    try:
        execution = execute_program(executor, candidate["program"])
    except Exception as exc:
        execution = {
            "status": "error",
            "answers": [],
            "nonempty": False,
            "evidence_fact_steps": 0,
            "trace": [],
            "elapsed_ms": 0.0,
            "error": f"{type(exc).__name__}: {exc}",
        }

    relevance = program_question_relevance(question, candidate["program"])
    model_score = float(candidate.get("model_score") or 0.0)
    schema_score = float(candidate.get("schema_score") or 0.0)
    execution_bonus = 1.5 if execution["status"] == "ok" else -8.0
    nonempty_bonus = 2.0 if execution["nonempty"] else -2.0
    evidence_bonus = min(float(execution["evidence_fact_steps"]), 2.0) * 0.3
    final_score = (
        model_score
        + 0.06 * schema_score
        + execution_bonus
        + nonempty_bonus
        + 2.5 * relevance
        + evidence_bonus
    )
    return {
        **candidate,
        "question_relevance": round(relevance, 6),
        "execution": execution,
        "sce_selection_score": round(final_score, 6),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kb", type=Path, default=ROOT / "data" / "kqapro" / "kb.json")
    parser.add_argument("--official-repo", type=Path, default=OFFICIAL_REPO)
    parser.add_argument(
        "--input",
        type=Path,
        default=ROOT / "work" / "kqapro_val_sce_schema_selected.jsonl",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "work" / "kqapro_val_sce_blind_predictions.jsonl",
    )
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    if args.output.exists() and not args.overwrite and not args.resume:
        raise FileExistsError(f"Refusing to overwrite: {args.output}")

    executor = load_executor(args.official_repo, args.kb)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    completed_ids: set[str] = set()
    if args.resume and args.output.exists():
        with args.output.open("r", encoding="utf-8") as existing:
            for line in existing:
                line = line.strip()
                if line:
                    completed_ids.add(str(json.loads(line)["question_id"]))

    rows_written = 0
    mode = "a" if args.resume and args.output.exists() else "w"
    with args.input.open("r", encoding="utf-8") as source, args.output.open(mode, encoding="utf-8") as target:
        for line in source:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if str(row["question_id"]) in completed_ids:
                continue
            executed = [
                execute_candidate(executor, row["question"], candidate)
                for candidate in row["candidates"]
            ]
            bart_top1 = next(item for item in executed if int(item["rank"]) == 1)
            schema_selected_text = row["selected_candidate"]["serialized_program"]
            schema_selected = next(
                item for item in executed if item["serialized_program"] == schema_selected_text
            )
            full_selected = max(executed, key=lambda item: item["sce_selection_score"])
            output = {
                "question_id": row["question_id"],
                "source_index": row["source_index"],
                "question": row["question"],
                "input_policy": "question_only_no_gold_program_sparql_answer_or_choices",
                "bart_top1": bart_top1,
                "schema_selected": schema_selected,
                "sce_full_selected": full_selected,
                "candidates": executed,
            }
            target.write(json.dumps(output, ensure_ascii=False) + "\n")
            target.flush()
            rows_written += 1
            print(
                f"executed {len(completed_ids) + rows_written} {row['question_id']}",
                flush=True,
            )
            if args.limit > 0 and rows_written >= args.limit:
                break

    print(
        json.dumps(
            {
                "output": str(args.output),
                "rows": len(completed_ids) + rows_written,
                "new_rows": rows_written,
                "gold_fields_read": [],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
