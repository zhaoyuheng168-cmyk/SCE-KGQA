# -*- coding: utf-8 -*-
"""Build a FAISS index over KG relation schema descriptions."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

from embedding_backend import EmbeddingUnavailable, build_faiss_index, embed_texts, write_jsonl
from embedding_config import PROJECT_ROOT, get_embedding_config
from relation_schema_catalog import RELATION_SCHEMA_ROWS, relation_embedding_text


def _write_report(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_index() -> int:
    cfg = get_embedding_config()
    out_dir = Path(str(cfg["relation_index_dir"]))
    report_path = out_dir / "build_report.md"
    metadata_path = out_dir / "metadata.jsonl"
    index_path = out_dir / "faiss.index"

    rows = []
    for i, row in enumerate(RELATION_SCHEMA_ROWS, start=1):
        item = dict(row)
        item["relation_schema_id"] = f"relation_schema_{i:03d}"
        item["embedding_text"] = relation_embedding_text(item)
        rows.append(item)

    report = [
        "# Relation Embedding Index 构建报告",
        f"- 构建时间：{datetime.now().isoformat(timespec='seconds')}",
        f"- 项目根目录：{PROJECT_ROOT}",
        f"- embedding 后端：{cfg['embedding_backend']}",
        f"- embedding 模型名：{cfg['embedding_model_name'] or '<EMPTY>'}",
        f"- FAISS index 路径：{index_path}",
        f"- metadata 路径：{metadata_path}",
        f"- 关系 schema 数量：{len(rows)}",
        "",
    ]

    try:
        if not rows:
            raise EmbeddingUnavailable("no relation schema rows")
        vectors = embed_texts([str(row["embedding_text"]) for row in rows])
        build_faiss_index(np.asarray(vectors, dtype="float32"), index_path)
        write_jsonl(metadata_path, rows)
        report.extend(["## 构建结果", "- 状态：OK", f"- 向量维度：{vectors.shape[1] if vectors.size else 0}"])
        _write_report(report_path, report)
        return 0
    except Exception as exc:
        report.extend(["## 构建结果", "- 状态：未生成索引", f"- 原因：{exc}"])
        _write_report(report_path, report)
        print(f"[relation embedding build failed] {exc}", file=sys.stderr)
        return 1


def main() -> None:
    argparse.ArgumentParser().parse_args()
    raise SystemExit(build_index())


if __name__ == "__main__":
    main()
