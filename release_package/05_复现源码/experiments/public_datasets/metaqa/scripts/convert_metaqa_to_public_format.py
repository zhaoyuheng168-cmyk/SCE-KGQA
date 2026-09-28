#!/usr/bin/env python3
"""Bounded MetaQA converter for smoke preparation.

This script refuses full conversion. A positive --limit-per-split is required
unless --dry-run is used.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple


HOPS = (1, 2, 3)
SPLITS = ("train", "dev", "test")


def write_jsonl(path: Path, rows: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def count_lines(path: Path) -> int:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return sum(1 for _ in handle)


def parse_qa(line: str) -> Tuple[str, List[str], str]:
    text = line.rstrip("\r\n")
    if "\t" not in text:
        return text, [], "missing_tab"
    question, answer_text = text.split("\t", 1)
    answers = [answer.strip() for answer in answer_text.split("|") if answer.strip()]
    return question, answers, "empty_answer" if not answers else ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--limit-per-split", type=int, default=0)
    parser.add_argument("--include-graph", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.limit_per_split <= 0 and not args.dry_run:
        parser.error("A positive --limit-per-split is required; full conversion is disabled.")

    raw_dir = Path(args.raw_dir).resolve()
    out_dir = Path(args.out_dir).resolve()
    limit = max(args.limit_per_split, 0)
    malformed_counts: Dict[str, int] = {}
    line_counts: Dict[str, int] = {}
    qa_output_files: List[str] = []
    graph_output_files: List[str] = []

    for hop in HOPS:
        for split in SPLITS:
            qa_rel = f"{hop}-hop/vanilla/qa_{split}.txt"
            qtype_rel = f"{hop}-hop/qa_{split}_qtype.txt"
            qa_path = raw_dir / qa_rel
            qtype_path = raw_dir / qtype_rel
            qa_count = count_lines(qa_path)
            qtype_count = count_lines(qtype_path)
            line_counts[qa_rel] = qa_count
            line_counts[qtype_rel] = qtype_count
            if qa_count != qtype_count:
                raise RuntimeError(
                    f"qtype/QA line-count mismatch: {qtype_rel}={qtype_count}, "
                    f"{qa_rel}={qa_count}"
                )

            rows = []
            malformed = 0
            with qa_path.open("r", encoding="utf-8", errors="replace") as qa_handle, qtype_path.open(
                "r", encoding="utf-8", errors="replace"
            ) as qtype_handle:
                for index, (qa_line, qtype_line) in enumerate(zip(qa_handle, qtype_handle)):
                    if limit and index >= limit:
                        break
                    question, answers, warning = parse_qa(qa_line)
                    if warning:
                        malformed += 1
                    rows.append(
                        {
                            "dataset": "MetaQA",
                            "hop": hop,
                            "split": split,
                            "qid": f"metaqa_{hop}hop_{split}_{index:06d}",
                            "question": question,
                            "answers": answers,
                            "qtype": qtype_line.rstrip("\r\n"),
                            "source_question_file": qa_rel,
                            "source_qtype_file": qtype_rel,
                            **({"warning": warning} if warning else {}),
                        }
                    )
            malformed_counts[f"{hop}-hop/{split}/qa"] = malformed
            output = out_dir / "qa" / f"metaqa_{hop}hop_{split}.jsonl"
            qa_output_files.append(str(output))
            if not args.dry_run:
                write_jsonl(output, rows)

    if args.include_graph:
        kb_path = raw_dir / "kb.txt"
        line_counts["kb.txt"] = count_lines(kb_path)
        nodes: Dict[str, dict] = {}
        edges = []
        malformed = 0
        with kb_path.open("r", encoding="utf-8", errors="replace") as handle:
            for index, line in enumerate(handle):
                if limit and index >= limit:
                    break
                text = line.rstrip("\r\n")
                parts = text.split("|")
                if len(parts) != 3 or not all(part.strip() for part in parts):
                    malformed += 1
                    continue
                source, relation, target = parts
                nodes.setdefault(source, {"id": source, "name": source, "type": "Entity"})
                nodes.setdefault(target, {"id": target, "name": target, "type": "Entity"})
                edges.append(
                    {
                        "source": source,
                        "relation": relation,
                        "target": target,
                        "source_file": "kb.txt",
                    }
                )
        malformed_counts["kb.txt_smoke"] = malformed
        node_path = out_dir / "graph" / "metaqa_nodes.jsonl"
        edge_path = out_dir / "graph" / "metaqa_edges.jsonl"
        graph_output_files.extend([str(node_path), str(edge_path)])
        if not args.dry_run:
            write_jsonl(node_path, list(nodes.values()))
            write_jsonl(edge_path, edges)

    manifest = {
        "raw_dir": str(raw_dir),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "limit_per_split": limit,
        "hops": list(HOPS),
        "splits": list(SPLITS),
        "qa_output_files": qa_output_files,
        "graph_output_files": graph_output_files,
        "malformed_counts": malformed_counts,
        "line_counts": line_counts,
        "dry_run": args.dry_run,
        "graph_smoke_limit": limit if args.include_graph else 0,
    }
    manifest_path = out_dir / "manifest.json"
    if not args.dry_run:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"dry_run={args.dry_run}")
    print(f"limit_per_split={limit}")
    print(f"qa_records={len(HOPS) * len(SPLITS) * limit}")
    print(f"manifest={manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

