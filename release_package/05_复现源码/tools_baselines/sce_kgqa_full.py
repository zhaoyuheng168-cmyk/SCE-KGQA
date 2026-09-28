#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from typing import Any

from common_io import ROOT, disable_thinking_for_qwen35, split_items


SCRIPT_DIR = ROOT / "app" / "retrieval_only" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from answer_hybrid_v8_graph_kag_fallback import answer_hybrid_v8  # noqa: E402


FULL_FLAGS = {
    "GTF_ENABLE_V7_FALLBACK": "0",
    "GTF_ENABLE_KAG_FALLBACK": "1",
    "GTF_ENABLE_GENERIC_RELATION_FALLBACK": "1",
    "GTF_ENABLE_REVERSE_RELATION": "1",
    "GTF_ENABLE_V8_KAG_MULTIHOP_PLANNER": "1",
    "GTF_ENABLE_SCOPE_GATE_V2": "1",
    "GTF_ENABLE_SCOPE_LLM_GATE": "1",
    "GTF_ENABLE_REFUSAL_OUTPUT": "1",
    "GTF_ENABLE_LLM_RESPONSE_CACHE": "0",
    "GTF_LLM_RESPONSE_CACHE_DIR": str(ROOT / "app/retrieval_only/results/llm_response_cache"),
    "GTF_ENABLE_EMBEDDING": "1",
    "GTF_ENABLE_EMBEDDING_EVIDENCE": "1",
    "GTF_ENABLE_ENTITY_EMBEDDING_GROUNDING": "1",
    "GTF_ENABLE_TRUE_ENTITY_GROUNDING": "1",
    "GTF_ENABLE_EMBEDDING_ENTITY_CANDIDATES": "1",
    "GTF_ENABLE_EMBEDDING_RELATION_FALLBACK": "1",
    "GTF_ENABLE_EMBEDDING_ANSWER_RERANK": "1",
    "GTF_EMBEDDING_MODEL_NAME": os.getenv("GTF_EMBEDDING_MODEL_NAME", "runtime_data/models/bge-small-zh-v1.5"),
    "TRANSFORMERS_OFFLINE": "1",
    "TOKENIZERS_PARALLELISM": "false",
}


@contextmanager
def capture_llm_usage():
    """Capture OpenAI-compatible token usage for V8 calls without editing V8."""
    import requests

    original_post = requests.post
    usage = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }
    models: dict[str, int] = {}
    call_count = 0

    def wrapped_post(*args: Any, **kwargs: Any):
        nonlocal call_count
        payload = kwargs.get("json")
        if isinstance(payload, dict):
            kwargs["json"] = disable_thinking_for_qwen35(payload)
        response = original_post(*args, **kwargs)
        payload = kwargs.get("json") or {}
        model = str(payload.get("model") or "")
        try:
            data = response.json()
        except Exception:
            data = {}
        response_usage = data.get("usage") if isinstance(data, dict) else {}
        if response_usage:
            call_count += 1
            usage["prompt_tokens"] += int(response_usage.get("prompt_tokens") or 0)
            usage["completion_tokens"] += int(response_usage.get("completion_tokens") or 0)
            usage["total_tokens"] += int(response_usage.get("total_tokens") or 0)
            if model:
                models[model] = models.get(model, 0) + 1
        return response

    requests.post = wrapped_post
    try:
        yield usage, models, lambda: call_count
    finally:
        requests.post = original_post


def answer(question: str, row: dict[str, str] | None = None, **_: Any) -> dict[str, Any]:
    for key, value in FULL_FLAGS.items():
        os.environ[key] = value
    with capture_llm_usage() as (llm_usage, llm_models, get_llm_call_count):
        result = answer_hybrid_v8(question)
    answer_text = str(result.get("answer") or "")
    answer_items = split_items(result.get("graph_answers") or result.get("kag_answers") or "")
    if not answer_items and answer_text:
        answer_items = split_items(answer_text)
    result["llm_usage"] = llm_usage
    result["llm_call_count"] = get_llm_call_count()
    result["llm_models"] = llm_models
    result["route_observation"] = {
        "route": result.get("route", ""),
        "final_route": result.get("final_route", ""),
        "answer_source": result.get("answer_source", ""),
        "kag_used": bool(result.get("kag_used")),
        "intent_source": result.get("intent_source", ""),
    }
    return {
        "answer": answer_items,
        "answer_text": answer_text,
        "evidence": result.get("kag_evidence", ""),
        "raw": result,
    }
