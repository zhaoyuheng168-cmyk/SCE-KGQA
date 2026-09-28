# -*- coding: utf-8 -*-
"""Text-RAG embedding baseline.

This baseline intentionally does not call Neo4j, V8, V7, Type Gate, generic
relation fallback, rule reasoning, or multihop planner.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict

import requests
import yaml

from embedding_config import PROJECT_ROOT, get_embedding_config
from embedding_retriever import retrieve_evidence


def _load_chat_cfg() -> Dict[str, str]:
    candidates = [
        Path(os.getenv("GTF_KAG_CONFIG_PATH", "")) if os.getenv("GTF_KAG_CONFIG_PATH") else None,
        PROJECT_ROOT / "app" / "kag_config.yaml",
        PROJECT_ROOT / "kag_config.yaml",
    ]
    for path in candidates:
        if path and path.exists():
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            cfg = data.get("chat_llm") or {}
            api_key = cfg.get("api_key") or os.getenv("DASHSCOPE_API_KEY") or os.getenv("GTF_REWRITE_API_KEY")
            base_url = cfg.get("base_url")
            model = cfg.get("model")
            if api_key and base_url and model:
                return {"api_key": str(api_key), "base_url": str(base_url).rstrip("/"), "model": str(model)}
    raise RuntimeError("Cannot find chat_llm config for Text-RAG baseline")


def _call_chat_llm(question: str, evidence_text: str) -> str:
    cfg = _load_chat_cfg()
    url = cfg["base_url"] + "/chat/completions"
    headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
    system_prompt = "你是甘肃科技金融 KGQA 的 Text-RAG baseline。只能根据给定 evidence 回答；证据不足时说无法从证据中确定。"
    user_prompt = f"问题：{question}\n\nEvidence:\n{evidence_text}"
    payload = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0,
        "max_tokens": 700,
    }
    response = requests.post(url, headers=headers, json=payload, timeout=90)
    if response.status_code >= 400:
        raise RuntimeError(f"chat_llm HTTP {response.status_code}: {response.text[:300]}")
    return response.json()["choices"][0]["message"]["content"]


def answer_text_rag(question: str) -> Dict[str, Any]:
    cfg = get_embedding_config()
    chunks = retrieve_evidence(
        question,
        top_k=int(cfg["evidence_top_k"]),
        min_score=float(cfg["evidence_min_score"]),
    )
    if not chunks:
        return {
            "question": question,
            "answer": "未检索到可用 evidence，Text-RAG baseline 无法回答。",
            "baseline": "text_rag_embedding",
            "answer_source": "embedding_text_rag_no_evidence",
            "retrieved_chunks": [],
        }
    evidence_text = "\n\n".join(
        f"[{item['rank']}] {item.get('text', '')}" for item in chunks
    )
    answer = _call_chat_llm(question, evidence_text)
    return {
        "question": question,
        "answer": answer,
        "baseline": "text_rag_embedding",
        "answer_source": "embedding_text_rag",
        "retrieved_chunks": chunks,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    args = parser.parse_args()
    print(json.dumps(answer_text_rag(args.query), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

