#!/usr/bin/env python3
"""Prepare packed LightRAG documents without changing source knowledge."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "experiments" / "external_baselines"


def pack_documents(source: Path, target: Path, max_chars: int) -> tuple[int, int]:
    source_files = sorted(source.glob("*.txt"))
    packs: list[str] = []
    current: list[str] = []
    current_chars = 0

    for path in source_files:
        text = path.read_text(encoding="utf-8").strip()
        if current and current_chars + len(text) > max_chars:
            packs.append("\n\n".join(current) + "\n")
            current = []
            current_chars = 0
        current.append(text)
        current_chars += len(text)
    if current:
        packs.append("\n\n".join(current) + "\n")

    for index, text in enumerate(packs, 1):
        (target / f"pack_{index:06d}.txt").write_text(text, encoding="utf-8")
    return len(source_files), len(packs)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["smoke", "full"], required=True)
    parser.add_argument("--variant", choices=["raw", "natural", "compact"], default="natural")
    parser.add_argument(
        "--max-chars",
        type=int,
        default=1800,
        help="Pack short source records into coherent LightRAG-sized documents without changing their text.",
    )
    args = parser.parse_args()

    suffix = f"_{args.variant}" if args.variant != "raw" else ""
    source = BASE / "common" / "corpus" / (("smoke_docs" if args.mode == "smoke" else "all_docs") + suffix)
    if not source.exists():
        raise SystemExit(f"Corpus not found: {source}. Build it before preparing LightRAG.")

    target = BASE / "lightrag" / "workspace" / args.mode
    documents = target / "documents"
    if documents.exists():
        shutil.rmtree(documents)
    documents.mkdir(parents=True)

    source_count, packed_count = pack_documents(source, documents, args.max_chars)
    (target / "ENVIRONMENT.template").write_text(
        "DASHSCOPE_API_KEY=<export-in-shell-only>\n"
        "DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1\n"
        "DASHSCOPE_MODEL=qwen-plus\n"
        "LIGHTRAG_EMBED_MODEL=text-embedding-v3\n"
        "LIGHTRAG_EMBED_DIM=1024\n",
        encoding="utf-8",
    )
    print(
        f"{target} source_documents={source_count} packed_documents={packed_count} "
        f"variant={args.variant} max_chars={args.max_chars}"
    )


if __name__ == "__main__":
    main()
