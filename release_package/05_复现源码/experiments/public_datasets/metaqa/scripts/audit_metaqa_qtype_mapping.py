#!/usr/bin/env python3
"""Read-only audit of real MetaQA qtypes and their generated typed paths."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Dict

from metaqa_schema_mapping import parse_qtype_path


HOPS = (1, 2, 3)
SPLITS = ("train", "dev", "test")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--mapping-json", required=True)
    args = parser.parse_args()

    raw_dir = Path(args.raw_dir).resolve()
    report = Path(args.report).resolve()
    mapping_json = Path(args.mapping_json).resolve()
    qtype_counts: Dict[int, Counter[str]] = {hop: Counter() for hop in HOPS}

    for hop in HOPS:
        for split in SPLITS:
            path = raw_dir / f"{hop}-hop/qa_{split}_qtype.txt"
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                qtype_counts[hop].update(line.strip() for line in handle if line.strip())

    mappings = {}
    errors = []
    for hop, counts in qtype_counts.items():
        for qtype, count in sorted(counts.items()):
            try:
                steps = parse_qtype_path(qtype)
                if len(steps) != hop:
                    errors.append(f"{qtype}: expected {hop} steps, generated {len(steps)}")
                mappings[qtype] = {"hop": hop, "count": count, "steps": steps}
            except ValueError as exc:
                errors.append(str(exc))

    mapping_json.parent.mkdir(parents=True, exist_ok=True)
    mapping_json.write_text(json.dumps(mappings, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# MetaQA Qtype to Typed-Path Mapping Audit",
        "",
        f"- Raw directory: `{raw_dir}`",
        f"- Unique qtypes: **{len(mappings)}**",
        f"- Mapping errors: **{len(errors)}**",
        f"- Conclusion: **{'PASS' if not errors else 'FAIL'}**",
        "",
        "## Summary",
        "",
        "| Hop | Unique qtypes | Total aligned QA/qtype rows |",
        "|---:|---:|---:|",
    ]
    for hop in HOPS:
        lines.append(f"| {hop} | {len(qtype_counts[hop])} | {sum(qtype_counts[hop].values())} |")

    lines.extend(
        [
            "",
            "## Generated Typed Paths",
            "",
            "| Hop | Qtype | Count | Typed path |",
            "|---:|---|---:|---|",
        ]
    )
    for qtype, spec in sorted(mappings.items(), key=lambda item: (item[1]["hop"], item[0])):
        path_text = " ; ".join(
            f"{step['source_role']} -[{step['relation']} / {step['direction']}]-> {step['target_role']}"
            for step in spec["steps"]
        )
        lines.append(f"| {spec['hop']} | `{qtype}` | {spec['count']} | `{path_text}` |")

    lines.extend(["", "## Errors", ""])
    if errors:
        lines.extend(f"- {error}" for error in errors)
    else:
        lines.append("- None.")
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"unique_qtypes={len(mappings)}")
    print(f"mapping_errors={len(errors)}")
    print(f"report={report}")
    print(f"mapping_json={mapping_json}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

