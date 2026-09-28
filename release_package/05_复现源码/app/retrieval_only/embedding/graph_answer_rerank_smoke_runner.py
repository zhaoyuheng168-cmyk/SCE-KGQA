# -*- coding: utf-8 -*-
"""Run small smoke tests for graph answer embedding rerank."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List

from embedding_config import PROJECT_ROOT, get_embedding_config
from graph_answer_reranker import rerank_graph_answers


DEFAULT_CASES = PROJECT_ROOT / "experiment_notes" / "graph_answer_rerank_smoke_8.jsonl"
DEFAULT_JSONL_OUT = PROJECT_ROOT / "experiment_notes" / "graph_answer_rerank_smoke_latest.jsonl"
DEFAULT_MD_OUT = PROJECT_ROOT / "experiment_notes" / "graph_answer_rerank_smoke_latest.md"


def _read_cases(path: Path) -> List[Dict[str, object]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def run_cases(cases: Iterable[Dict[str, object]]) -> List[Dict[str, object]]:
    records = []
    for case in cases:
        result = rerank_graph_answers(
            str(case["query"]),
            case.get("graph_answers", []),
            context=str(case.get("context", "")),
            top_n=int(case.get("top_n", 0)) or None,
            display_strategy=str(case.get("display_strategy", "conservative")),
            min_top_score=float(case.get("min_top_score", 0.45)),
            min_score_gap=float(case.get("min_score_gap", 0.05)),
        )
        ranked = result.get("ranked_answers", [])
        display = result.get("display_answers", [])
        records.append(
            {
                "id": case.get("id", ""),
                "query": case.get("query", ""),
                "expect": case.get("expect", ""),
                "input_count": result.get("input_count", 0),
                "ranked_count": len(ranked),
                "display_count": len(display),
                "display_order": result.get("display_order", ""),
                "display_reason": result.get("display_reason", ""),
                "is_final_answer": result.get("is_final_answer", None),
                "top_answer": ranked[0].get("answer_text", "") if ranked else "",
                "display_top_answer": display[0].get("answer_text", "") if display else "",
                "ranked_answers": [
                    {
                        "embedding_rank": row.get("embedding_rank"),
                        "original_rank": row.get("original_rank"),
                        "embedding_score": row.get("embedding_score"),
                        "answer_text": row.get("answer_text"),
                    }
                    for row in ranked
                ],
                "display_answers": [
                    {
                        "embedding_rank": row.get("embedding_rank"),
                        "original_rank": row.get("original_rank"),
                        "embedding_score": row.get("embedding_score"),
                        "answer_text": row.get("answer_text"),
                    }
                    for row in display
                ],
            }
        )
    return records


def _write_jsonl(path: Path, records: List[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in records:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _fmt_score(score: object) -> str:
    if score is None:
        return "-"
    try:
        return f"{float(score):.4f}"
    except Exception:
        return str(score)


def _write_markdown(path: Path, records: List[Dict[str, object]]) -> None:
    cfg = get_embedding_config()
    lines = [
        "# Graph Answer Rerank Smoke 最新报告",
        "",
        f"- 生成时间：{datetime.now().isoformat(timespec='seconds')}",
        f"- 模型路径：{cfg['embedding_model_name'] or '<EMPTY>'}",
        "- 说明：本报告只评估 graph_answers 的 embedding 辅助排序，不评估最终答案。",
        "- 边界：reranker 不新增、不删除、不验证 graph_answers；`is_final_answer=false`。",
        "",
        "| case | query | input | ranked | display | display order | display top | embedding top |",
        "|---|---|---:|---:|---:|---|---|---|",
    ]
    for row in records:
        lines.append(
            "| {id} | {query} | {input_count} | {ranked_count} | {display_count} | {display_order} | {display_top} | {top_answer} |".format(
                id=row.get("id", ""),
                query=str(row.get("query", "")).replace("|", "\\|"),
                input_count=row.get("input_count", 0),
                ranked_count=row.get("ranked_count", 0),
                display_count=row.get("display_count", 0),
                display_order=row.get("display_order", "-"),
                display_top=str(row.get("display_top_answer", "")).replace("|", "\\|") or "-",
                top_answer=str(row.get("top_answer", "")).replace("|", "\\|") or "-",
            )
        )
    lines.extend(["", "## 排序明细", ""])
    for row in records:
        lines.extend([f"### {row.get('id', '')}", "", f"- 问题：{row.get('query', '')}", f"- 预期观察：{row.get('expect', '')}", ""])
        lines.extend(
            [
                f"- 展示顺序：{row.get('display_order', '-')}",
                f"- 展示原因：{row.get('display_reason', '-')}",
                "",
            ]
        )
        lines.extend(["| embedding rank | original rank | score | answer |", "|---:|---:|---:|---|"])
        for answer in row.get("ranked_answers", []):
            lines.append(
                "| {erank} | {orank} | {score} | {answer} |".format(
                    erank=answer.get("embedding_rank", ""),
                    orank=answer.get("original_rank", ""),
                    score=_fmt_score(answer.get("embedding_score")),
                    answer=str(answer.get("answer_text", "")).replace("|", "\\|"),
                )
            )
        lines.append("")
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
