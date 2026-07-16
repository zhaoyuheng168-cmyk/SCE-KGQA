# -*- coding: utf-8 -*-
"""Pure configuration helpers for the embedding experiment branch."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict


PROJECT_ROOT = Path(__file__).resolve().parents[4]


def _env_flag(name: str, default: str = "0") -> bool:
    value = str(os.getenv(name, default)).strip().lower()
    return value not in {"", "0", "false", "off", "no"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(str(os.getenv(name, str(default))).strip())
    except Exception:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(str(os.getenv(name, str(default))).strip())
    except Exception:
        return default


def _env_path(name: str, default: str) -> str:
    raw = str(os.getenv(name, default)).strip() or default
    path = Path(raw)
    if path.is_absolute():
        return str(path)
    return str(PROJECT_ROOT / path)


def get_embedding_config() -> Dict[str, Any]:
    """Return embedding config without side effects.

    Importing or calling this function never loads a model, reads an index,
    connects to Neo4j, or changes V8/V7 behavior.
    """

    return {
        "enable_embedding": _env_flag("GTF_ENABLE_EMBEDDING", "0"),
        "enable_embedding_evidence": _env_flag("GTF_ENABLE_EMBEDDING_EVIDENCE", "0"),
        "enable_entity_embedding_grounding": _env_flag(
            "GTF_ENABLE_ENTITY_EMBEDDING_GROUNDING", "0"
        ),
        "enable_embedding_entity_candidates": _env_flag(
            "GTF_ENABLE_EMBEDDING_ENTITY_CANDIDATES",
            os.getenv("GTF_ENABLE_ENTITY_EMBEDDING_GROUNDING", "0"),
        ),
        "enable_embedding_relation_fallback": _env_flag(
            "GTF_ENABLE_EMBEDDING_RELATION_FALLBACK", "0"
        ),
        "enable_embedding_answer_rerank": _env_flag(
            "GTF_ENABLE_EMBEDDING_ANSWER_RERANK", "0"
        ),
        "evidence_top_k": _env_int("GTF_EMBEDDING_EVIDENCE_TOP_K", 5),
        "evidence_min_score": _env_float("GTF_EMBEDDING_EVIDENCE_MIN_SCORE", 0.65),
        "entity_top_k": _env_int("GTF_ENTITY_EMBEDDING_TOP_K", 10),
        "entity_min_score": _env_float("GTF_ENTITY_EMBEDDING_MIN_SCORE", 0.70),
        "evidence_index_dir": _env_path(
            "GTF_EVIDENCE_EMBEDDING_INDEX_DIR",
            "app/retrieval_only/embedding_indexes/evidence_chunks",
        ),
        "entity_index_dir": _env_path(
            "GTF_ENTITY_EMBEDDING_INDEX_DIR",
            "app/retrieval_only/embedding_indexes/entity_names",
        ),
        "relation_index_dir": _env_path(
            "GTF_RELATION_EMBEDDING_INDEX_DIR",
            "app/retrieval_only/embedding_indexes/relation_schema",
        ),
        "relation_min_score": _env_float("GTF_RELATION_EMBEDDING_MIN_SCORE", 0.45),
        "relation_top_k": _env_int("GTF_RELATION_EMBEDDING_TOP_K", 5),
        "embedding_backend": str(
            os.getenv("GTF_EMBEDDING_BACKEND", "sentence_transformers")
        ).strip(),
        "embedding_model_name": str(os.getenv("GTF_EMBEDDING_MODEL_NAME", "")).strip(),
        "embedding_batch_size": _env_int("GTF_EMBEDDING_BATCH_SIZE", 32),
        "kag_config_path": str(os.getenv("GTF_KAG_CONFIG_PATH", "")).strip(),
    }


__all__ = ["PROJECT_ROOT", "get_embedding_config"]
