#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reuse the existing OpenSPG/KAG runtime as an external baseline.

This wrapper does not build/import OpenSPG data and does not call SCE-KGQA
runtime APIs. It only calls the existing KAG solver against an already-running
OpenSPG project, then returns answers in the common baseline JSONL schema.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any

from common_io import extract_answer_items


ROOT = Path(__file__).resolve().parents[2]
KAG_ROOT = Path(os.getenv("GTF_OPENS_PG_KAG_ROOT", "/root/work/kag"))
KAG_EXAMPLE = KAG_ROOT / "examples" / "GansuTechFinanceDevV1Enhance"
DEFAULT_CONFIG = ROOT / "experiments" / "baselines" / "openspg_kag" / "runtime_reuse" / "kag_config.yaml"

# Add the parent so `import kag` resolves to /root/work/kag, but do not add
# KAG_ROOT itself: it contains a top-level `mcp/` package that shadows the
# third-party MCP package expected by KAG.
for path in [KAG_ROOT.parent, KAG_EXAMPLE]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def _require_reuse_env() -> None:
    if not KAG_ROOT.exists():
        raise RuntimeError(f"KAG root not found: {KAG_ROOT}")
    if not KAG_EXAMPLE.exists():
        raise RuntimeError(f"KAG GansuTechFinance example not found: {KAG_EXAMPLE}")
    if not DEFAULT_CONFIG.exists():
        raise RuntimeError(f"OpenSPG-KAG reuse config not found: {DEFAULT_CONFIG}")


def _bridge_llm_env() -> None:
    if os.getenv("DASHSCOPE_API_KEY") and not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = str(os.getenv("DASHSCOPE_API_KEY"))
    if os.getenv("DASHSCOPE_BASE_URL") and not os.getenv("OPENAI_BASE_URL"):
        os.environ["OPENAI_BASE_URL"] = str(os.getenv("DASHSCOPE_BASE_URL"))
    if os.getenv("DASHSCOPE_MODEL") and not os.getenv("OPENAI_MODEL"):
        os.environ["OPENAI_MODEL"] = str(os.getenv("DASHSCOPE_MODEL"))


def answer(question: str, row: dict[str, str] | None = None, **_: Any) -> dict[str, Any]:
    _require_reuse_env()
    _bridge_llm_env()

    from kag.common.conf import init_env  # type: ignore
    from solver.qa import GansuTechFinanceDevV1EnhanceDemo  # type: ignore

    init_env(str(DEFAULT_CONFIG))
    demo = GansuTechFinanceDevV1EnhanceDemo()
    answer_text = asyncio.run(demo.qa(question))
    return {
        "answer": extract_answer_items(answer_text),
        "answer_text": answer_text,
        "evidence": [],
        "raw": {
            "framework": "OpenSPG-KAG",
            "mode": "reuse_existing_runtime",
            "kag_root": str(KAG_ROOT),
            "config": str(DEFAULT_CONFIG),
        },
    }
