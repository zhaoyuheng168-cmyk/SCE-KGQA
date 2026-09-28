#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Export a baseline-only entity lexicon from frozen runtime KG nodes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from common_io import ROOT


NODES = ROOT / "app/builder/data/runtime/nodes_kag.json"
OUTPUT = ROOT / "experiments/baselines/corpus/entity_lexicon.jsonl"


def aliases_from_properties(properties: dict[str, Any]) -> list[str]:
    aliases: list[str] = []
    for key in ("aliases", "alias", "shortName", "abbr", "normalizedName"):
        value = properties.get(key)
        values = value if isinstance(value, list) else [value]
        for item in values:
            text = str(item or "").strip()
            if text and text not in aliases:
                aliases.append(text)
    return aliases


def main() -> None:
    nodes = json.loads(NODES.read_text(encoding="utf-8"))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as f:
        for node in nodes:
            properties = node.get("properties") or {}
            row = {
                "entity_id": node.get("id"),
                "name": node.get("name"),
                "entity_type": node.get("label"),
                "aliases": aliases_from_properties(properties),
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps({"output": str(OUTPUT), "rows": len(nodes)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
