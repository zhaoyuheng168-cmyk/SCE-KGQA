# -*- coding: utf-8 -*-
"""Safe retrieval APIs for evidence chunks and entity candidates."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Dict, List, Optional

from embedding_backend import (
    EmbeddingUnavailable,
    embed_texts,
    read_jsonl,
    search_faiss_index,
    warn,
)
from embedding_config import get_embedding_config


def _safe_search(index_dir: str, query: str, top_k: int):
    index_path = Path(index_dir) / "faiss.index"
    metadata_path = Path(index_dir) / "metadata.jsonl"
    if not index_path.exists() or not metadata_path.exists():
        warn(f"index files not found under {index_dir}")
        return [], []
    query_vector = embed_texts([query])
    scores, indices = search_faiss_index(index_path, query_vector, top_k)
    metadata = read_jsonl(metadata_path)
    return list(zip(scores, indices)), metadata


def _make_evidence_result(row: Dict[str, object], score: float, rank: int, matched_filter: bool = False) -> Dict[str, object]:
    return {
        "rank": rank,
        "score": float(score),
        "chunk_id": row.get("chunk_id", ""),
        "text": row.get("text", ""),
        "source_path": row.get("source_path", ""),
        "matched_filter": matched_filter,
        "metadata": row,
    }


def _normalize_filters(values: Optional[List[str]]) -> List[str]:
    return [str(item or "").strip() for item in (values or []) if str(item or "").strip()]


def _extract_declared_relations(row: Dict[str, object]) -> List[str]:
    text = str(row.get("text", ""))
    relations: List[str] = []
    for raw in re.findall(r"包含关系：([^\s。；;]+)", text):
        for item in re.split(r"[,，、/]+", raw):
            item = item.strip()
            if item:
                relations.append(item)
    return relations


def _extract_entity_anchors(row: Dict[str, object]) -> List[str]:
    text = str(row.get("text", ""))
    anchors: List[str] = []
    for match in re.findall(r"实体名称：(.+?)\s+实体类型", text):
        if match.strip():
            anchors.append(match.strip())
    for match in re.findall(r"事实\d+：(.+?)(?=\s+事实\d+：|\s+关系证据汇总：|\s+来源链接：|\s+导入批次：|$)", text):
        if match.strip():
            anchors.append(match.strip())
    for match in re.findall(r"事实三元组：(.+?)(?=\s+主体标签：|\s+客体标签：|\s+审计状态：|$)", text):
        if match.strip():
            anchors.append(match.strip())
    for match in re.findall(r"Structured Fact\s+(.+?)(?=\s+## Evidence Text|\s+## Fact Basis|$)", text):
        if match.strip():
            anchors.append(match.strip())
    for item in row.get("entity_mentions", []) or []:
        if str(item).strip():
            anchors.append(str(item).strip())
    anchors.extend(
        [
            str(row.get("source_path", "")),
            str(row.get("source_name", "")),
        ]
    )
    return anchors


def _matches_entity_filter(row: Dict[str, object], filters: List[str]) -> bool:
    if not filters:
        return True
    haystack = " ".join(_extract_entity_anchors(row))
    return any(item and item in haystack for item in filters)


def _matches_relation_filter(row: Dict[str, object], filters: List[str]) -> bool:
    if not filters:
        return True
    declared = set(_extract_declared_relations(row))
    if declared and any(item in declared for item in filters):
        return True
    haystack = " ".join(
        [
            str(row.get("text", "")),
            str(row.get("source_path", "")),
            str(row.get("source_name", "")),
        ]
    )
    return any(item and item in haystack for item in filters)


def retrieve_evidence(
    query: str,
    top_k: int = 5,
    min_score: float = 0.65,
    entity_filter: Optional[List[str]] = None,
    source_relation_filter: Optional[List[str]] = None,
    strict_entity_filter: bool = False,
    candidate_multiplier: int = 500,
) -> List[Dict[str, object]]:
    cfg = get_embedding_config()
    if not cfg["enable_embedding"] or not cfg["enable_embedding_evidence"]:
        return []
    entity_filters = _normalize_filters(entity_filter)
    relation_filters = _normalize_filters(source_relation_filter)
    search_top_k = top_k
    if entity_filters or relation_filters:
        search_top_k = max(top_k, top_k * max(1, int(candidate_multiplier)))
    try:
        hits, metadata = _safe_search(str(cfg["evidence_index_dir"]), query, search_top_k)
    except EmbeddingUnavailable as exc:
        warn(str(exc))
        return []
    except Exception as exc:
        warn(f"evidence retrieval failed: {exc}")
        return []
    candidates: List[tuple[float, Dict[str, object], bool]] = []
    for score, idx in hits:
        if idx < 0 or idx >= len(metadata) or float(score) < min_score:
            continue
        row = metadata[idx]
        matched_entity = _matches_entity_filter(row, entity_filters)
        matched_relation = _matches_relation_filter(row, relation_filters)
        candidates.append((float(score), row, matched_entity and matched_relation))

    if not entity_filters and not relation_filters:
        return [
            _make_evidence_result(row, score, rank=i + 1)
            for i, (score, row, _) in enumerate(candidates[:top_k])
        ]

    filtered = [(score, row, matched) for score, row, matched in candidates if matched]
    if strict_entity_filter:
        selected = filtered[:top_k]
        return [
            _make_evidence_result(row, score, rank=i + 1, matched_filter=True)
            for i, (score, row, _) in enumerate(selected)
        ]
    remainder = [(score, row, matched) for score, row, matched in candidates if not matched]
    selected = (filtered + remainder)[:top_k]
    return [
        _make_evidence_result(row, score, rank=i + 1, matched_filter=matched)
        for i, (score, row, matched) in enumerate(selected)
    ]


def retrieve_entities(
    query: str,
    top_k: int = 10,
    min_score: float = 0.70,
    label_filter: Optional[List[str]] = None,
) -> List[Dict[str, object]]:
    cfg = get_embedding_config()
    if not cfg["enable_embedding"] or not cfg["enable_entity_embedding_grounding"]:
        return []
    filters = {str(label).split(".")[-1] for label in (label_filter or [])}
    try:
        hits, metadata = _safe_search(str(cfg["entity_index_dir"]), query, top_k)
    except EmbeddingUnavailable as exc:
        warn(str(exc))
        return []
    except Exception as exc:
        warn(f"entity retrieval failed: {exc}")
        return []
    results: List[Dict[str, object]] = []
    for score, idx in hits:
        if idx < 0 or idx >= len(metadata) or float(score) < min_score:
            continue
        row = metadata[idx]
        labels = [str(label).split(".")[-1] for label in row.get("labels", [])]
        if filters and not any(label in filters for label in labels):
            continue
        results.append(
            {
                "rank": len(results) + 1,
                "score": float(score),
                "entity_id": row.get("entity_id", ""),
                "name": row.get("name", ""),
                "labels": labels,
                "metadata": row,
            }
        )
    return results


def retrieve_relations(
    query: str,
    top_k: int = 5,
    min_score: float = 0.58,
    source_type_filter: Optional[List[str]] = None,
    target_type_filter: Optional[List[str]] = None,
) -> List[Dict[str, object]]:
    cfg = get_embedding_config()
    if not cfg["enable_embedding"] or not cfg["enable_embedding_relation_fallback"]:
        return []
    source_filters = {str(item).split(".")[-1] for item in (source_type_filter or []) if str(item).strip()}
    target_filters = {str(item).split(".")[-1] for item in (target_type_filter or []) if str(item).strip()}
    try:
        hits, metadata = _safe_search(str(cfg["relation_index_dir"]), query, top_k)
    except EmbeddingUnavailable as exc:
        warn(str(exc))
        return []
    except Exception as exc:
        warn(f"relation retrieval failed: {exc}")
        return []
    results: List[Dict[str, object]] = []
    for score, idx in hits:
        if idx < 0 or idx >= len(metadata) or float(score) < min_score:
            continue
        row = metadata[idx]
        source_type = str(row.get("source_type", "")).split(".")[-1]
        target_type = str(row.get("target_type", "")).split(".")[-1]
        if source_filters and source_type not in source_filters and target_type not in source_filters:
            continue
        if target_filters and target_type not in target_filters:
            continue
        results.append(
            {
                "rank": len(results) + 1,
                "score": float(score),
                "relation": row.get("relation", ""),
                "source_type": source_type,
                "target_type": target_type,
                "question_type": row.get("question_type", ""),
                "metadata": row,
            }
        )
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["evidence", "entity", "relation"], required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--top-k", type=int, default=None)
    parser.add_argument("--min-score", type=float, default=None)
    parser.add_argument(
        "--entity-filter",
        action="append",
        default=None,
        help="Prefer evidence chunks containing this entity/subject string. Can be repeated.",
    )
    parser.add_argument(
        "--source-relation-filter",
        action="append",
        default=None,
        help="Prefer evidence chunks containing this KG relation name, such as providesProduct. Can be repeated.",
    )
    parser.add_argument(
        "--strict-entity-filter",
        action="store_true",
        help="When filters are provided, return only chunks matching all supplied entity/relation filters.",
    )
    parser.add_argument(
        "--candidate-multiplier",
        type=int,
        default=500,
        help="Search this many times top-k candidates before applying evidence filters.",
    )
    parser.add_argument("--source-type-filter", action="append", default=None)
    parser.add_argument("--target-type-filter", action="append", default=None)
    args = parser.parse_args()
    cfg = get_embedding_config()
    if args.mode == "evidence":
        rows = retrieve_evidence(
            args.query,
            args.top_k or int(cfg["evidence_top_k"]),
            args.min_score if args.min_score is not None else float(cfg["evidence_min_score"]),
            entity_filter=args.entity_filter,
            source_relation_filter=args.source_relation_filter,
            strict_entity_filter=args.strict_entity_filter,
            candidate_multiplier=args.candidate_multiplier,
        )
    elif args.mode == "entity":
        rows = retrieve_entities(
            args.query,
            args.top_k or int(cfg["entity_top_k"]),
            args.min_score if args.min_score is not None else float(cfg["entity_min_score"]),
        )
    else:
        rows = retrieve_relations(
            args.query,
            args.top_k or int(cfg["relation_top_k"]),
            args.min_score if args.min_score is not None else float(cfg["relation_min_score"]),
            source_type_filter=args.source_type_filter,
            target_type_filter=args.target_type_filter,
        )
    for row in rows:
        print(row)


if __name__ == "__main__":
    main()
