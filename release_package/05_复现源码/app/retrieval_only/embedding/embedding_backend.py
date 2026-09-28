# -*- coding: utf-8 -*-
"""Embedding model and vector-index helpers.

The retrieval path must fail closed: if a dependency, model, or index is
missing, callers get a clear warning/exception in CLI mode and an empty result
in safe retrieval mode.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List

import numpy as np
import requests

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - optional runtime dependency
    yaml = None

from embedding_config import PROJECT_ROOT, get_embedding_config


class EmbeddingUnavailable(RuntimeError):
    """Raised when the configured embedding backend cannot be used."""


def warn(message: str) -> None:
    print(f"[embedding warning] {message}", file=sys.stderr)


def normalize_vectors(vectors: np.ndarray) -> np.ndarray:
    arr = np.asarray(vectors, dtype="float32")
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return arr / norms


def iter_json_dicts(value: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from iter_json_dicts(item)
    elif isinstance(value, list):
        for item in value:
            yield from iter_json_dicts(item)


def _candidate_config_paths() -> List[Path]:
    cfg = get_embedding_config()
    paths = []
    if cfg.get("kag_config_path"):
        paths.append(Path(str(cfg["kag_config_path"])))
    paths.extend(
        [
            PROJECT_ROOT / "app" / "kag_config.yaml",
            PROJECT_ROOT / "kag_config.yaml",
        ]
    )
    return paths


def _load_openai_compatible_embedding_cfg() -> Dict[str, Any]:
    if yaml is None:
        raise EmbeddingUnavailable("PyYAML is not available; cannot read kag_config.yaml")
    for path in _candidate_config_paths():
        if not path.exists():
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for item in iter_json_dicts(data):
            api_key = item.get("api_key") or os.getenv("DASHSCOPE_API_KEY")
            base_url = item.get("base_url")
            model = item.get("model") or item.get("name")
            model_text = str(model or "").lower()
            if api_key and base_url and model and (
                "embedding" in model_text or item.get("vector_dimensions")
            ):
                return {
                    "api_key": str(api_key),
                    "base_url": str(base_url).rstrip("/"),
                    "model": str(model),
                    "cfg_path": str(path),
                }
    raise EmbeddingUnavailable("Cannot find an embedding model config in kag_config.yaml")


def embed_texts(texts: List[str]) -> np.ndarray:
    """Embed texts with the configured backend and return normalized vectors."""

    cfg = get_embedding_config()
    backend = str(cfg.get("embedding_backend") or "sentence_transformers").lower()
    model_name = str(cfg.get("embedding_model_name") or "").strip()
    clean_texts = [str(text or "").strip() for text in texts]
    if not clean_texts:
        return np.zeros((0, 0), dtype="float32")

    if backend in {"sentence_transformers", "sentence-transformers"}:
        if not model_name:
            raise EmbeddingUnavailable(
                "GTF_EMBEDDING_MODEL_NAME is empty for sentence_transformers backend"
            )
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except Exception as exc:
            raise EmbeddingUnavailable(
                "sentence_transformers is not installed; install it or use an "
                "openai_compatible embedding backend"
            ) from exc
        model = SentenceTransformer(model_name)
        vectors = model.encode(
            clean_texts,
            batch_size=int(cfg.get("embedding_batch_size") or 32),
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return normalize_vectors(np.asarray(vectors, dtype="float32"))

    if backend in {"openai_compatible", "dashscope", "http"}:
        emb_cfg = _load_openai_compatible_embedding_cfg()
        url = emb_cfg["base_url"] + "/embeddings"
        headers = {
            "Authorization": f"Bearer {emb_cfg['api_key']}",
            "Content-Type": "application/json",
        }
        vectors = []
        for text in clean_texts:
            payload = {"model": emb_cfg["model"], "input": text}
            response = requests.post(url, headers=headers, json=payload, timeout=90)
            if response.status_code >= 400:
                raise EmbeddingUnavailable(
                    f"embedding HTTP {response.status_code}: {response.text[:300]}"
                )
            data = response.json()
            vectors.append(data["data"][0]["embedding"])
        return normalize_vectors(np.asarray(vectors, dtype="float32"))

    raise EmbeddingUnavailable(f"Unsupported embedding backend: {backend}")


def require_faiss():
    try:
        import faiss  # type: ignore
    except Exception as exc:
        raise EmbeddingUnavailable(
            "faiss is not installed; cannot build/read FAISS index"
        ) from exc
    return faiss


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> int:
    count = 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def build_faiss_index(vectors: np.ndarray, output_path: Path) -> None:
    faiss = require_faiss()
    normalized = normalize_vectors(vectors)
    if normalized.size == 0:
        raise EmbeddingUnavailable("no vectors to index")
    index = faiss.IndexFlatIP(normalized.shape[1])
    index.add(normalized)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(output_path))


def search_faiss_index(index_path: Path, query_vector: np.ndarray, top_k: int):
    faiss = require_faiss()
    index = faiss.read_index(str(index_path))
    q = normalize_vectors(query_vector)
    scores, indices = index.search(q.astype("float32"), int(top_k))
    return scores[0].tolist(), indices[0].tolist()


__all__ = [
    "EmbeddingUnavailable",
    "build_faiss_index",
    "embed_texts",
    "read_jsonl",
    "search_faiss_index",
    "warn",
    "write_jsonl",
]

