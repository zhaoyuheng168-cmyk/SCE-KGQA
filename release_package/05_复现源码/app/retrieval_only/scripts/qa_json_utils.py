"""
Pure JSON text parsing helpers for V8 LLM-output adapters.

This module must not import V8 runtime code, Neo4j, LLM clients, filesystem
helpers, or environment configuration. It mirrors the V8 legacy JSON object
extractor exactly.
"""

import json
import re
from typing import Any, Dict

__all__ = ["extract_json_obj"]


def extract_json_obj(text: str) -> Dict[str, Any]:
    text = str(text or "").strip()
    text = re.sub(r"^```json", "", text).strip()
    text = re.sub(r"^```", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    m = re.search(r"\{.*\}", text, flags=re.S)
    if not m:
        raise ValueError("No JSON object found in LLM output")
    return json.loads(m.group(0))
