#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Audit over-returned answers against declared KG relation paths.

This script does not run QA. It reads an existing prediction result file and
checks whether predicted items, especially extra items not present in gold, are
valid under the source benchmark relation paths.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd
from neo4j import GraphDatabase


SEP_RE = re.compile(r"\|\||[；;，,\n\r]+")
NAMESPACE = os.getenv("GTF_NAMESPACE", "GansuTechFinanceDevV1Enhance")
NEO4J_URI = os.getenv("GTF_NEO4J_URI", "bolt://127.0.0.1:7688")
NEO4J_USER = os.getenv("GTF_NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("GTF_NEO4J_PASSWORD", "CHANGE_ME")
NEO4J_DATABASE = os.getenv("GTF_NEO4J_DATABASE", "neo4j")


def label(name: str) -> str:
    return f"`{NAMESPACE}.{name}`"


def split_items(value: object) -> List[str]:
    text = "" if value is None else str(value)
    if not text or text.lower() == "nan":
        return []
    items: List[str] = []
    for part in SEP_RE.split(text):
        item = part.strip().strip("。；;，,、 ")
        if item and item.lower() != "nan" and item not in items:
            items.append(item)
    return items


def norm(value: object) -> str:
    text = "" if value is None else str(value)
    text = text.strip()
    if not text or text.lower() == "nan":
        return ""
    return re.sub(r"\s+", "", text).replace("（", "(").replace("）", ")")


def parse_subject_parts(subject: object) -> List[str]:
    text = "" if subject is None else str(subject)
    if not text or text.lower() == "nan":
        return []
    return [x.strip() for x in text.split("/") if x.strip()]


def path_tokens(path: str) -> Optional[Tuple[List[str], List[str]]]:
    if not path or "openNeighborhood" in path or "{" in path:
        return None
    toks = [x.strip() for x in path.split("-") if x.strip()]
    if len(toks) < 3 or len(toks) % 2 == 0:
        return None
    labels = [x.replace("<", "").replace(">", "") for x in toks[0::2]]
    rels = toks[1::2]
    clean_rels: List[str] = []
    for rel in rels:
        clean_rels.append(rel.replace("<", "").replace(">", ""))
    return labels, clean_rels


def cypher_for_path(labels: Sequence[str], rels: Sequence[str], reverse: bool) -> str:
    pieces = []
    for i, lab in enumerate(labels):
        pieces.append(f"(n{i}:{label(lab)})")
        if i < len(rels):
            rel = rels[i]
            if reverse:
                pieces.append(f"<-[:{rel}]-")
            else:
                pieces.append(f"-[:{rel}]->")
    chain = "".join(pieces)
    return (
        f"MATCH {chain}\n"
        "WHERE n0.name = $start AND n" + str(len(labels) - 1) + ".name = $end\n"
        "RETURN 1 AS ok LIMIT 1"
    )


class PathAuditor:
    def __init__(self) -> None:
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        self.cache: Dict[Tuple[str, str, str, bool], bool] = {}

    def close(self) -> None:
        self.driver.close()

    def exists_path(self, path: str, start: str, end: str) -> bool:
        parsed = path_tokens(path)
        if parsed is None or not start or not end:
            return False
        labels, rels = parsed
        for reverse in (False, True):
            key = (path, norm(start), norm(end), reverse)
            if key in self.cache:
                if self.cache[key]:
                    return True
                continue
            cypher = cypher_for_path(labels, rels, reverse)
            with self.driver.session(database=NEO4J_DATABASE) as session:
                ok = bool(session.run(cypher, {"start": start, "end": end}).single())
            self.cache[key] = ok
            if ok:
                return True
        return False

    def exists_open_path(self, valid_paths: Iterable[str], subject: str, item: str) -> Tuple[bool, str]:
        for path in valid_paths:
            if self.exists_path(path, subject, item):
                return True, path
        return False, ""

    def exists_cypher(self, cypher: str, params: Dict[str, str]) -> bool:
        key = ("RAW", cypher, "|".join(f"{k}={norm(v)}" for k, v in sorted(params.items())), False)
        if key in self.cache:
            return self.cache[key]
        with self.driver.session(database=NEO4J_DATABASE) as session:
            ok = bool(session.run(cypher, params).single())
        self.cache[key] = ok
        return ok

    def exists_target_aware(self, row: pd.Series, item: str) -> Tuple[bool, str]:
        """Validate paths where the answer target is not necessarily the last node."""
        path = str(row.get("relation_path", "") or "")
        parts = subject_candidates(row)
        target_type = str(row.get("target_type", "") or "")

        if target_type != "Enterprise" or len(parts) < 2:
            return False, ""

        left, right = parts[0], parts[1]
        if path == "FinancialProduct-servesEnterprise-Enterprise-belongsToIndustry-IndustrySegment":
            cypher = f"""
            MATCH (fp:{label('FinancialProduct')})-[:servesEnterprise]->(e:{label('Enterprise')})-[:belongsToIndustry]->(i:{label('IndustrySegment')})
            WHERE fp.name = $left AND e.name = $item AND i.name = $right
            RETURN 1 AS ok LIMIT 1
            """
            return self.exists_cypher(cypher, {"left": left, "right": right, "item": item}), path

        if path == "FinancialProduct-servesEnterprise-Enterprise-locatedIn-Region":
            cypher = f"""
            MATCH (fp:{label('FinancialProduct')})-[:servesEnterprise]->(e:{label('Enterprise')})-[:locatedIn]->(r:{label('Region')})
            WHERE fp.name = $left AND e.name = $item AND r.name = $right
            RETURN 1 AS ok LIMIT 1
            """
            return self.exists_cypher(cypher, {"left": left, "right": right, "item": item}), path

        if path == "FinancialProduct<-potentiallyMatchesProduct-Enterprise-belongsToIndustry-IndustrySegment":
            cypher = f"""
            MATCH (e:{label('Enterprise')})-[:potentiallyMatchesProduct]->(fp:{label('FinancialProduct')}),
                  (e)-[:belongsToIndustry]->(i:{label('IndustrySegment')})
            WHERE fp.name = $left AND e.name = $item AND i.name = $right
            RETURN 1 AS ok LIMIT 1
            """
            return self.exists_cypher(cypher, {"left": left, "right": right, "item": item}), path

        if path == "FinancialProduct<-potentiallyMatchesProduct-Enterprise-locatedIn-Region":
            cypher = f"""
            MATCH (e:{label('Enterprise')})-[:potentiallyMatchesProduct]->(fp:{label('FinancialProduct')}),
                  (e)-[:locatedIn]->(r:{label('Region')})
            WHERE fp.name = $left AND e.name = $item AND r.name = $right
            RETURN 1 AS ok LIMIT 1
            """
            return self.exists_cypher(cypher, {"left": left, "right": right, "item": item}), path

        if path == "FinancialProduct<-potentiallyMatchesProduct-Enterprise-hasFeature-QualificationCreditFeature":
            cypher = f"""
            MATCH (e:{label('Enterprise')})-[:potentiallyMatchesProduct]->(fp:{label('FinancialProduct')}),
                  (e)-[:hasFeature]->(f:{label('QualificationCreditFeature')})
            WHERE fp.name = $left AND e.name = $item AND f.name = $right
            RETURN 1 AS ok LIMIT 1
            """
            return self.exists_cypher(cypher, {"left": left, "right": right, "item": item}), path

        if path == "Policy<-potentiallyMatchesPolicy-Enterprise-belongsToIndustry-IndustrySegment":
            cypher = f"""
            MATCH (e:{label('Enterprise')})-[:potentiallyMatchesPolicy]->(p:{label('Policy')}),
                  (e)-[:belongsToIndustry]->(i:{label('IndustrySegment')})
            WHERE p.name = $left AND e.name = $item AND i.name = $right
            RETURN 1 AS ok LIMIT 1
            """
            return self.exists_cypher(cypher, {"left": left, "right": right, "item": item}), path

        if path == "Policy<-potentiallyMatchesPolicy-Enterprise-locatedIn-Region":
            cypher = f"""
            MATCH (e:{label('Enterprise')})-[:potentiallyMatchesPolicy]->(p:{label('Policy')}),
                  (e)-[:locatedIn]->(r:{label('Region')})
            WHERE p.name = $left AND e.name = $item AND r.name = $right
            RETURN 1 AS ok LIMIT 1
            """
            return self.exists_cypher(cypher, {"left": left, "right": right, "item": item}), path

        return False, ""


def candidate_paths(row: pd.Series) -> List[str]:
    valid = split_items(row.get("valid_relation_paths", ""))
    if valid:
        return [x for x in valid if path_tokens(x) is not None]
    rel_path = str(row.get("relation_path", "") or "")
    return [rel_path] if path_tokens(rel_path) is not None else []


def subject_candidates(row: pd.Series) -> List[str]:
    parts = parse_subject_parts(row.get("subject", ""))
    if parts:
        return parts
    return [str(row.get("subject", "") or "").strip()]


def audit_rows(
    merged: pd.DataFrame,
    out_dir: Path,
    max_rows: int,
    max_items_per_row: int,
    paper_modes: Sequence[str],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    auditor = PathAuditor()
    detail_rows: List[Dict[str, object]] = []
    try:
        work = merged.copy()
        work["over_return"] = work["pred_count"].fillna(0) - work["gold_count"].fillna(0)
        work = work[work["paper_metric_mode"].isin(paper_modes)]
        work = work.sort_values(["over_return", "pred_count"], ascending=False)
        if max_rows > 0:
            work = work.head(max_rows)

        for _, row in work.iterrows():
            gold = {norm(x) for x in split_items(row.get("gold_items", ""))}
            pred = split_items(row.get("pred_items", ""))
            paths = candidate_paths(row)
            subjects = subject_candidates(row)
            checked = 0
            for item in pred:
                if max_items_per_row > 0 and checked >= max_items_per_row:
                    break
                checked += 1
                in_gold = norm(item) in gold
                valid = False
                matched_path = ""
                ok, path = auditor.exists_target_aware(row, item)
                if ok:
                    valid = True
                    matched_path = path
                else:
                    for subject in subjects:
                        ok, path = auditor.exists_open_path(paths, subject, item)
                        if ok:
                            valid = True
                            matched_path = path
                            break
                if in_gold or not in_gold:
                    detail_rows.append(
                        {
                            "question_id": row.get("question_id", ""),
                            "category": row.get("category", ""),
                            "paper_metric_mode": row.get("paper_metric_mode", ""),
                            "question": row.get("question", ""),
                            "relation_path": row.get("relation_path", ""),
                            "subject": row.get("subject", ""),
                            "pred_item": item,
                            "in_gold": in_gold,
                            "path_valid": valid,
                            "matched_path": matched_path,
                            "gold_count": row.get("gold_count", ""),
                            "pred_count": row.get("pred_count", ""),
                            "hit_count": row.get("hit_count", ""),
                            "final_route": row.get("final_route", ""),
                        }
                    )
    finally:
        auditor.close()

    detail_path = out_dir / "overreturned_path_validity_detail.csv"
    with detail_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(detail_rows[0].keys()) if detail_rows else ["question_id"])
        writer.writeheader()
        writer.writerows(detail_rows)

    if detail_rows:
        d = pd.DataFrame(detail_rows)
        rows = []
        for key, sub in d.groupby("paper_metric_mode"):
            extra = sub[~sub["in_gold"]]
            rows.append(
                {
                    "paper_metric_mode": key,
                    "checked_items": len(sub),
                    "gold_items_seen": int(sub["in_gold"].sum()),
                    "extra_items_seen": len(extra),
                    "extra_path_valid": int(extra["path_valid"].sum()) if len(extra) else 0,
                    "extra_path_valid_rate": float(extra["path_valid"].mean()) if len(extra) else 0.0,
                }
            )
        pd.DataFrame(rows).to_csv(out_dir / "overreturned_path_validity_summary.csv", index=False, encoding="utf-8-sig")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--metrics-rows", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--max-rows", type=int, default=30)
    parser.add_argument("--max-items-per-row", type=int, default=80)
    parser.add_argument(
        "--paper-modes",
        default="open_core_recall_relation_valid_proxy,core_recall_set_multihop,core_recall_set_rule",
        help="Comma-separated paper_metric_mode values to audit.",
    )
    args = parser.parse_args()

    source = pd.read_csv(args.source)
    metrics = pd.read_csv(args.metrics_rows)
    merged = metrics.merge(
        source[
            [
                "question_id",
                "subject",
                "subject_type",
                "target_type",
                "relation_path",
                "valid_relation_paths",
                "allow_extra_items",
                "complete_gold",
            ]
        ],
        on="question_id",
        how="left",
    )
    modes = [x.strip() for x in args.paper_modes.split(",") if x.strip()]
    audit_rows(merged, args.out_dir, args.max_rows, args.max_items_per_row, modes)
    print(f"wrote {args.out_dir / 'overreturned_path_validity_detail.csv'}")
    print(f"wrote {args.out_dir / 'overreturned_path_validity_summary.csv'}")


if __name__ == "__main__":
    main()
