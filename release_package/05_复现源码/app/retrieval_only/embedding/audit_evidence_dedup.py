# -*- coding: utf-8 -*-
"""Audit duplicate evidence chunks without rebuilding the FAISS index."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from embedding_config import PROJECT_ROOT, get_embedding_config


RELATIONS = (
    "providesProduct",
    "supports",
    "issuesLoan",
    "loanToEnterprise",
    "issues",
    "hasFeature",
)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", str(text or "")).strip()


def _text_hash(text: str) -> str:
    return hashlib.sha256(_normalize_text(text).encode("utf-8")).hexdigest()


def _source_bucket(source_path: str) -> str:
    if "structured_evidence_docs_full_auto" in source_path:
        return "structured_evidence_docs_full_auto"
    if "structured_evidence_docs" in source_path:
        return "structured_evidence_docs"
    if "relation_chunk_pool" in source_path:
        return "relation_chunk_pool"
    if "batch2_60/kag_sync" in source_path:
        return "batch2_60_kag_sync"
    if "batch3_large_90/kag_sync" in source_path:
        return "batch3_large_90_kag_sync"
    if "unstructured_extract_staging/kag_sync" in source_path:
        return "kag_sync"
    return "other"


def _strip_suffix(name: str) -> str:
    return re.sub(r"\.(txt|md|json|jsonl)$", "", name)


def _fact_key_from_source(source_path: str) -> str:
    stem = _strip_suffix(Path(source_path).name)
    if stem.startswith("V1U_LIGHT_"):
        parts = stem.split("_")
        if len(parts) >= 5:
            return "fact:" + "_".join(parts[2:])
    if stem.startswith("BATCH2_"):
        parts = stem.split("_")
        if len(parts) >= 5:
            return "fact:" + "_".join(parts[2:])
    if stem.startswith("V1U_B3_"):
        parts = stem.split("_")
        if len(parts) >= 5:
            return "fact:" + "_".join(parts[3:])
    for relation in RELATIONS:
        marker = f"_{relation}_"
        if marker in stem:
            before, after = stem.split(marker, 1)
            subject = before.split("__")[-1]
            return f"fact:{subject}_{relation}_{after}"
        if stem.endswith(f"_{relation}"):
            subject = stem[: -len(relation) - 1].split("__")[-1]
            return f"relation_doc:{subject}_{relation}"
    return ""


def _read_jsonl(path: Path) -> Iterable[Dict[str, object]]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def audit(metadata_path: Path, report_path: Path, sample_limit: int = 20) -> None:
    rows = list(_read_jsonl(metadata_path))
    source_files = {str(row.get("source_path", "")) for row in rows}
    by_hash: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    by_fact: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    bucket_chunks = Counter()
    bucket_files = Counter(_source_bucket(path) for path in source_files)

    for row in rows:
        source_path = str(row.get("source_path", ""))
        text = str(row.get("text", ""))
        by_hash[_text_hash(text)].append(row)
        fact_key = _fact_key_from_source(source_path)
        if fact_key:
            by_fact[fact_key].append(row)
        bucket_chunks[_source_bucket(source_path)] += 1

    exact_groups = {k: v for k, v in by_hash.items() if len(v) > 1}
    fact_groups = {k: v for k, v in by_fact.items() if len({str(r.get("source_path", "")) for r in v}) > 1}
    exact_duplicate_chunks = sum(len(v) - 1 for v in exact_groups.values())
    fact_duplicate_chunks = sum(len(v) - 1 for v in fact_groups.values())
    fact_unique_source_duplicate_groups = {
        k: sorted({str(r.get("source_path", "")) for r in v})
        for k, v in fact_groups.items()
    }

    lines: List[str] = [
        "# Evidence Dedup 只读审计报告",
        "",
        f"- 审计时间：{datetime.now().isoformat(timespec='seconds')}",
        f"- 项目根目录：{PROJECT_ROOT}",
        f"- metadata 路径：{metadata_path}",
        f"- chunk 总数：{len(rows)}",
        f"- 源文件数：{len(source_files)}",
        "",
        "## 来源分布",
        "",
        "| 来源桶 | 文件数 | chunk 数 |",
        "| --- | ---: | ---: |",
    ]
    for bucket in sorted(set(bucket_files) | set(bucket_chunks)):
        lines.append(f"| {bucket} | {bucket_files[bucket]} | {bucket_chunks[bucket]} |")

    lines.extend(
        [
            "",
            "## 精确重复 chunk",
            "",
            f"- 精确重复组数：{len(exact_groups)}",
            f"- 可去掉的完全重复 chunk 数：{exact_duplicate_chunks}",
            f"- 精确去重后预计 chunk 数：{len(rows) - exact_duplicate_chunks}",
            "",
            "## 文件名/路径事实级重复",
            "",
            f"- 事实级重复组数：{len(fact_groups)}",
            f"- 按当前粗粒度 fact key 可去掉的重复 chunk 数：{fact_duplicate_chunks}",
            f"- 事实级去重后预计 chunk 数：{len(rows) - fact_duplicate_chunks}",
            "",
            "说明：事实级重复是根据文件名/路径中的 subject-relation-object 或 relation doc 规则粗略抽取，不能直接等同最终删除策略，需要人工确认保留优先级。",
            "",
        ]
    )

    if exact_groups:
        lines.extend(["## 精确重复样例", ""])
        for i, group in enumerate(list(exact_groups.values())[:sample_limit], 1):
            lines.append(f"### 样例 {i}")
            lines.append(f"- 重复 chunk 数：{len(group)}")
            for row in group[:8]:
                lines.append(f"- {row.get('chunk_id')} | {row.get('source_path')}")
            lines.append("")

    if fact_unique_source_duplicate_groups:
        lines.extend(["## 事实级重复样例", ""])
        for i, (key, paths) in enumerate(list(fact_unique_source_duplicate_groups.items())[:sample_limit], 1):
            lines.append(f"### 样例 {i}")
            lines.append(f"- fact_key：`{key}`")
            lines.append(f"- 涉及源文件数：{len(paths)}")
            for path in paths[:10]:
                lines.append(f"- {path}")
            lines.append("")

    lines.extend(
        [
            "## 初步建议",
            "",
            "1. 先做精确文本 hash 去重，风险最低。",
            "2. 再做 fact_key 去重，但需要定义来源优先级。",
            "3. 建议优先保留结构最清晰、证据字段最完整的来源；同一事实不要让多个派生文件同时占满 top-k。",
            "4. 去重后重建 evidence index，再跑 10 条 smoke，重点观察 top-k 多样性。",
            "",
        ]
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    cfg = get_embedding_config()
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--metadata",
        default=str(Path(str(cfg["evidence_index_dir"])) / "metadata.jsonl"),
    )
    parser.add_argument(
        "--report",
        default=str(PROJECT_ROOT / "experiment_notes" / "stage_emb_evidence_dedup_audit.md"),
    )
    args = parser.parse_args()
    audit(Path(args.metadata), Path(args.report))


if __name__ == "__main__":
    main()

