#!/usr/bin/env python3
"""Patch a generated Microsoft GraphRAG settings file for DashScope."""

from __future__ import annotations

import argparse
import shutil
import time
from pathlib import Path
from typing import Any

import yaml


ENTITY_TYPES = [
    "policy",
    "government_agency",
    "financial_institution",
    "financial_product",
    "enterprise",
    "region",
    "industry",
    "qualification_feature",
    "service_platform",
    "loan_event",
    "subsidy_event",
]


def model_config(data: dict[str, Any], name: str) -> dict[str, Any]:
    models = data.setdefault("models", {})
    model = models.setdefault(name, {})
    model["model_provider"] = "openai"
    model["auth_type"] = "api_key"
    model["api_key"] = "${DASHSCOPE_API_KEY}"
    model["api_base"] = "${DASHSCOPE_BASE_URL}"
    model["concurrent_requests"] = 2
    model["max_retries"] = 3
    return model


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()
    settings = args.workspace / "settings.yaml"
    if not settings.exists():
        raise SystemExit(f"settings.yaml does not exist: {settings}")

    backup = settings.with_name(f"settings.yaml.bak_{time.strftime('%Y%m%d_%H%M%S')}")
    shutil.copy2(settings, backup)
    data = yaml.safe_load(settings.read_text(encoding="utf-8")) or {}

    chat = model_config(data, "default_chat_model")
    chat["type"] = "chat"
    chat["model"] = "qwen-plus"
    chat["model_supports_json"] = True

    embedding = model_config(data, "default_embedding_model")
    embedding["type"] = "embedding"
    embedding["model"] = "text-embedding-v3"

    extract_graph = data.setdefault("extract_graph", {})
    extract_graph["entity_types"] = ENTITY_TYPES

    settings.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(f"settings={settings}")
    print(f"backup={backup}")


if __name__ == "__main__":
    main()
