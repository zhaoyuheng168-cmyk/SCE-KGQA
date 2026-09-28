# -*- coding: utf-8 -*-
"""Runtime adapter registry kept outside the shared KGQA core."""

from __future__ import annotations

from typing import Dict, Type

from ..core import DomainAdapter
from .gansu_finance import GansuFinanceAdapter
from .metaqa import MetaQAAdapter
from .metaqa_real import MetaQARealAdapter


ADAPTERS: Dict[str, Type[DomainAdapter]] = {
    GansuFinanceAdapter.name: GansuFinanceAdapter,
    MetaQAAdapter.name: MetaQAAdapter,
    MetaQARealAdapter.name: MetaQARealAdapter,
}


def adapter_names():
    return sorted(ADAPTERS)


def get_adapter(name: str) -> DomainAdapter:
    key = str(name or "").strip()
    if key not in ADAPTERS:
        raise KeyError(f"Unknown adapter: {key}")
    return ADAPTERS[key]()
