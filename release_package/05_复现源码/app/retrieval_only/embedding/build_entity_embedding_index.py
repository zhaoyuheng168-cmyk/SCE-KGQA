# -*- coding: utf-8 -*-
"""Build a FAISS index over Neo4j entities with aliases and graph context."""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List

import numpy as np
from neo4j import GraphDatabase

from embedding_backend import EmbeddingUnavailable, build_faiss_index, embed_texts, write_jsonl
from embedding_config import PROJECT_ROOT, get_embedding_config


CORE_LABELS = {
    "Policy",
    "FinancialProduct",
    "FinancialInstitution",
    "Enterprise",
    "Region",
    "IndustrySegment",
    "QualificationCreditFeature",
    "LoanEvent",
    "GovernmentAgency",
}


def _plain_label(label: str) -> str:
    return str(label or "").split(".")[-1]


ALIAS_PROP_KEYS = {
    "alias",
    "aliases",
    "aliasName",
    "aliasNames",
    "shortName",
    "short_name",
    "abbr",
    "abbreviation",
    "compact_name",
    "normalized_name",
}

CONTEXT_PROP_KEYS = {
    "providerName",
    "issuingAgencyName",
    "targetGroup",
    "industry",
    "enterpriseType",
    "theme",
    "policyType",
    "remark",
}


def _dedup(values: Iterable[str], limit: int = 24) -> List[str]:
    results: List[str] = []
    seen = set()
    for value in values:
        text = re.sub(r"\s+", "", str(value or "").strip())
        if not text or text in seen:
            continue
        seen.add(text)
        results.append(text)
        if len(results) >= limit:
            break
    return results


def _split_prop_values(value: object) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        raw_items = [str(item) for item in value]
    else:
        raw_items = re.split(r"[,，、;/；\s]+", str(value))
    return [item.strip() for item in raw_items if item and item.strip()]


def _generated_aliases(name: str, plain_labels: List[str], props: Dict[str, object]) -> List[str]:
    aliases: List[str] = []
    for key in ALIAS_PROP_KEYS:
        aliases.extend(_split_prop_values(props.get(key)))

    aliases.append(name.replace("“", "").replace("”", "").replace("\"", ""))
    aliases.append(re.sub(r"[（）()《》<>\"“”]", "", name))

    if "FinancialProduct" in plain_labels:
        if "e贷" in name:
            aliases.append(name.replace("e贷", "E贷"))
            aliases.append(name.replace("e贷", "易贷"))
            aliases.append(name.replace("e贷", "贷"))
        if "E贷" in name:
            aliases.append(name.replace("E贷", "e贷"))
            aliases.append(name.replace("E贷", "易贷"))
            aliases.append(name.replace("E贷", "贷"))

    if "FinancialInstitution" in plain_labels:
        if name.endswith("银行"):
            stem = name[: -len("银行")]
            if len(stem) >= 2:
                aliases.append(f"{stem}行")
                aliases.append(f"{stem[:1]}行")
        if "中国邮政储蓄银行" in name:
            aliases.append(name.replace("中国邮政储蓄银行", "邮储银行"))
            aliases.append(name.replace("中国邮政储蓄银行", "邮储"))
            if "甘肃省分行" in name:
                aliases.extend(["邮储甘肃分行", "邮储银行甘肃分行", "邮储银行甘肃省分行"])

    return [alias for alias in _dedup(aliases) if alias != name]


def _context_terms(props: Dict[str, object], rels: List[Dict[str, object]]) -> List[str]:
    terms: List[str] = []
    for key in CONTEXT_PROP_KEYS:
        terms.extend(_split_prop_values(props.get(key)))
    for rel in rels[:20]:
        rel_type = str(rel.get("rel", "")).strip()
        neighbor = str(rel.get("neighbor", "")).strip()
        if rel_type and neighbor:
            terms.append(f"{rel_type}:{neighbor}")
    return _dedup(terms, limit=32)


