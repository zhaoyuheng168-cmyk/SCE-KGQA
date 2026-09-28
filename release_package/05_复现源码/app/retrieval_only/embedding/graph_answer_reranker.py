# -*- coding: utf-8 -*-
"""Embedding reranker for KG-confirmed graph answers.

The reranker never creates or removes answers. It only adds embedding scores
and an auxiliary display order for graph_answers that already came from the
controlled KGQA pipeline.
"""

from __future__ import annotations

import argparse
import json
from typing import Any, Dict, Iterable, List, Optional

import numpy as np

from embedding_backend import EmbeddingUnavailable, embed_texts, warn
from embedding_config import get_embedding_config


def _answer_to_text(answer: Any) -> str:
    if isinstance(answer, str):
        return answer.strip()
    if isinstance(answer, dict):
        preferred_keys = (
            "name",
            "answer",
            "value",
            "text",
            "entity",
            "label",
            "title",
            "type",
            "entity_type",
            "relation",
            "subject",
            "object",
            "industry",
            "product",
            "policy",
            "context",
            "evidence_hint",
        )
        parts = [str(answer.get(key, "")).strip() for key in preferred_keys if answer.get(key)]
        if parts:
            return "；".join(parts)
        return json.dumps(answer, ensure_ascii=False, sort_keys=True)
    return str(answer or "").strip()


def _build_answer_embedding_text(answer_text: str, context: str = "") -> str:
    context = str(context or "").strip()
    if context:
        return f"{answer_text}；上下文：{context}"
    return answer_text


def rerank_graph_answers(
    query: str,
    graph_answers: Iterable[Any],
    context: str = "",
    top_n: Optional[int] = None,
    display_strategy: str = "conservative",
    min_top_score: float = 0.45,
    min_score_gap: float = 0.05,
) -> Dict[str, object]:
    """Return graph answers with auxiliary embedding scores.

    `top_n` only controls the optional `display_answers` slice. The full
    `ranked_answers` list always contains every input answer.
    """

    cfg = get_embedding_config()
    answers = list(graph_answers or [])
    base = {
        "enabled": bool(cfg["enable_embedding"] and cfg["enable_embedding_answer_rerank"]),
        "used_as_assist": False,
        "is_final_answer": False,
        "answer_policy": "embedding_rerank_only_does_not_add_remove_or_validate_graph_answers",
        "query": query,
        "input_count": len(answers),
        "ranked_answers": [],
        "display_answers": [],
    }
    if not cfg["enable_embedding"] or not cfg["enable_embedding_answer_rerank"]:
        base["reason"] = "embedding_answer_rerank_disabled"
        base["ranked_answers"] = [
            {
                "original_rank": idx + 1,
                "embedding_rank": idx + 1,
                "embedding_score": None,
                "answer_text": _answer_to_text(answer),
                "answer": answer,
            }
            for idx, answer in enumerate(answers)
        ]
        base["display_answers"] = base["ranked_answers"][: top_n or len(answers)]
        return base
    if not answers:
        base["reason"] = "empty_graph_answers"
        return base

    answer_texts = [_answer_to_text(answer) for answer in answers]
    embedding_texts = [_build_answer_embedding_text(text, context) for text in answer_texts]
    try:
        vectors = embed_texts([query] + embedding_texts)
    except EmbeddingUnavailable as exc:
        warn(str(exc))
        base["reason"] = str(exc)
        return base
    except Exception as exc:
        warn(f"graph answer rerank failed: {exc}")
        base["reason"] = f"graph_answer_rerank_failed: {exc}"
        return base

    query_vec = vectors[0]
    answer_vecs = vectors[1:]
    scores = np.asarray(answer_vecs @ query_vec, dtype="float32").tolist()
    rows = []
    for idx, (answer, answer_text, score) in enumerate(zip(answers, answer_texts, scores)):
        rows.append(
            {
                "original_rank": idx + 1,
                "embedding_score": float(score),
                "answer_text": answer_text,
                "answer": answer,
            }
        )
    rows.sort(key=lambda row: (-float(row["embedding_score"]), int(row["original_rank"])))
    for idx, row in enumerate(rows):
        row["embedding_rank"] = idx + 1

    display_limit = top_n if top_n is not None else len(rows)
    use_embedding_display = True
    display_reason = "embedding_rank"
    if display_strategy == "original":
        use_embedding_display = False
        display_reason = "forced_original_order"
    elif display_strategy == "embedding":
        display_reason = "forced_embedding_order"
    elif display_strategy == "conservative":
        top_score = float(rows[0]["embedding_score"]) if rows else 0.0
        original_top_rank = min(rows, key=lambda row: int(row["original_rank"]))
        original_top_score = float(original_top_rank["embedding_score"])
        if top_score < min_top_score:
            use_embedding_display = False
            display_reason = f"top_score_below_threshold:{top_score:.4f}<{min_top_score:.4f}"
        elif int(rows[0]["original_rank"]) != 1 and top_score - original_top_score < min_score_gap:
            use_embedding_display = False
            display_reason = (
                f"score_gap_below_threshold:{top_score - original_top_score:.4f}<{min_score_gap:.4f}"
            )
    display_source = rows if use_embedding_display else sorted(rows, key=lambda row: int(row["original_rank"]))
    return {
        **base,
        "used_as_assist": True,
        "context": context,
        "display_strategy": display_strategy,
        "display_order": "embedding_rank" if use_embedding_display else "original_rank",
        "display_reason": display_reason,
        "ranked_answers": rows,
        "display_answers": display_source[: max(0, int(display_limit))],
        "notes": [
            "本模块只对 KG/V8 已返回的 graph_answers 做辅助排序。",
            "它不新增、不删除、不验证答案，最终答案集合仍以 graph_answers 为准。",
        ],
    }


def _parse_graph_answers(values: Optional[List[str]]) -> List[Any]:
    if not values:
        return []
    if len(values) == 1:
        raw = values[0].strip()
        if raw.startswith("["):
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return parsed
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    parser.add_argument("--graph-answer", action="append", default=None)
    parser.add_argument("--context", default="")
    parser.add_argument("--top-n", type=int, default=None)
    parser.add_argument("--display-strategy", choices=["conservative", "embedding", "original"], default="conservative")
    parser.add_argument("--min-top-score", type=float, default=0.45)
    parser.add_argument("--min-score-gap", type=float, default=0.05)
    args = parser.parse_args()
    result = rerank_graph_answers(
        args.query,
        _parse_graph_answers(args.graph_answer),
        context=args.context,
        top_n=args.top_n,
        display_strategy=args.display_strategy,
        min_top_score=args.min_top_score,
        min_score_gap=args.min_score_gap,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
