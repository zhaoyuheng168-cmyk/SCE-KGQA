# -*- coding: utf-8 -*-
"""Lightweight retrieval helpers for BM25/vector baselines."""

from __future__ import annotations

import math
import re
import hashlib
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from common_io import read_jsonl
from common_io import ROOT


TOKEN_RE = re.compile(r"[\u4e00-\u9fff]|[A-Za-z0-9_]+")


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def char_ngrams(text: str, n: int = 2) -> Counter[str]:
    compact = re.sub(r"\s+", "", text.lower())
    return Counter(compact[i : i + n] for i in range(max(0, len(compact) - n + 1)))


class CorpusIndex:
    def __init__(self, corpus_path: Path) -> None:
        self.docs = read_jsonl(corpus_path)
        self.tokens = [tokenize(str(doc.get("text", ""))) for doc in self.docs]
        self.doc_len = [len(toks) or 1 for toks in self.tokens]
        self.avg_len = sum(self.doc_len) / max(1, len(self.doc_len))
        self.df: Counter[str] = Counter()
        self.inverted: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for idx, toks in enumerate(self.tokens):
            counts = Counter(toks)
            for term, tf in counts.items():
                self.df[term] += 1
                self.inverted[term].append((idx, tf))
        self.ngrams = [char_ngrams(str(doc.get("text", ""))) for doc in self.docs]
        self.ngram_norms = [math.sqrt(sum(v * v for v in vec.values())) or 1.0 for vec in self.ngrams]

    def bm25(self, query: str, top_k: int = 20) -> list[dict[str, Any]]:
        q_terms = tokenize(query)
        scores: dict[int, float] = defaultdict(float)
        n_docs = max(1, len(self.docs))
        k1 = 1.5
        b = 0.75
        for term in q_terms:
            postings = self.inverted.get(term, [])
            if not postings:
                continue
            idf = math.log(1 + (n_docs - len(postings) + 0.5) / (len(postings) + 0.5))
            for idx, tf in postings:
                denom = tf + k1 * (1 - b + b * self.doc_len[idx] / self.avg_len)
                scores[idx] += idf * (tf * (k1 + 1) / denom)
        return self._rank(scores, top_k)

    def vector(self, query: str, top_k: int = 20) -> list[dict[str, Any]]:
        q_vec = char_ngrams(query)
        q_norm = math.sqrt(sum(v * v for v in q_vec.values())) or 1.0
        scores: dict[int, float] = {}
        for idx, vec in enumerate(self.ngrams):
            common = set(q_vec) & set(vec)
            if not common:
                continue
            dot = sum(q_vec[k] * vec[k] for k in common)
            scores[idx] = dot / (q_norm * self.ngram_norms[idx])
        return self._rank(scores, top_k)

    def _rank(self, scores: dict[int, float], top_k: int) -> list[dict[str, Any]]:
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        out: list[dict[str, Any]] = []
        for rank, (idx, score) in enumerate(ranked, 1):
            doc = dict(self.docs[idx])
            doc["rank"] = rank
            doc["score"] = score
            out.append(doc)
        return out


class SemanticVectorIndex:
    """Persistent BGE cosine index over the exact corpus passed to a baseline."""

    def __init__(self, corpus_path: Path) -> None:
        import numpy as np

        embedding_dir = ROOT / "app" / "retrieval_only" / "embedding"
        if str(embedding_dir) not in sys.path:
            sys.path.insert(0, str(embedding_dir))
        from embedding_backend import embed_texts, normalize_vectors

        self._fallback_embed_texts = embed_texts
        self._normalize_vectors = normalize_vectors
        self._model = None
        model_name = os.getenv("GTF_EMBEDDING_MODEL_NAME", "runtime_data/models/bge-small-zh-v1.5")
        backend = os.getenv("GTF_EMBEDDING_BACKEND", "sentence_transformers").lower()
        if backend in {"sentence_transformers", "sentence-transformers"}:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(model_name)
        self.docs = read_jsonl(corpus_path)
        stat = corpus_path.resolve().stat()
        fingerprint = hashlib.sha1(
            (
                f"{corpus_path.resolve()}|{stat.st_size}|{int(stat.st_mtime)}|"
                f"{model_name}"
            ).encode("utf-8")
        ).hexdigest()[:16]
        cache = ROOT / "experiments" / "baselines" / "indexes" / "semantic_bge" / f"{fingerprint}.npy"
        cache.parent.mkdir(parents=True, exist_ok=True)
        if cache.exists():
            self.vectors = np.load(cache, mmap_mode="r")
            if len(self.vectors) != len(self.docs):
                raise RuntimeError(f"Semantic index/document mismatch: {cache}")
        else:
            texts = [str(doc.get("text") or "") for doc in self.docs]
            batch_size = int(os.getenv("BASELINE_EMBEDDING_BATCH_SIZE", "64"))
            first = self._encode(texts[:batch_size])
            temp = cache.with_suffix(".tmp.npy")
            vectors = np.lib.format.open_memmap(
                temp,
                mode="w+",
                dtype="float32",
                shape=(len(texts), first.shape[1]),
            )
            vectors[: len(first)] = first
            print(f"[semantic-bge-index] {len(first)}/{len(texts)}", flush=True)
            for start in range(len(first), len(texts), batch_size):
                batch = self._encode(texts[start : start + batch_size])
                vectors[start : start + len(batch)] = batch
                print(f"[semantic-bge-index] {start + len(batch)}/{len(texts)}", flush=True)
            vectors.flush()
            del vectors
            temp.replace(cache)
            self.vectors = np.load(cache, mmap_mode="r")

    def _encode(self, texts: list[str]):
        import numpy as np

        if self._model is not None:
            vectors = self._model.encode(
                texts,
                batch_size=int(os.getenv("BASELINE_EMBEDDING_BATCH_SIZE", "64")),
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            return self._normalize_vectors(np.asarray(vectors, dtype="float32"))
        return self._fallback_embed_texts(texts)

    def search(self, query: str, top_k: int = 20) -> list[dict[str, Any]]:
        import numpy as np

        query_vector = self._encode([query])[0].astype("float32")
        scores = self.vectors @ query_vector
        indexes = np.argsort(scores)[::-1][:top_k]
        out: list[dict[str, Any]] = []
        for rank, index in enumerate(indexes.tolist(), 1):
            doc = dict(self.docs[index])
            doc["rank"] = rank
            doc["score"] = float(scores[index])
            out.append(doc)
        return out
