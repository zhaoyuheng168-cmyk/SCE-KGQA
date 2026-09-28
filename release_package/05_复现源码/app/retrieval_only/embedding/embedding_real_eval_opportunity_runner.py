# -*- coding: utf-8 -*-
"""Analyze real eval rows for embedding mainline opportunity.

This script is read-only with respect to eval data. It does not run V8/V7 and
does not judge final answers. It only samples existing eval/test rows and runs
embedding assist modules to estimate whether entity candidates, relation
fallback candidates, or graph answer rerank may help.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List

from embedding_config import PROJECT_ROOT, get_embedding_config
from embedding_pipeline_proposal import propose_pipeline_assist
from graph_answer_reranker import rerank_graph_answers


DEFAULT_SOURCES = [
    PROJECT_ROOT
    / "app/retrieval_only/tests/results/真实自由问答测试集_v1前1800题冒烟评测结果/真实自由问答测试集_v1前1800题冒烟评测结果.csv",
    PROJECT_ROOT
    / "deliverables/paper_submission_system_20260522_114215/eval_results/stageE8_1200_current/blind1200_v3_stageE8_naturalized_workers12_20260522_114215.csv",
    PROJECT_ROOT / "blind_tests/blind1200_v2/v2_2_diversity_repaired/sealed/blind_test_v2_2_diversity_repaired_1200.csv",
]
DEFAULT_JSONL_OUT = PROJECT_ROOT / "experiment_notes" / "embedding_real_eval_opportunity_30.jsonl"
DEFAULT_MD_OUT = PROJECT_ROOT / "experiment_notes" / "embedding_real_eval_opportunity_30.md"


PATTERNS = {
    "entity_alias_or_shortname": re.compile(r"(科创|政采|护航计划|技改|再贷款|上市贷|e贷|易贷|人才贷)"),
    "relation_paraphrase": re.compile(
        r"(扶持|帮了|服务|面向|覆盖|指向|落在|落到|放款|放过款|贷款给|拿到.*贷款|提供.*产品|谁提供|由哪家|支持啥|提到|归入|关联哪些行业)"
    ),
    "boundary": re.compile(r"(天气|写.*诗|能不能批贷|一定能不能|预测|建议)"),
}


def _read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _gold_items(row: Dict[str, str]) -> List[str]:
    raw = row.get("gold_items_eval") or row.get("gold_items") or row.get("pred_items") or ""
    if not raw:
        return []
    if "||" in raw:
        return [item.strip() for item in raw.split("||") if item.strip()]
    if "|" in raw:
        return [item.strip() for item in raw.split("|") if item.strip()]
    return [raw.strip()] if raw.strip() else []


def _gold_count(row: Dict[str, str]) -> int:
    value = (row.get("gold_count") or "").strip()
    if value.isdigit():
        return int(value)
    return len(_gold_items(row))


def _is_multihop(row: Dict[str, str]) -> bool:
    hop = (row.get("hop_count") or "").strip()
    if hop.isdigit() and int(hop) > 1:
        return True
    path = row.get("relation_path") or ""
    return path.count("->") >= 2 or path.count("-") >= 4


def _passed(row: Dict[str, str]) -> str:
    raw = (row.get("passed") or "").strip().lower()
    if raw in {"1", "true", "y", "yes"}:
        return "pass"
    if raw in {"0", "false", "n", "no"}:
        return "fail"
    return "unknown"


def _classify(row: Dict[str, str]) -> List[str]:
    question = row.get("question", "")
    labels = []
    for name, pattern in PATTERNS.items():
        if pattern.search(question):
            labels.append(name)
    if _gold_count(row) > 1:
        labels.append("rerank_multi_answer")
    if _is_multihop(row):
        labels.append("multihop_path")
    return labels or ["other"]


def _source_name(path: Path) -> str:
    text = str(path)
    if "1800" in text or "自由问答" in text:
        return "freeqa1800_result"
    if "stageE8_1200" in text or "blind1200_v3" in text:
        return "stageE8_1200_result"
    if "blind1200" in text:
        return "blind1200_testset"
    return path.name


def _pick_cases(paths: Iterable[Path], limit: int) -> List[Dict[str, str]]:
    candidates = []
    for path in paths:
        if not path.exists():
            continue
        source = _source_name(path)
        for row in _read_csv(path):
            labels = _classify(row)
            status = _passed(row)
            score = 0
            if status == "fail":
                score += 100
            if "rerank_multi_answer" in labels:
                score += 20
            if "entity_alias_or_shortname" in labels:
                score += 15
            if "relation_paraphrase" in labels:
                score += 15
            if "multihop_path" in labels:
                score += 10
            if "other" in labels:
                score -= 20
            candidates.append(
                {
                    "source": source,
                    "question_id": row.get("question_id") or row.get("row_index") or "",
                    "question": row.get("question", ""),
                    "category": row.get("category", ""),
                    "difficulty": row.get("difficulty", ""),
                    "relation_path": row.get("relation_path", ""),
                    "passed": status,
                    "gold_count": str(_gold_count(row)),
                    "gold_items": "||".join(_gold_items(row)),
                    "opportunity_labels": "||".join(labels),
                    "_score": str(score),
                }
            )
    candidates.sort(key=lambda row: (-int(row["_score"]), row["source"], row["question_id"]))
    selected = []
    seen = set()
    label_counts = Counter()
    for row in candidates:
        key = (row["source"], row["question_id"])
        if key in seen:
            continue
        labels = row["opportunity_labels"].split("||")
        if len(selected) >= limit:
            break
        if any(label_counts[label] < max(3, limit // 6) for label in labels):
            selected.append(row)
            seen.add(key)
            for label in labels:
                label_counts[label] += 1
    for row in candidates:
        if len(selected) >= limit:
            break
        key = (row["source"], row["question_id"])
        if key not in seen:
            selected.append(row)
            seen.add(key)
    for row in selected:
        row.pop("_score", None)
    return selected


def _summarize_pipeline(question: str) -> Dict[str, object]:
    proposal = propose_pipeline_assist(question)
    entity_rows = proposal.get("entity_proposal", {}).get("candidates", [])[:5]
    relation_rows = proposal.get("relation_proposal_after_router_miss", {}).get("relation_candidates", [])
    return {
        "entity_enabled": proposal.get("entity_proposal", {}).get("enabled"),
        "relation_enabled": proposal.get("relation_proposal_after_router_miss", {}).get("enabled"),
        "entity_candidates": [row.get("name", "") for row in entity_rows],
        "relation_candidates": relation_rows,
    }


def _summarize_rerank(question: str, gold_items: List[str]) -> Dict[str, object]:
    if len(gold_items) <= 1:
        return {"eligible": False}
    result = rerank_graph_answers(question, gold_items, top_n=min(5, len(gold_items)))
    display = result.get("display_answers", [])
    return {
        "eligible": True,
        "enabled": result.get("enabled"),
        "display_order": result.get("display_order"),
        "display_reason": result.get("display_reason"),
        "top_display": display[0].get("answer_text", "") if display else "",
        "ranked_count": len(result.get("ranked_answers", [])),
    }


def run(paths: List[Path], limit: int) -> List[Dict[str, object]]:
    rows = _pick_cases(paths, limit)
    records = []
    for row in rows:
        gold_items = [item for item in row.get("gold_items", "").split("||") if item]
        pipeline = _summarize_pipeline(row["question"])
        rerank = _summarize_rerank(row["question"], gold_items)
        possible = []
        if pipeline.get("entity_candidates"):
            possible.append("entity_candidates")
        if pipeline.get("relation_candidates"):
            possible.append("relation_fallback")
        if rerank.get("eligible"):
            possible.append("answer_rerank")
        records.append({**row, "pipeline": pipeline, "rerank": rerank, "embedding_possible_layers": possible})
    return records


def _write_jsonl(path: Path, records: List[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in records:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _fmt(value: object) -> str:
    if not value:
        return "-"
    if isinstance(value, list):
        return "<br>".join(str(item) for item in value) or "-"
    return str(value)


def _write_md(path: Path, records: List[Dict[str, object]]) -> None:
    cfg = get_embedding_config()
    label_counts = Counter()
    layer_counts = Counter()
    for row in records:
        for label in str(row.get("opportunity_labels", "")).split("||"):
            if label:
                label_counts[label] += 1
        for layer in row.get("embedding_possible_layers", []):
            layer_counts[layer] += 1
    lines = [
        "# Embedding 真实评测机会样本 30题报告",
        "",
        f"- 生成时间：{datetime.now().isoformat(timespec='seconds')}",
        f"- 模型路径：{cfg['embedding_model_name'] or '<EMPTY>'}",
        "- 范围：只读已有 1800/1200 CSV，不运行 V8/V7，不评估最终答案。",
        "- 目的：判断主线三能力在真实题目上的潜在帮助层。",
        "",
        "## 机会类型统计",
        "",
        "| label | count |",
        "|---|---:|",
    ]
    for key, value in label_counts.most_common():
        lines.append(f"| {key} | {value} |")
    lines.extend(["", "## Embedding 可能帮助层", "", "| layer | count |", "|---|---:|"])
    for key, value in layer_counts.most_common():
        lines.append(f"| {key} | {value} |")
    lines.extend(["", "## 样本明细", "", "| id | source | passed | labels | question | entity candidates | relation candidates | rerank top | possible layers |", "|---|---|---|---|---|---|---|---|---|"])
    for row in records:
        pipeline = row["pipeline"]
        rerank = row["rerank"]
        lines.append(
            "| {id} | {source} | {passed} | {labels} | {q} | {ents} | {rels} | {top} | {layers} |".format(
                id=row.get("question_id", ""),
                source=row.get("source", ""),
                passed=row.get("passed", ""),
                labels=str(row.get("opportunity_labels", "")).replace("||", "<br>"),
                q=str(row.get("question", "")).replace("|", "\\|"),
                ents=_fmt(pipeline.get("entity_candidates")),
                rels=_fmt(pipeline.get("relation_candidates")),
                top=str(rerank.get("top_display", "-")).replace("|", "\\|"),
                layers=_fmt(row.get("embedding_possible_layers")),
            )
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--source", action="append", default=None)
    parser.add_argument("--jsonl-out", default=str(DEFAULT_JSONL_OUT))
    parser.add_argument("--md-out", default=str(DEFAULT_MD_OUT))
    args = parser.parse_args()
    paths = [Path(item) for item in args.source] if args.source else DEFAULT_SOURCES
    records = run(paths, args.limit)
    _write_jsonl(Path(args.jsonl_out), records)
    _write_md(Path(args.md_out), records)
    print(json.dumps({"cases": len(records), "jsonl_out": args.jsonl_out, "md_out": args.md_out}, ensure_ascii=False))


if __name__ == "__main__":
    main()
