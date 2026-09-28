#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LangChain RAG baseline over the unified merged_rag_corpus."""

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

_VECTORSTORE_CACHE: dict[str, Any] = {}
_EMBED_LOCK = Lock()
INDEX_ROOT = ROOT / "experiments" / "baselines" / "indexes" / "langchain_faiss"


def _index_dir(corpus_path: Path) -> Path:
    resolved = corpus_path.resolve()
    stat = resolved.stat()
    key_src = f"{resolved}|{stat.st_size}|{int(stat.st_mtime)}"
    return INDEX_ROOT / hashlib.sha1(key_src.encode("utf-8")).hexdigest()[:16]


def _require_langchain():
    try:
        from langchain_core.documents import Document  # type: ignore
        from langchain_community.vectorstores import FAISS  # type: ignore
        from langchain_core.embeddings import Embeddings  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "LangChain is not installed. Install it before running this external baseline: "
            "pip install langchain langchain-community"
        ) from exc
    return Document, FAISS, Embeddings


def _get_vectorstore(corpus_path: Path, Document: Any, FAISS: Any, embeddings: Any) -> Any:
    cache_key = str(corpus_path.resolve())
    if cache_key not in _VECTORSTORE_CACHE:
        index_dir = _index_dir(corpus_path)
        if (index_dir / "index.faiss").exists() and (index_dir / "index.pkl").exists():
            _VECTORSTORE_CACHE[cache_key] = FAISS.load_local(
                str(index_dir),
                embeddings,
                allow_dangerous_deserialization=True,
            )
        else:
            docs = [
                Document(
                    page_content=str(item.get("text", "")),
                    metadata={"doc_id": item.get("doc_id"), "source_type": item.get("source_type")},
                )
                for item in read_jsonl(corpus_path)
                if str(item.get("text", "")).strip()
            ]
            vectorstore = FAISS.from_documents(docs, embeddings)
            index_dir.mkdir(parents=True, exist_ok=True)
            vectorstore.save_local(str(index_dir))
            _VECTORSTORE_CACHE[cache_key] = vectorstore
    return _VECTORSTORE_CACHE[cache_key]


def answer(question: str, row: dict[str, str] | None = None, corpus_path: Path | None = None, top_k: int = 20, **_: Any) -> dict[str, Any]:
    if corpus_path is None:
        raise ValueError("corpus_path is required")
    Document, FAISS, Embeddings = _require_langchain()

    from embedding_backend import embed_texts

    class LocalBGEEmbeddings(Embeddings):  # type: ignore[misc]
        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            with _EMBED_LOCK:
                return [vec.tolist() for vec in embed_texts(texts)]

        def embed_query(self, text: str) -> list[float]:
            with _EMBED_LOCK:
                return embed_texts([text])[0].tolist()

    vectorstore = _get_vectorstore(corpus_path, Document, FAISS, LocalBGEEmbeddings())
    hits = vectorstore.similarity_search_with_score(question, k=top_k)
    evidence = [
        {
            "rank": idx + 1,
            "score": float(score),
            "text": doc.page_content,
            "metadata": dict(doc.metadata or {}),
        }
        for idx, (doc, score) in enumerate(hits)
    ]
    evidence_text = "\n\n".join(f"[{h['rank']}] {h['text']}" for h in evidence)
    llm = call_chat_llm_with_usage(RAG_SYSTEM, f"问题：{question}\n\nLangChain retrieved context:\n{evidence_text}")
    text = str(llm["text"])
    return {
        "answer": extract_answer_items(text),
        "answer_text": text,
        "evidence": evidence,
        "raw": {"framework": "langchain", "top_k": top_k, "llm_usage": llm["usage"], "llm_model": llm["model"]},
    }
