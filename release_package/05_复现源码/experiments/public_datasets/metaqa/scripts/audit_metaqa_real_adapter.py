#!/usr/bin/env python3
"""Static audit of the real MetaQA adapter against uploaded raw metadata."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.generic_kgqa_framework.adapters.metaqa_real import MetaQARealAdapter
from tools.generic_kgqa_framework.validation import validate_schema


HOPS = (1, 2, 3)
SPLITS = ("train", "dev", "test")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()

    raw_dir = Path(args.raw_dir).resolve()
    report_path = Path(args.report).resolve()
    schema = MetaQARealAdapter().schema()
    validation_issues = validate_schema(schema)

    raw_qtypes = set()
    raw_qtype_counts = Counter()
    raw_qtypes_by_hop = {}
    for hop in HOPS:
        hop_qtypes = set()
        for split in SPLITS:
            path = raw_dir / f"{hop}-hop/qa_{split}_qtype.txt"
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    qtype = line.strip()
                    if qtype:
                        hop_qtypes.add(qtype)
                        raw_qtypes.add(qtype)
                        raw_qtype_counts[qtype] += 1
        raw_qtypes_by_hop[hop] = hop_qtypes

    raw_relations = Counter()
    with (raw_dir / "kb.txt").open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            parts = line.rstrip("\r\n").split("|")
            if len(parts) == 3:
                raw_relations[parts[1]] += 1

    adapter_qtypes = set(schema.routes)
    adapter_relations = set(schema.relations)
    missing_qtypes = sorted(raw_qtypes - adapter_qtypes)
    extra_qtypes = sorted(adapter_qtypes - raw_qtypes)
    missing_relations = sorted(set(raw_relations) - adapter_relations)
    extra_relations = sorted(adapter_relations - set(raw_relations))
    constrained_routes = {
        qtype: list(route.path_constraints.exclude_start_at_steps)
        for qtype, route in schema.routes.items()
        if route.path_constraints.exclude_start_at_steps
    }

    passed = not (
        validation_issues
        or missing_qtypes
        or extra_qtypes
        or missing_relations
        or extra_relations
    )
    lines = [
        "# Real MetaQA Unified-Core Adapter Audit",
        "",
        f"- Raw directory: `{raw_dir}`",
        f"- Adapter: `{MetaQARealAdapter.name}`",
        f"- Raw unique qtypes: **{len(raw_qtypes)}**",
        f"- Adapter routes: **{len(adapter_qtypes)}**",
        f"- Raw relations: **{len(raw_relations)}**",
        f"- Adapter relations: **{len(adapter_relations)}**",
        f"- Schema validation issues: **{len(validation_issues)}**",
        f"- Conclusion: **{'PASS' if passed else 'FAIL'}**",
        "",
        "## Coverage",
        "",
        "| Item | Missing from adapter | Extra in adapter |",
        "|---|---:|---:|",
        f"| Qtypes | {len(missing_qtypes)} | {len(extra_qtypes)} |",
        f"| Relations | {len(missing_relations)} | {len(extra_relations)} |",
        "",
        "## Routes by Hop",
        "",
        "| Hop | Raw qtypes | Adapter routes |",
        "|---:|---:|---:|",
    ]
    for hop in HOPS:
        adapter_hop = {
            qtype for qtype, route in schema.routes.items() if route.metadata.get("hop") == hop
        }
        lines.append(f"| {hop} | {len(raw_qtypes_by_hop[hop])} | {len(adapter_hop)} |")

    lines.extend(
        [
            "",
            "## Automatically Constrained Routes",
            "",
            "| Qtype | Exclude start at steps |",
            "|---|---|",
        ]
    )
    for qtype, steps in sorted(constrained_routes.items()):
        lines.append(f"| `{qtype}` | `{steps}` |")

    lines.extend(["", "## Errors", ""])
    errors = []
    errors.extend(f"validation: {issue.code}: {issue.message}" for issue in validation_issues)
    errors.extend(f"missing qtype: {value}" for value in missing_qtypes)
    errors.extend(f"extra qtype: {value}" for value in extra_qtypes)
    errors.extend(f"missing relation: {value}" for value in missing_relations)
    errors.extend(f"extra relation: {value}" for value in extra_relations)
    lines.extend(f"- {error}" for error in errors)
    if not errors:
        lines.append("- None.")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"routes={len(adapter_qtypes)}")
    print(f"relations={len(adapter_relations)}")
    print(f"constrained_routes={len(constrained_routes)}")
    print(f"validation_issues={len(validation_issues)}")
    print(f"missing_qtypes={len(missing_qtypes)}")
    print(f"extra_qtypes={len(extra_qtypes)}")
    print(f"report={report_path}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
