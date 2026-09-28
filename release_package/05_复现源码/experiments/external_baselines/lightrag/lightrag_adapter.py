#!/usr/bin/env python3
"""Run the official LightRAG baseline in its isolated virtual environment."""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import re
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "experiments" / "external_baselines"
DEFAULT_DATASET = ROOT / "experiments" / "baselines" / "datasets" / "gtf_kgqa_1300_formal_expanded_gold.csv"
REFUSAL_MARKERS = ("无法", "不能确定", "证据不足", "没有足够")
UNIFIED_ANSWER_POLICY = (
    "请严格遵守最终答案格式：只依据检索到的知识图谱和文档块回答；"
    "可回答时只输出一行“答案：实体1||实体2”，多个答案使用双竖线分隔；"
    "不要输出推理链、Markdown、引用列表或额外说明；"
    "证据不足时只输出“无法从当前可用知识中确定。”"
)


def index_dir(mode: str) -> Path:
    model = re.sub(r"[^A-Za-z0-9_.-]+", "_", os.environ["LIGHTRAG_EMBED_MODEL"])
    dimension = int(os.environ["LIGHTRAG_EMBED_DIM"])
    variant = re.sub(r"[^A-Za-z0-9_.-]+", "_", os.environ.get("LIGHTRAG_CORPUS_VARIANT", "natural"))
    return BASE / "lightrag" / "workspace" / mode / f"index_{variant}_{model}_{dimension}d"


def require_env() -> None:
    required = [
        "DASHSCOPE_API_KEY",
        "DASHSCOPE_BASE_URL",
        "DASHSCOPE_MODEL",
        "LIGHTRAG_EMBED_MODEL",
        "LIGHTRAG_EMBED_DIM",
        "LIGHTRAG_CORPUS_VARIANT",
    ]
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")


def read_dataset(path: Path, limit: int) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as src:
        rows = list(csv.DictReader(src))
    return rows[:limit] if limit > 0 else rows


def extract_answer_items(text: str) -> list[str]:
    cleaned = re.sub(r"^(答案|根据资料|根据上下文|根据提供的信息)[:：]\s*", "", text.strip())
    parts = [item.strip(" \t。；;,，") for item in re.split(r"\|\||[、；;\n]+", cleaned) if item.strip()]
    return parts[:50]