def _entity_text(name: str, labels: List[str], aliases: List[str], context_terms: List[str]) -> str:
    clean_labels = [_plain_label(label) for label in labels]
    parts = [
        f"实体名称：{name}",
        f"实体类型：{'/'.join(clean_labels)}",
    ]
    if aliases:
        parts.append(f"别名简称拼写变体：{'、'.join(aliases[:16])}")
    if context_terms:
        parts.append(f"关系上下文：{'；'.join(context_terms[:20])}")
    parts.append("领域：甘肃科技金融")
    return "；".join(parts)


def load_entities() -> List[Dict[str, object]]:
    uri = os.getenv("GTF_NEO4J_URI")
    user = os.getenv("GTF_NEO4J_USER")
    password = os.getenv("GTF_NEO4J_PASSWORD")
    database = os.getenv("GTF_NEO4J_DATABASE", "neo4j")
    if not (uri and user and password):
        raise EmbeddingUnavailable("Neo4j env vars are incomplete")
    query = """
    MATCH (n)
    WHERE coalesce(n.name, '') <> ''
    OPTIONAL MATCH (n)-[r]-(m)
    WITH n, elementId(n) AS element_id, labels(n) AS labels, properties(n) AS props,
         collect(DISTINCT {rel: type(r), neighbor: m.name, neighbor_labels: labels(m)}) AS rels
    RETURN element_id, n.name AS name, labels, props, rels[0..20] AS rels
    """
    rows: List[Dict[str, object]] = []
    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        with driver.session(database=database) as session:
            for record in session.run(query):
                labels = list(record["labels"] or [])
                plain = [_plain_label(label) for label in labels]
                if not any(label in CORE_LABELS for label in plain):
                    continue
                name = str(record["name"] or "").strip()
                if not name:
                    continue
                props = dict(record["props"] or {})
                rels = [dict(item) for item in (record["rels"] or [])]
                aliases = _generated_aliases(name, plain, props)
                context_terms = _context_terms(props, rels)
                rows.append(
                    {
                        "entity_id": props.get("id")
                        or props.get("entityId")
                        or props.get("policyId")
                        or props.get("productId")
                        or props.get("enterpriseId")
                        or f"neo4j_element_{record['element_id']}",
                        "neo4j_element_id": record["element_id"],
                        "name": name,
                        "labels": plain,
                        "aliases": aliases,
                        "relation_contexts": context_terms,
                        "embedding_text": _entity_text(name, labels, aliases, context_terms),
                        "source": "neo4j",
                    }
                )
    finally:
        driver.close()
    return rows


def _write_report(path: Path, lines: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_index() -> int:
    cfg = get_embedding_config()
    out_dir = Path(str(cfg["entity_index_dir"]))
    report_path = out_dir / "build_report.md"
    metadata_path = out_dir / "metadata.jsonl"
    index_path = out_dir / "faiss.index"
    report = [
        "# Entity Embedding Index 构建报告",
        f"- 构建时间：{datetime.now().isoformat(timespec='seconds')}",
        f"- 项目根目录：{PROJECT_ROOT}",
        f"- Neo4j URI：{os.getenv('GTF_NEO4J_URI', '<EMPTY>')}",
        f"- embedding 后端：{cfg['embedding_backend']}",
        f"- embedding 模型名：{cfg['embedding_model_name'] or '<EMPTY>'}",
        f"- FAISS index 路径：{index_path}",
        f"- metadata 路径：{metadata_path}",
        "",
    ]
    try:
        rows = load_entities()
        counts = Counter(label for row in rows for label in row.get("labels", []))
        report.extend(
            [
                f"- 读取实体总数：{len(rows)}",
                "## 标签计数",
                *[f"- {label}: {count}" for label, count in sorted(counts.items())],
                "",
            ]
        )
        if not rows:
            raise EmbeddingUnavailable("no Neo4j entities collected")
        vectors = embed_texts([str(row["embedding_text"]) for row in rows])
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
    except Exception as exc:
        report.extend(["## 构建结果", "- 状态：未生成索引", f"- 原因：{exc}"])
        _write_report(report_path, report)
        print(f"[entity embedding build failed] {exc}", file=sys.stderr)
        return 1


def main() -> None:
    argparse.ArgumentParser().parse_args()
    raise SystemExit(build_index())


if __name__ == "__main__":
    main()
