# -*- coding: utf-8 -*-
"""Dataset loading helpers for public KGQA benchmark adapters."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence


@dataclass(frozen=True)
class Triple:
    subject: str
    relation: str
    object: str


def _clean(value: object) -> str:
    return str(value or "").strip()


def parse_triple_line(line: str, delimiters: Sequence[str] = ("\t", "|")) -> Optional[Triple]:
    """Parse one triple line from common KGQA benchmark formats.

    MetaQA commonly uses pipe-separated triples, while many other public KGQA
    exports use TSV. The parser accepts both by default.
    """

    text = str(line or "").strip()
    if not text or text.startswith("#"):
        return None

    for delimiter in delimiters:
        parts = [part.strip() for part in text.split(delimiter)]
        if len(parts) == 3 and all(parts):
            return Triple(parts[0], parts[1], parts[2])

    parts = text.split()
    if len(parts) == 3 and all(parts):
        return Triple(parts[0], parts[1], parts[2])

    raise ValueError(f"Cannot parse triple line: {line!r}")


def load_triples(path: str, delimiters: Sequence[str] = ("\t", "|")) -> List[Triple]:
    triples: List[Triple] = []
    source = Path(path)
    for lineno, line in enumerate(source.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            triple = parse_triple_line(line, delimiters=delimiters)
        except ValueError as exc:
            raise ValueError(f"{source}:{lineno}: {exc}") from exc
        if triple is not None:
            triples.append(triple)
    return triples


def triples_from_rows(rows: Iterable[Sequence[str]]) -> List[Triple]:
    triples: List[Triple] = []
    for row in rows:
        if len(row) != 3:
            raise ValueError(f"Expected 3 columns, got {len(row)}")
        subject, relation, obj = [_clean(value) for value in row]
        if subject and relation and obj:
            triples.append(Triple(subject, relation, obj))
    return triples