def strip_reference_section(text: str) -> str:
    """Remove framework-added citation sections from the scored answer."""
    return re.split(
        r"\n\s*(?:#{1,6}\s*)?(?:References?|参考(?:文献|资料|来源))\s*:?\s*\n",
        str(text).strip(),
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip()


def read_completed_indexes(output: Path) -> set[int]:
    completed: set[int] = set()
    if not output.exists():
        return completed
    with output.open("r", encoding="utf-8") as src:
        for line in src:
            try:
                item = json.loads(line)
            except (json.JSONDecodeError, TypeError):
                continue
            index = item.get("dataset_index")
            if isinstance(index, int):
                completed.add(index)
    return completed


async def build_rag(mode: str, token_tracker: Any):
    from lightrag import LightRAG
    from lightrag.llm.openai import openai_complete_if_cache, openai_embed
    from lightrag.utils import EmbeddingFunc

    configured_dim = int(os.environ["LIGHTRAG_EMBED_DIM"])

    async def llm(prompt, system_prompt=None, history_messages=None, **kwargs):
        kwargs.pop("token_tracker", None)
        extra_body = dict(kwargs.pop("extra_body", {}) or {})
        extra_body["enable_thinking"] = False
        return await openai_complete_if_cache(
            os.environ["DASHSCOPE_MODEL"],
            prompt,
            system_prompt=system_prompt,
            history_messages=history_messages or [],
            api_key=os.environ["DASHSCOPE_API_KEY"],
            base_url=os.environ["DASHSCOPE_BASE_URL"],
            token_tracker=token_tracker,
            extra_body=extra_body,
            **kwargs,
        )

    async def embed(texts, embedding_dim=None, max_token_size=None, context="document"):
        return await openai_embed.func(
            texts,
            model=os.environ["LIGHTRAG_EMBED_MODEL"],
            api_key=os.environ["DASHSCOPE_API_KEY"],
            base_url=os.environ["DASHSCOPE_BASE_URL"],
            embedding_dim=configured_dim,
            max_token_size=max_token_size,
            context=context,
        )

    probe = await embed(["LightRAG embedding dimension probe"])
    if probe.shape != (1, configured_dim):
        raise RuntimeError(
            f"LightRAG embedding preflight failed: shape={probe.shape}, expected=(1, {configured_dim})"
        )

    rag = LightRAG(
        working_dir=str(index_dir(mode)),
        llm_model_func=llm,
        llm_model_name=os.environ["DASHSCOPE_MODEL"],
        embedding_func=EmbeddingFunc(
            embedding_dim=configured_dim,
            max_token_size=8192,
            func=embed,
        ),
        top_k=int(os.environ.get("LIGHTRAG_TOP_K", "30")),
        chunk_top_k=int(os.environ.get("LIGHTRAG_CHUNK_TOP_K", "20")),
        max_total_tokens=int(os.environ.get("LIGHTRAG_MAX_TOTAL_TOKENS", "16000")),
        llm_model_max_async=int(os.environ.get("LIGHTRAG_LLM_MAX_ASYNC", "2")),
        embedding_func_max_async=int(os.environ.get("LIGHTRAG_EMBED_MAX_ASYNC", "4")),
        enable_llm_cache=os.environ.get("LIGHTRAG_ENABLE_LLM_CACHE", "1") == "1",
    )
    await rag.initialize_storages()
    return rag


def validate_index(mode: str) -> dict[str, Any]:
    workspace = index_dir(mode)
    vector_rows: dict[str, int] = {}
    for namespace in ("chunks", "entities", "relationships"):
        path = workspace / f"vdb_{namespace}.json"
        if not path.exists():
            raise RuntimeError(f"LightRAG index gate failed: missing {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        actual_dim = int(payload.get("embedding_dim") or 0)
        expected_dim = int(os.environ["LIGHTRAG_EMBED_DIM"])
        if actual_dim != expected_dim:
            raise RuntimeError(
                f"LightRAG index gate failed: {namespace} dimension={actual_dim}, expected={expected_dim}"
            )
        vector_rows[namespace] = len(payload.get("data") or [])
        if vector_rows[namespace] == 0:
            raise RuntimeError(f"LightRAG index gate failed: {namespace} vector store is empty")

    status_path = workspace / "kv_store_doc_status.json"
    statuses: dict[str, int] = {}
    duplicate_statuses: dict[str, int] = {}
    if status_path.exists():
        for doc_id, item in json.loads(status_path.read_text(encoding="utf-8")).items():
            status = str(item.get("status") or "unknown")
            target = duplicate_statuses if str(doc_id).startswith("dup-") else statuses
            target[status] = target.get(status, 0) + 1
    bad_statuses = {key: value for key, value in statuses.items() if key != "processed"}
    if bad_statuses:
        raise RuntimeError(f"LightRAG index gate failed: non-processed documents={bad_statuses}")
    return {
        "index_dir": str(workspace),
        "vector_rows": vector_rows,
        "document_statuses": statuses,
        "duplicate_audit_statuses": duplicate_statuses,
    }


async def index_documents(args: argparse.Namespace) -> None:
    from lightrag.utils import TokenTracker

    tracker = TokenTracker()
    rag = await build_rag(args.mode, tracker)
    documents = sorted((BASE / "lightrag" / "workspace" / args.mode / "documents").glob("*.txt"))
    if args.limit > 0:
        documents = documents[: args.limit]
    if not documents:
        raise RuntimeError(f"No documents prepared for LightRAG mode={args.mode}")

    try:
        for start in range(0, len(documents), args.batch_size):
            batch = documents[start : start + args.batch_size]
            texts = [path.read_text(encoding="utf-8") for path in batch]
            await rag.ainsert(texts, file_paths=[str(path) for path in batch])
            print(f"[lightrag-index] {min(start + len(batch), len(documents))}/{len(documents)}", flush=True)
    finally:
        await rag.finalize_storages()

    validation = validate_index(args.mode)
    report = {
        "method": "lightrag",
        "mode": args.mode,
        "documents": len(documents),
        "embedding_model": os.environ["LIGHTRAG_EMBED_MODEL"],
        "embedding_dim": int(os.environ["LIGHTRAG_EMBED_DIM"]),
        "corpus_variant": os.environ["LIGHTRAG_CORPUS_VARIANT"],
        "llm_model": os.environ["DASHSCOPE_MODEL"],
        "llm_usage": tracker.get_usage(),
        "validation": validation,
    }
    report_path = BASE / "results" / f"lightrag_{args.mode}_index_usage.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


async def query_dataset(args: argparse.Namespace) -> None:
    from lightrag import QueryParam
    from lightrag.utils import TokenTracker

    rows = read_dataset(args.dataset, args.limit)
    completed = read_completed_indexes(args.output) if args.resume else set()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if args.resume else "w"

    async def query_one(index: int, row: dict[str, str], rag: Any, tracker: Any) -> dict[str, Any]:
        tracker.reset()
        start = time.time()
        status = "ok"
        error = None
        try:
            raw_answer = str(
                await rag.aquery(
                    row.get("question", ""),
                    param=QueryParam(
                        mode=args.query_mode,
                        top_k=args.top_k,
                        chunk_top_k=args.chunk_top_k,
                        enable_rerank=False,
                        user_prompt=UNIFIED_ANSWER_POLICY if args.answer_policy == "unified" else None,
                    ),
                )
            )
            answer = strip_reference_section(raw_answer)
            if any(marker in answer for marker in REFUSAL_MARKERS):
                status = "refuse"
        except Exception as exc:
            answer = ""
            status = "error"
            error = f"{type(exc).__name__}: {exc}"
        return {
            "qid": row.get("question_id", ""),
            "dataset_index": index,
            "question": row.get("question", ""),
            "method": f"lightrag_{args.answer_policy}",
            "protocol_version": "comparison_protocol_v2_20260607",
            "input_policy": "question_id_and_question_only",
            "answer": extract_answer_items(answer),
            "answer_text": answer,
            "evidence": [],
            "status": status,
            "latency_ms": int((time.time() - start) * 1000),
            "error": error,
            "raw": {
                "query_mode": args.query_mode,
                "answer_policy": args.answer_policy,
                "top_k": args.top_k,
                "chunk_top_k": args.chunk_top_k,
                "workers": args.workers,
                "llm_cache_enabled": os.environ.get("LIGHTRAG_ENABLE_LLM_CACHE", "1") == "1",
                "llm_model": os.environ["DASHSCOPE_MODEL"],
                "llm_usage": tracker.get_usage(),
            },
        }

    pending = [
        (index, row)
        for index, row in enumerate(rows, 1)
        if index not in completed
    ]
    trackers = [TokenTracker() for _ in range(args.workers)]
    rags = [await build_rag(args.mode, tracker) for tracker in trackers]
    try:
        with args.output.open(mode, encoding="utf-8") as dst:
            for start in range(0, len(pending), args.workers):
                batch = pending[start : start + args.workers]
                results = await asyncio.gather(
                    *(
                        query_one(index, row, rags[slot], trackers[slot])
                        for slot, (index, row) in enumerate(batch)
                    )
                )
                for result in sorted(results, key=lambda item: item["dataset_index"]):
                    dst.write(json.dumps(result, ensure_ascii=False) + "\n")
                    dst.flush()
                    print(
                        f"[lightrag] {result['dataset_index']}/{len(rows)} "
                        f"{result['qid']} status={result['status']}",
                        flush=True,
                    )
    finally:
        await asyncio.gather(*(rag.finalize_storages() for rag in rags))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    index_parser = subparsers.add_parser("index")
    index_parser.add_argument("--mode", choices=["smoke", "full"], required=True)
    index_parser.add_argument("--batch-size", type=int, default=10)
    index_parser.add_argument("--limit", type=int, default=0)

    query_parser = subparsers.add_parser("query")
    query_parser.add_argument("--mode", choices=["smoke", "full"], required=True)
    query_parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    query_parser.add_argument("--output", type=Path, required=True)
    query_parser.add_argument("--limit", type=int, default=0)
    query_parser.add_argument("--resume", action="store_true")
    query_parser.add_argument("--query-mode", choices=["local", "global", "hybrid", "mix", "naive"], default="hybrid")
    query_parser.add_argument("--top-k", type=int, default=30)
    query_parser.add_argument("--chunk-top-k", type=int, default=20)
    query_parser.add_argument("--answer-policy", choices=["official", "unified"], default="unified")
    query_parser.add_argument("--workers", type=int, default=1, choices=range(1, 5))
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    require_env()
    if args.command == "index":
        await index_documents(args)
    else:
        await query_dataset(args)


if __name__ == "__main__":
    asyncio.run(main())
