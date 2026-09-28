# -*- coding: utf-8 -*-
"""Run user-question robustness smoke tests for embedding assist modules."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List

from embedding_assist_wrapper import assist_retrieve
from embedding_config import PROJECT_ROOT, get_embedding_config
from graph_answer_reranker import rerank_graph_answers


DEFAULT_CASES = PROJECT_ROOT / "experiment_notes" / "embedding_robustness_smoke_20.jsonl"
DEFAULT_JSONL_OUT = PROJECT_ROOT / "experiment_notes" / "embedding_robustness_smoke_latest.jsonl"
DEFAULT_MD_OUT = PROJECT_ROOT / "experiment_notes" / "embedding_robustness_smoke_latest.md"


def _read_cases(path: Path) -> List[Dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _contains(items: object, expected: object) -> bool:
    if not expected:
        return False
    needle = str(expected)
    if isinstance(items, list):
        return any(needle in str(item) for item in items)
    return needle in str(items)


def _rerank_case(case: Dict[str, object]) -> Dict[str, object]:
    result = rerank_graph_answers(
        str(case["query"]),
        case.get("graph_answers", []),
        top_n=int(case.get("top_n", 0)) or None,
    )
    display = result.get("display_answers", [])
    top = str(display[0].get("answer_text", "")) if display else ""
    expected_top = str(case.get("expected_top", ""))
    passed = bool(expected_top and expected_top in top)
    return {
        "mode": "rerank",
        "passed": passed,
        "top": top,
        "expected_top": expected_top,
        "display_order": result.get("display_order", ""),
        "display_reason": result.get("display_reason", ""),
        "input_count": result.get("input_count", 0),
        "ranked_count": len(result.get("ranked_answers", [])),
        "is_final_answer": result.get("is_final_answer"),
    }


def _assist_case(case: Dict[str, object]) -> Dict[str, object]:
    result = assist_retrieve(
        str(case["query"]),
        entity_top_k=5,
        entity_min_score=0.60,
        evidence_top_k=3,
        evidence_min_score=0.60,
    )
    entity_ok = _contains(result.get("entity_filters", []), case.get("expected_entity"))
    relation_ok = _contains(result.get("relation_filters", []), case.get("expected_relation"))
    expected_entity = case.get("expected_entity")
    expected_relation = case.get("expected_relation")
    if expected_entity and expected_relation:
        passed = entity_ok and relation_ok
    elif expected_entity:
        passed = entity_ok
    elif expected_relation:
        passed = relation_ok
    else:
        passed = not result.get("entity_filters") and not result.get("relation_filters")
    reason = result.get("selection_reason", {}) or {}
    return {
        "mode": "assist",
        "passed": passed,
        "entity_filters": result.get("entity_filters", []),
        "relation_filters": result.get("relation_filters", []),
        "expected_entity": expected_entity or "",
        "expected_relation": expected_relation or "",
        "entity_ok": entity_ok,
        "relation_ok": relation_ok,
        "relation_reason": reason.get("relation_reason", ""),
        "entity_label_reason": reason.get("entity_label_reason", ""),
        "is_final_answer": result.get("is_final_answer"),
    }


def run_cases(cases: Iterable[Dict[str, object]]) -> List[Dict[str, object]]:
    records = []
    for case in cases:
        category = str(case.get("category", ""))
        if category == "rerank":
            outcome = _rerank_case(case)
        else:
            outcome = _assist_case(case)
        records.append(
            {
                "id": case.get("id", ""),
                "category": category,
                "query": case.get("query", ""),
                "expect": case.get("expect", ""),
                **outcome,
            }
        )
    return records


def _write_jsonl(path: Path, records: List[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in records:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _fmt_items(value: object) -> str:
    if not value:
        return "-"
    if isinstance(value, list):
        return "<br>".join(str(item) for item in value) or "-"
    return str(value)


def _write_markdown(path: Path, records: List[Dict[str, object]]) -> None:
    cfg = get_embedding_config()
    counts = Counter(str(row.get("category", "")) for row in records)
    passes = Counter(str(row.get("category", "")) for row in records if row.get("passed"))
    lines = [
        "# Embedding 用户问法鲁棒性 Smoke 最新报告",
        "",
        f"- 生成时间：{datetime.now().isoformat(timespec='seconds')}",
        f"- 模型路径：{cfg['embedding_model_name'] or '<EMPTY>'}",
        "- 说明：本报告只评估 embedding 对用户问法鲁棒性的辅助潜力，不评估 V8/V7 最终答案。",
        "- 边界：所有模块均应 `is_final_answer=false`。",
        "",
        "## 分类通过概览",
        "",
        "| category | pass | total |",
        "|---|---:|---:|",
    ]
    for category in sorted(counts):
        lines.append(f"| {category} | {passes[category]} | {counts[category]} |")
    lines.extend(
        [
            "",
            "## 明细",
            "",
            "| id | category | pass | query | observed | expected |",
            "|---|---|---|---|---|---|",
        ]
    )
    for row in records:
        if row.get("mode") == "rerank":
            observed = f"top={row.get('top', '-')}; order={row.get('display_order', '-')}"
            expected = row.get("expected_top", "")
        else:
            observed = (
                f"entities={_fmt_items(row.get('entity_filters'))}; "
                f"relations={_fmt_items(row.get('relation_filters'))}"
            )
            expected = f"entity={row.get('expected_entity', '-')}; relation={row.get('expected_relation', '-')}"
        lines.append(
            "| {id} | {cat} | {passed} | {query} | {observed} | {expected} |".format(
                id=row.get("id", ""),
                cat=row.get("category", ""),
                passed="Y" if row.get("passed") else "N",
                query=str(row.get("query", "")).replace("|", "\\|"),
                observed=str(observed).replace("|", "\\|"),
                expected=str(expected).replace("|", "\\|"),
            )
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument("--jsonl-out", default=str(DEFAULT_JSONL_OUT))
    parser.add_argument("--md-out", default=str(DEFAULT_MD_OUT))
    args = parser.parse_args()
    records = run_cases(_read_cases(Path(args.cases)))
    _write_jsonl(Path(args.jsonl_out), records)
    _write_markdown(Path(args.md_out), records)
    print(json.dumps({"cases": len(records), "jsonl_out": args.jsonl_out, "md_out": args.md_out}, ensure_ascii=False))


if __name__ == "__main__":
    main()
