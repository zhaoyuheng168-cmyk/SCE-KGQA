#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the unified RAG corpus for baseline comparison."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from common_io import ROOT, write_jsonl


DATA = ROOT / "app" / "builder" / "data"
DEFAULT_OUT = ROOT / "experiments" / "baselines" / "corpus"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def build_kg_triples() -> list[dict[str, Any]]:
    nodes = {row["id"]: row for row in load_json(DATA / "runtime" / "nodes_kag.json")}
    edges = load_json(DATA / "runtime" / "edges_kag.json")
    rows: list[dict[str, Any]] = []
    for idx, edge in enumerate(edges, 1):
        s = nodes.get(edge.get("from"), {})
        o = nodes.get(edge.get("to"), {})
        s_name = s.get("name") or edge.get("from")
        o_name = o.get("name") or edge.get("to")
        predicate = edge.get("label") or edge.get("type") or edge.get("properties", {}).get("relationType") or ""
        text = f"{s_name} {predicate} {o_name}。"
        rows.append(
            {
                "doc_id": f"kg_triple_{idx:06d}",
                "source_type": "kg_triple",
                "text": text,
                "subject": s_name,
                "predicate": predicate,
                "object": o_name,
                "metadata": {
                    "subject_id": edge.get("from"),
                    "object_id": edge.get("to"),
                    "subject_type": edge.get("fromType") or s.get("label"),
                    "object_type": edge.get("toType") or o.get("label"),
                    "edge_id": edge.get("id"),
                },
            }
        )
    return rows


def iter_evidence_files() -> list[Path]:
    roots = [
        DATA / "evidence" / "structured_evidence_docs",
        DATA / "evidence" / "structured_evidence_docs_full_auto",
        DATA / "evidence" / "relation_chunk_pool",
        DATA / "unstructured" / "unstructured_extract_staging" / "clean_docs",
        DATA / "unstructured" / "unstructured_extract_staging" / "outputs",
        DATA / "unstructured" / "unstructured_extract_staging" / "batch3_large_90" / "kag_sync" / "light_evidence_cards",
    ]
    files: list[Path] = []
    for root in roots:
        if root.exists():
            files.extend(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in {".txt", ".md", ".jsonl"})
    return sorted(files)


def read_text_chunks(path: Path) -> list[str]:
    if path.suffix.lower() == ".jsonl":
        chunks: list[str] = []
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            try:
                data = json.loads(line)
            except Exception:
                continue
            text = str(data.get("text") or data.get("content") or "").strip()
            if text:
                chunks.append(text)
        return chunks
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    return [text] if text else []


def build_evidence() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in iter_evidence_files():
        for text in read_text_chunks(path):
            rows.append(
                {
                    "doc_id": f"evidence_{len(rows) + 1:06d}",
                    "source_type": "evidence",
                    "text": text[:4000],
                    "subject": None,
                    "predicate": "evidence_support",
                    "object": None,
                    "metadata": {"source_file": str(path.relative_to(ROOT))},
                }
            )
    return rows


def write_report(out_dir: Path, kg_rows: list[dict[str, Any]], ev_rows: list[dict[str, Any]]) -> None:
    merged = kg_rows + ev_rows
    source_counter = Counter(row["source_type"] for row in merged)
    pred_counter = Counter(str(row.get("predicate") or "") for row in merged)
    report = [
        "# Corpus V1 Report",
        "",
        f"- kg_triples: {len(kg_rows)}",
        f"- evidence_chunks: {len(ev_rows)}",
        f"- merged_total: {len(merged)}",
        "",
        "## source_type",
        "",
    ]
    report += [f"- {k}: {v}" for k, v in source_counter.most_common()]
    report += ["", "## top predicates", ""]
    report += [f"- {k}: {v}" for k, v in pred_counter.most_common(30)]
    report += ["", "## leakage note", "", "Corpus is built only from frozen runtime KG and evidence files; no test gold fields are read."]
    (out_dir / "corpus_v1_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    kg_rows = build_kg_triples()
    ev_rows = build_evidence()
    write_jsonl(args.out_dir / "kg_triples_corpus.jsonl", kg_rows)
    write_jsonl(args.out_dir / "evidence_corpus.jsonl", ev_rows)
    write_jsonl(args.out_dir / "merged_rag_corpus.jsonl", kg_rows + ev_rows)
    write_report(args.out_dir, kg_rows, ev_rows)
    print(f"kg_triples={len(kg_rows)} evidence={len(ev_rows)} merged={len(kg_rows) + len(ev_rows)}")


if __name__ == "__main__":
    main()
