# -*- coding: utf-8 -*-
"""Build a FAISS index over evidence text chunks."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List

import numpy as np

from embedding_backend import EmbeddingUnavailable, build_faiss_index, embed_texts, write_jsonl
from embedding_config import PROJECT_ROOT, get_embedding_config


DEFAULT_SOURCE_DIRS = [
    "app/builder/data/evidence/structured_evidence_docs",
    "app/builder/data/evidence/structured_evidence_docs_full_auto/structured_evidence_docs_full_auto",
    "app/builder/data/evidence/relation_chunk_pool",
    "app/builder/data/unstructured/unstructured_extract_staging/kag_sync",
    "app/builder/data/unstructured/unstructured_extract_staging/batch2_60/kag_sync",
    "app/builder/data/unstructured/unstructured_extract_staging/batch3_large_90/kag_sync",
]


EXCLUDED_DIR_NAMES = {"reports", "reportscd", "__pycache__"}
EXCLUDED_NAME_TOKENS = ("manifest", "report", "summary")


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _dedup_key(text: str) -> str:
    normalized = re.sub(r"\s+", "", str(text or "")).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _read_text(path: Path) -> str:
    if path.suffix.lower() in {".json", ".jsonl"}:
        parts = []
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            try:
                obj = json.loads(line)
                parts.append(json.dumps(obj, ensure_ascii=False))
            except Exception:
                parts.append(line)
        return "\n".join(parts)
    return path.read_text(encoding="utf-8", errors="ignore")


def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 80) -> Iterable[str]:
    clean = _clean_text(text)
    if len(clean) < 30:
        return
    start = 0
    while start < len(clean):
        chunk = clean[start : start + chunk_size].strip()
        if len(chunk) >= 30:
            yield chunk
        if start + chunk_size >= len(clean):
            break
        start += max(1, chunk_size - overlap)


def _should_index_file(path: Path) -> bool:
    """Return False for operational reports/manifests that are not evidence."""

    lower_parts = {part.lower() for part in path.parts}
    if lower_parts & EXCLUDED_DIR_NAMES:
        return False
    lower_name = path.name.lower()
    return not any(token in lower_name for token in EXCLUDED_NAME_TOKENS)


def collect_chunks(source_dirs: List[str]) -> tuple[List[Dict[str, object]], List[str], List[str], int, int]:
    rows: List[Dict[str, object]] = []
    skipped_paths: List[str] = []
    warnings: List[str] = []
    excluded_files = 0
    duplicate_chunks = 0
    seen_chunk_hashes = set()
    exts = {".txt", ".md", ".json", ".jsonl"}
    for raw_dir in source_dirs:
        source_dir = Path(raw_dir)
        if not source_dir.is_absolute():
            source_dir = PROJECT_ROOT / source_dir
        if not source_dir.exists():
            skipped_paths.append(str(source_dir))
            continue
        for path in sorted(p for p in source_dir.rglob("*") if p.suffix.lower() in exts):
            if not _should_index_file(path):
                excluded_files += 1
                continue
            try:
                text = _read_text(path)
            except Exception as exc:
                warnings.append(f"读取失败：{path}: {exc}")
                continue
            rel = str(path.relative_to(PROJECT_ROOT)) if path.is_relative_to(PROJECT_ROOT) else str(path)
            for idx, chunk in enumerate(_chunk_text(text)):
                key = _dedup_key(chunk)
                if key in seen_chunk_hashes:
                    duplicate_chunks += 1
                    continue
                seen_chunk_hashes.add(key)
                rows.append(
                    {
                        "chunk_id": f"evidence_{len(rows) + 1:06d}",
                        "source_path": rel,
                        "source_name": path.name,
                        "text": chunk,
                        "doc_type": _infer_doc_type(rel),
                        "entity_mentions": [],
                        "qtype_hint": "",
                        "char_len": len(chunk),
                        "chunk_index": idx,
                    }
                )
    return rows, skipped_paths, warnings, excluded_files, duplicate_chunks


def _infer_doc_type(path: str) -> str:
    if "structured_evidence_docs_full_auto" in path:
        return "structured_evidence_full_auto"
    if "relation_chunk_pool" in path:
        return "relation_chunk_pool"
    if "kag_sync" in path:
        return "kag_evidence_card"
    return "structured_evidence"


def _write_report(path: Path, lines: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_index(source_dirs: List[str]) -> int:
    cfg = get_embedding_config()
    out_dir = Path(str(cfg["evidence_index_dir"]))
    report_path = out_dir / "build_report.md"
    metadata_path = out_dir / "metadata.jsonl"
    index_path = out_dir / "faiss.index"
    rows, skipped, warnings, excluded_files, duplicate_chunks = collect_chunks(source_dirs)
    report = [
        "# Evidence Embedding Index 构建报告",
        f"- 构建时间：{datetime.now().isoformat(timespec='seconds')}",
        f"- 项目根目录：{PROJECT_ROOT}",
        f"- 扫描目录数：{len(source_dirs)}",
        f"- 跳过路径数：{len(skipped)}",
        f"- 排除报告/清单文件数：{excluded_files}",
        f"- 精确重复 chunk 去除数：{duplicate_chunks}",
        f"- chunk 总数：{len(rows)}",
        f"- embedding 后端：{cfg['embedding_backend']}",
        f"- embedding 模型名：{cfg['embedding_model_name'] or '<EMPTY>'}",
        f"- FAISS index 路径：{index_path}",
        f"- metadata 路径：{metadata_path}",
        "",
    ]
    if skipped:
        report.extend(["## 跳过路径", *[f"- {item}" for item in skipped], ""])
    if warnings:
        report.extend(["## 警告", *[f"- {item}" for item in warnings[:200]], ""])
    if not rows:
        report.append("## 构建结果\n- 状态：未生成索引\n- 原因：未收集到 chunk")
        _write_report(report_path, report)
        return 1
    try:
        vectors = embed_texts([str(row["text"]) for row in rows])
        build_faiss_index(np.asarray(vectors, dtype="float32"), index_path)
        write_jsonl(metadata_path, rows)
        report.extend(
            [
                "## 构建结果",
                "- 状态：OK",
                f"- 向量维度：{vectors.shape[1] if vectors.size else 0}",
            ]
        )
        _write_report(report_path, report)
        return 0
    except EmbeddingUnavailable as exc:
        report.extend(["## 构建结果", "- 状态：未生成索引", f"- 原因：{exc}"])
        _write_report(report_path, report)
        print(f"[embedding build failed] {exc}", file=sys.stderr)
        return 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", action="append", default=None)
    args = parser.parse_args()
    raise SystemExit(build_index(args.source_dir or DEFAULT_SOURCE_DIRS))


if __name__ == "__main__":
    main()
