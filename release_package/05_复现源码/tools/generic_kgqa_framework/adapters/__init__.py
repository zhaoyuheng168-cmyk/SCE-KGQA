# -*- coding: utf-8 -*-
"""Domain adapters for the KGQA framework prototype."""

from .gansu_finance import GansuFinanceAdapter
from .metaqa import MetaQAAdapter
from .metaqa_real import MetaQARealAdapter
from .registry import adapter_names, get_adapter

__all__ = [
    "GansuFinanceAdapter",
    "MetaQAAdapter",
    "MetaQARealAdapter",
    "adapter_names",
    "get_adapter",
]
