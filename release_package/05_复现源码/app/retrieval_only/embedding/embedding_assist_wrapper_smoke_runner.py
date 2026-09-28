# -*- coding: utf-8 -*-
"""Run small smoke tests for embedding assist candidates.

This runner is for the Stage EMB experiment branch only. It does not call V8/V7,
does not generate final answers, and does not evaluate graph_answers.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List

from embedding_assist_wrapper import assist_retrieve
from embedding_config import PROJECT_ROOT, get_embedding_config


DEFAULT_CASES = PROJECT_ROOT / "experiment_notes" / "embedding_strict_smoke_12.jsonl"
DEFAULT_JSONL_OUT = PROJECT_ROOT / "experiment_notes" / "embedding_assist_wrapper_smoke_latest.jsonl"
DEFAULT_MD_OUT = PROJECT_ROOT / "experiment_notes" / "embedding_assist_wrapper_smoke_latest.md"


def _read_cases(path: Path) -> List[Dict[str, object]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _flatten_chunks(result: Dict[str, object]) -> List[Dict[str, object]]:
    chunks = []
    for group in result.get("evidence_groups", []) or []:
        for chunk in group.get("chunks", []) or []:
            row = dict(chunk)
            row["entity_filter"] = group.get("entity_filter", "")
            row["source_relation_filter"] = group.get("source_relation_filter", "")
            chunks.append(row)
    return chunks


def _summarize_result(result: Dict[str, object]) -> Dict[str, object]:
    chunks = _flatten_chunks(result)
    top = chunks[0] if chunks else {}
    return {
        "used_as_assist": bool(result.get("used_as_assist")),
        "is_final_answer": bool(result.get("is_final_answer")),
        "kg_confirmed_mode": bool(result.get("kg_confirmed_mode")),
        "entity_filters": result.get("entity_filters", []),
        "relation_filters": result.get("relation_filters", []),
        "graph_answer_filters": result.get("graph_answer_filters", []),
        "selection_reason": result.get("selection_reason", {}),
        "chunk_count": len(chunks),
        "top_chunk_id": top.get("chunk_id", ""),
        "top_score": top.get("score", None),
        "top_source_path": top.get("source_path", ""),
        "top_entity_filter": top.get("entity_filter", ""),
        "top_relation_filter": top.get("source_relation_filter", ""),
    }


def run_cases(cases: Iterable[Dict[str, object]], evidence_top_k: int | None = None) -> List[Dict[str, object]]:
    records = []
    for case in cases:
        top_k = int(evidence_top_k or case.get("top_k", 5))
        min_score = float(case.get("min_score", 0.60))
        manual = assist_retrieve(
            str(case["query"]),
            entity_filters=case.get("entity_filter"),
            relation_filters=case.get("source_relation_filter"),
            graph_answers=case.get("graph_answer"),
            evidence_top_k=top_k,
            evidence_min_score=min_score,
        )
        auto = assist_retrieve(
            str(case["query"]),
            entity_top_k=5,
            entity_min_score=0.60,
            evidence_top_k=top_k,
            evidence_min_score=min_score,
        )
        records.append(
            {
                "id": case.get("id", ""),
                "query": case.get("query", ""),
                "expect": case.get("expect", ""),
                "manual": _summarize_result(manual),
                "auto": _summarize_result(auto),
            }
        )
    return records


def _write_jsonl(path: Path, records: List[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in records:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _fmt_items(items: object) -> str:
    if not items:
        return "-"
    if isinstance(items, list):
        return "<br>".join(str(item) for item in items) or "-"
    return str(items)


def _write_markdown(path: Path, records: List[Dict[str, object]]) -> None:
    cfg = get_embedding_config()
    lines = [
        "# Embedding Assist Wrapper Smoke 最新报告",
        "",
        f"- 生成时间：{datetime.now().isoformat(timespec='seconds')}",
        f"- 模型路径：{cfg['embedding_model_name'] or '<EMPTY>'}",
        "- 说明：本报告只评估 embedding assist/evidence candidates，不评估最终答案。",
        "- 边界：`is_final_answer` 必须为 `false`，最终答案仍由 KG/V8/V7 受控主流程决定。",
        "",
        "| case | query | manual mode | manual chunks | manual top | auto entities | auto relations | auto chunks | auto top |",
        "|---|---|---|---:|---|---|---|---:|---|",
    ]
    for row in records:
        manual = row["manual"]
        auto = row["auto"]
        lines.append(
            "| {id} | {query} | {m_mode} | {m_count} | {m_top} | {a_entities} | {a_relations} | {a_count} | {a_top} |".format(
                id=row.get("id", ""),
                query=str(row.get("query", "")).replace("|", "\\|"),
                m_mode="KG-confirmed" if manual.get("kg_confirmed_mode") else "manual",
                m_count=manual.get("chunk_count", 0),
                m_top=manual.get("top_chunk_id") or "-",
                a_entities=_fmt_items(auto.get("entity_filters")),
                a_relations=_fmt_items(auto.get("relation_filters")),
                a_count=auto.get("chunk_count", 0),
                a_top=auto.get("top_chunk_id") or "-",
            )
        )
    lines.extend(
        [
            "",
            "## 自动选择原因",
            "",
        ]
    )
    for row in records:
        reason = row["auto"].get("selection_reason", {}) or {}
        lines.extend(
            [
                f"### {row.get('id', '')}",
                "",
                f"- 实体类型过滤：{_fmt_items(reason.get('entity_label_filters'))}",
                f"- 实体类型原因：{reason.get('entity_label_reason', '-')}",
                f"- 已选实体类型：{_fmt_items(reason.get('selected_entity_labels'))}",
                f"- 关系原因：{reason.get('relation_reason', '-')}",
                "",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument("--jsonl-out", default=str(DEFAULT_JSONL_OUT))
    parser.add_argument("--md-out", default=str(DEFAULT_MD_OUT))
    parser.add_argument("--evidence-top-k", type=int, default=None)
    args = parser.parse_args()

    cases = _read_cases(Path(args.cases))
    records = run_cases(cases, evidence_top_k=args.evidence_top_k)
    _write_jsonl(Path(args.jsonl_out), records)
    _write_markdown(Path(args.md_out), records)
    print(json.dumps({"cases": len(records), "jsonl_out": args.jsonl_out, "md_out": args.md_out}, ensure_ascii=False))


if __name__ == "__main__":
    main()
