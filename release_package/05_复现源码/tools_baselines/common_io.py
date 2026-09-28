#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared IO and scoring helpers for comparison baselines."""

from __future__ import annotations

import csv
import json
import os
import re
import time
from pathlib import Path
from typing import Any

import requests
import yaml


ROOT = Path(__file__).resolve().parents[2]
SEP_RE = re.compile(r"\|\||[；;，,\n\r、]+")
PROTOCOL_VERSION = "comparison_protocol_v2_20260607"


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def split_items(value: object) -> list[str]:
    text = "" if value is None else str(value)
    if not text or text.lower() == "nan":
        return []
    out: list[str] = []
    for part in SEP_RE.split(text):
        item = part.strip().strip("。；;，,、 ")
        if item and item.lower() != "nan" and item not in out:
            out.append(item)
    return out


def normalize_text(value: object) -> str:
    text = "" if value is None else str(value)
    text = re.sub(r"\s+", "", text)
    return text.replace("（", "(").replace("）", ")").replace("“", "").replace("”", "")


def now_ms() -> int:
    return int(time.time() * 1000)


def load_chat_cfg() -> dict[str, str]:
    # Formal comparison runs explicitly export these variables. Prefer them
    # over application config so every generative baseline uses the same LLM.
    explicit_api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY")
    explicit_base_url = os.getenv("DASHSCOPE_BASE_URL") or os.getenv("OPENAI_BASE_URL")
    explicit_model = os.getenv("DASHSCOPE_MODEL") or os.getenv("OPENAI_MODEL")
    if explicit_api_key and explicit_base_url and explicit_model:
        return {
            "api_key": explicit_api_key,
            "base_url": explicit_base_url.rstrip("/"),
            "model": explicit_model,
        }
    candidates = [
        Path(os.getenv("GTF_KAG_CONFIG_PATH", "")) if os.getenv("GTF_KAG_CONFIG_PATH") else None,
        ROOT / "app" / "kag_config.yaml",
        ROOT / "kag_config.yaml",
        ROOT.parents[1] / "app" / "kag_config.yaml",
        ROOT.parents[1] / "kag_config.yaml",
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
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("DASHSCOPE_API_KEY") or os.getenv("GTF_REWRITE_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL") or os.getenv("DASHSCOPE_BASE_URL") or os.getenv("GTF_LLM_BASE_URL")
    model = os.getenv("OPENAI_MODEL") or os.getenv("DASHSCOPE_MODEL") or os.getenv("GTF_LLM_MODEL")
    if api_key and base_url and model:
        return {"api_key": api_key, "base_url": base_url.rstrip("/"), "model": model}
    raise RuntimeError("Cannot find chat_llm config")


def disable_thinking_for_qwen35(payload: dict[str, Any]) -> dict[str, Any]:
    """Return an OpenAI-compatible payload with Qwen3.5 thinking disabled."""
    updated = dict(payload)
    model = str(updated.get("model") or "").lower()
    if model.startswith("qwen3.5"):
        updated["enable_thinking"] = False
    return updated


def call_chat_llm_with_usage(system_prompt: str, user_prompt: str, max_tokens: int = 700) -> dict[str, Any]:
    cfg = load_chat_cfg()
    payload = disable_thinking_for_qwen35(
        {
            "model": cfg["model"],
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0,
            "max_tokens": max_tokens,
        }
    )
    response = requests.post(
        cfg["base_url"] + "/chat/completions",
        headers={"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"},
        json=payload,
        timeout=90,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"chat_llm HTTP {response.status_code}: {response.text[:300]}")
    data = response.json()
    usage = data.get("usage") or {}
    return {
        "text": data["choices"][0]["message"]["content"],
        "usage": {
            "prompt_tokens": int(usage.get("prompt_tokens") or 0),
            "completion_tokens": int(usage.get("completion_tokens") or 0),
            "total_tokens": int(usage.get("total_tokens") or 0),
        },
        "model": cfg["model"],
        "protocol_version": PROTOCOL_VERSION,
    }


def call_chat_llm(system_prompt: str, user_prompt: str, max_tokens: int = 700) -> str:
    return str(call_chat_llm_with_usage(system_prompt, user_prompt, max_tokens=max_tokens)["text"])


def extract_answer_items(answer_text: str) -> list[str]:
    text = re.sub(r"^\s*答案[:：]\s*", "", str(answer_text).strip())
    text = re.split(r"\n\s*(?:###\s*)?(?:References|参考资料|参考文献)", text, maxsplit=1, flags=re.I)[0]
    candidates = split_items(text)
    return candidates[:50]
