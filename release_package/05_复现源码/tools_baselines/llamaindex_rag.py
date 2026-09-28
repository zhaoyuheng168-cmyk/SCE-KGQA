#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LlamaIndex RAG baseline over the unified merged_rag_corpus.

This wrapper intentionally requires LlamaIndex to be installed. It should not
silently fall back to our homemade retriever, otherwise it would not be an
external-framework baseline.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
from typing import Any
import hashlib
from threading import Lock

from common_io import call_chat_llm_with_usage, extract_answer_items, read_jsonl
from common_prompt import RAG_SYSTEM

ROOT = Path(__file__).resolve().parents[2]
EMBEDDING_DIR = ROOT / "app" / "retrieval_only" / "embedding"
if str(EMBEDDING_DIR) not in sys.path:
    sys.path.insert(0, str(EMBEDDING_DIR))

os.environ.setdefault("GTF_ENABLE_EMBEDDING", "1")
os.environ.setdefault("GTF_EMBEDDING_MODEL_NAME", "runtime_data/models/bge-small-zh-v1.5")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

_INDEX_CACHE: dict[str, Any] = {}
_EMBED_LOCK = Lock()
INDEX_ROOT = ROOT / "experiments" / "baselines" / "indexes" / "llamaindex"


def _index_dir(corpus_path: Path) -> Path:
    resolved = corpus_path.resolve()
    stat = resolved.stat()
    key_src = f"{resolved}|{stat.st_size}|{int(stat.st_mtime)}"
    return INDEX_ROOT / hashlib.sha1(key_src.encode("utf-8")).hexdigest()[:16]


def _require_llamaindex():
    try:
        from llama_index.core import Document, StorageContext, VectorStoreIndex, load_index_from_storage  # type: ignore
        from llama_index.core.embeddings import BaseEmbedding  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "LlamaIndex is not installed. Install it before running this external baseline: "
            "pip install llama-index"
        ) from exc
    return Document, StorageContext, VectorStoreIndex, load_index_from_storage, BaseEmbedding


def _get_index(corpus_path: Path, Document: Any, StorageContext: Any, VectorStoreIndex: Any, load_index_from_storage: Any, embed_model: Any) -> Any:
    cache_key = str(corpus_path.resolve())
    if cache_key not in _INDEX_CACHE:
        index_dir = _index_dir(corpus_path)
        if (index_dir / "docstore.json").exists():
            storage_context = StorageContext.from_defaults(persist_dir=str(index_dir))
            _INDEX_CACHE[cache_key] = load_index_from_storage(storage_context, embed_model=embed_model)
        else:
            docs = [
                Document(text=str(item.get("text", "")), metadata={"doc_id": item.get("doc_id"), "source_type": item.get("source_type")})
                for item in read_jsonl(corpus_path)
                if str(item.get("text", "")).strip()
            ]
            index = VectorStoreIndex.from_documents(docs, embed_model=embed_model)
            index_dir.mkdir(parents=True, exist_ok=True)
            index.storage_context.persist(persist_dir=str(index_dir))
            _INDEX_CACHE[cache_key] = index
    return _INDEX_CACHE[cache_key]


def answer(question: str, row: dict[str, str] | None = None, corpus_path: Path | None = None, top_k: int = 20, **_: Any) -> dict[str, Any]:
    if corpus_path is None:
        raise ValueError("corpus_path is required")
    Document, StorageContext, VectorStoreIndex, load_index_from_storage, BaseEmbedding = _require_llamaindex()

    # Import locally so this module remains importable without embedding deps.
    import numpy as np
    from pydantic import PrivateAttr

    from embedding_backend import embed_texts

    class LocalBGEEmbedding(BaseEmbedding):  # type: ignore[misc]
        _cache: dict[str, list[float]] = PrivateAttr(default_factory=dict)

        @classmethod
        def class_name(cls) -> str:
            return "LocalBGEEmbedding"

        def _get_query_embedding(self, query: str) -> list[float]:
            return self._embed_one(query)

        async def _aget_query_embedding(self, query: str) -> list[float]:
            return self._embed_one(query)

        def _get_text_embedding(self, text: str) -> list[float]:
            return self._embed_one(text)

        def _get_text_embeddings(self, texts: list[str]) -> list[list[float]]:
            with _EMBED_LOCK:
                vecs = embed_texts(texts)
            return [v.astype("float32").tolist() for v in np.asarray(vecs)]

        def _embed_one(self, text: str) -> list[float]:
            if text not in self._cache:
                with _EMBED_LOCK:
                    self._cache[text] = embed_texts([text])[0].astype("float32").tolist()
            return self._cache[text]

    index = _get_index(corpus_path, Document, StorageContext, VectorStoreIndex, load_index_from_storage, LocalBGEEmbedding())
    retriever = index.as_retriever(similarity_top_k=top_k)
    hits = retriever.retrieve(question)
    evidence = [
        {
            "rank": idx + 1,
            "score": float(getattr(hit, "score", 0.0) or 0.0),
            "text": hit.node.get_content(),
            "metadata": dict(hit.node.metadata or {}),
        }
        for idx, hit in enumerate(hits)
    ]
    evidence_text = "\n\n".join(f"[{h['rank']}] {h['text']}" for h in evidence)
    llm = call_chat_llm_with_usage(RAG_SYSTEM, f"问题：{question}\n\nLlamaIndex retrieved context:\n{evidence_text}")
    text = str(llm["text"])
    return {
        "answer": extract_answer_items(text),
        "answer_text": text,
        "evidence": evidence,
        "raw": {"framework": "llamaindex", "top_k": top_k, "llm_usage": llm["usage"], "llm_model": llm["model"]},
    }
