# -*- coding: utf-8 -*-
"""Pure runtime configuration helpers for V8."""

import os
from typing import Any


__all__ = ["env_flag"]


def env_flag(name: str, default: Any = "1") -> bool:
    """Return True unless an environment flag is explicitly disabled."""
    value = str(os.getenv(name, default)).strip().lower()
    return value not in {"0", "false", "off", "no"}
