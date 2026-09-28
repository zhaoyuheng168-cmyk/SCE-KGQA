#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Export comparison assets for an OpenSPG-KAG external baseline.

The script does not install or call OpenSPG/KAG. It prepares the frozen inputs
needed to build a fair external KAG baseline from the same KG, evidence chunks,
and QA splits used by the other comparison experiments.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / "experiments" / "baselines" / "openspg_kag"
CORPUS_DIR = ROOT / "experiments" / "baselines" / "corpus"
DATASET_DIR = ROOT / "experiments" / "baselines" / "datasets"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def export_triples(out_dir: Path) -> tuple[int, Counter[str], Counter[str]]:
    rows = read_jsonl(CORPUS_DIR / "kg_triples_corpus.jsonl")
    pred_counter: Counter[str] = Counter()
    type_counter: Counter[str] = Counter()
    out_path = out_dir / "data" / "kg_triples_for_openspg.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "subject_id",
                "subject_name",
                "subject_type",
                "predicate",
                "object_id",
                "object_name",
                "object_type",
                "source_doc_id",
                "source_text",
            ],
        )
        writer.writeheader()
        for row in rows:
            meta = row.get("metadata") or {}
            predicate = str(row.get("predicate") or "")
            subject_type = str(meta.get("subject_type") or "")
            object_type = str(meta.get("object_type") or "")
            pred_counter[predicate] += 1
            if subject_type:
                type_counter[subject_type] += 1
            if object_type:
                type_counter[object_type] += 1
            writer.writerow(
                {
                    "subject_id": meta.get("subject_id") or "",
                    "subject_name": row.get("subject") or "",
                    "subject_type": subject_type,
                    "predicate": predicate,
                    "object_id": meta.get("object_id") or "",
                    "object_name": row.get("object") or "",
                    "object_type": object_type,
                    "source_doc_id": row.get("doc_id") or "",
                    "source_text": row.get("text") or "",
                }
            )
    return len(rows), pred_counter, type_counter


def export_evidence(out_dir: Path) -> int:
    rows = read_jsonl(CORPUS_DIR / "evidence_corpus.jsonl")
    out_rows: list[dict[str, Any]] = []
    for row in rows:
        out_rows.append(
            {
                "id": row.get("doc_id"),
                "content": row.get("text"),
                "source_type": row.get("source_type"),
                "source_file": (row.get("metadata") or {}).get("source_file"),
                "predicate_hint": row.get("predicate"),
            }
        )
    write_jsonl(out_dir / "data" / "evidence_chunks_for_kag.jsonl", out_rows)
    return len(out_rows)


def export_qa_split(in_path: Path, out_path: Path) -> int:
    rows = read_csv_rows(in_path)
    out_rows: list[dict[str, Any]] = []
    for row in rows:
        out_rows.append(
            {
                "id": row.get("question_id"),
                "question": row.get("question"),
            }
        )
    write_jsonl(out_path, out_rows)
    return len(out_rows)


def write_schema_draft(out_dir: Path, pred_counter: Counter[str], type_counter: Counter[str]) -> None:
    lines = [
        "# OpenSPG-KAG Schema Draft for GansuTechFinance",
        "",
        "This is a neutral schema draft generated from the frozen comparison KG.",
        "It is intended for building an external OpenSPG-KAG baseline, not for",
        "changing the SCE-KGQA runtime.",
        "",
        "## Entity Types",
        "",
    ]
    for name, count in type_counter.most_common():
        lines.append(f"- {name}: {count}")
    lines += ["", "## Relation Types", ""]
    for name, count in pred_counter.most_common():
        lines.append(f"- {name}: {count}")
    lines += [
        "",
        "## Suggested OpenSPG Mapping",
        "",
        "- Treat each row in `kg_triples_for_openspg.csv` as one fact edge.",
        "- Treat `subject_type` and `object_type` as SPG concept/entity classes.",
        "- Treat `predicate` as the relation name.",
        "- Treat `evidence_chunks_for_kag.jsonl` as text chunks mutually indexed with graph facts.",
        "- Use the same QA JSONL split files for smoke/dev/formal evaluation.",
    ]
    (out_dir / "schema_draft.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_readme(out_dir: Path, triple_count: int, evidence_count: int, qa_counts: dict[str, int]) -> None:
    lines = [
        "# OpenSPG-KAG Baseline Assets",
        "",
        "This directory contains frozen input assets for an external OpenSPG-KAG comparison baseline.",
        "",
        "## Files",
        "",
        "- `data/kg_triples_for_openspg.csv`: structured KG facts exported from the same runtime KG used by SCE-KGQA.",
        "- `data/evidence_chunks_for_kag.jsonl`: evidence chunks exported from the same baseline evidence corpus.",
        "- `qa/smoke_30.jsonl`: smoke split for pipeline verification.",
        "- `qa/dev_120.jsonl`: development split for baseline tuning.",
        "- `qa/formal_1300.jsonl`: frozen formal split for paper results.",
        "- `schema_draft.md`: entity/relation inventory for OpenSPG schema mapping.",
        "",
        "## Counts",
        "",
        f"- KG triples: {triple_count}",
        f"- evidence chunks: {evidence_count}",
    ]
    for name, count in qa_counts.items():
        lines.append(f"- QA {name}: {count}")
    lines += [
        "",
        "## Fairness Boundary",
        "",
        "OpenSPG-KAG may use the exported graph facts, text chunks, schema mapping, qwen-plus,",
        "and a comparable embedding model. It must not call SCE-KGQA internal router, fallback",
        "logic, V8 planner, answer validator, or runtime answer API.",
        "",
        "## Expected Evaluation Flow",
        "",
        "1. Install OpenSPG engine and KAG toolkit in an isolated environment.",
        "2. Create a GansuTechFinance project/schema in OpenSPG.",
        "3. Import `kg_triples_for_openspg.csv` as graph facts.",
        "4. Import `evidence_chunks_for_kag.jsonl` as chunks/knowledge units.",
        "5. Configure KAG LLM and embedding settings.",
        "6. Run `qa/smoke_30.jsonl`, then `qa/dev_120.jsonl`, then frozen `qa/formal_1300.jsonl`.",
        "7. Convert KAG answers to the common baseline JSONL format and evaluate with",
        "   `tools/baselines/evaluate_baseline_results.py`.",
    ]
    (out_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    triple_count, pred_counter, type_counter = export_triples(args.out_dir)
    evidence_count = export_evidence(args.out_dir)
    qa_counts = {
        "smoke_30": export_qa_split(DATASET_DIR / "smoke_30.csv", args.out_dir / "qa" / "smoke_30.jsonl"),
        "dev_120": export_qa_split(DATASET_DIR / "dev_120.csv", args.out_dir / "qa" / "dev_120.jsonl"),
        "formal_1300": export_qa_split(
            DATASET_DIR / "gtf_kgqa_1300_formal.csv",
            args.out_dir / "qa" / "formal_1300.jsonl",
        ),
    }
    write_schema_draft(args.out_dir, pred_counter, type_counter)
    write_readme(args.out_dir, triple_count, evidence_count, qa_counts)
    print(
        json.dumps(
            {
                "out_dir": str(args.out_dir),
                "kg_triples": triple_count,
                "evidence_chunks": evidence_count,
                "qa": qa_counts,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
