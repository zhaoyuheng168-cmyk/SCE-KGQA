# -*- coding: utf-8 -*-
"""
KAG evidence-card autonomous diagnostic evaluation.

Purpose:
- Do NOT modify Neo4j.
- Do NOT modify main QA.
- Read V1-U light evidence cards / qa chunks.
- Parse Structured Fact from evidence cards.
- Answer generated special testset using KAG evidence layer only.
"""

import argparse
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd


DELIVERABLE_ROOT = Path(__file__).resolve().parents[3]
RUNTIME_DATA = DELIVERABLE_ROOT / "runtime_data"
BASE = DELIVERABLE_ROOT
OUT_DIR = DELIVERABLE_ROOT / "experiments/results/generated_special_eval"
OUT_DIR.mkdir(parents=True, exist_ok=True)

EVIDENCE_DIRS = [
    RUNTIME_DATA / "evidence/unstructured_extract_staging/batch2_60/kag_sync/light_evidence_cards",
    RUNTIME_DATA / "evidence/unstructured_extract_staging/batch3_large_90/kag_sync/light_evidence_cards",
]

# Full structured evidence generated from nodes_kag.json + edges_kag.json.
STRUCTURED_EVIDENCE_DIRS = [
    RUNTIME_DATA / "evidence/structured_evidence_docs_full_auto/structured_evidence_docs_full_auto/nodes",
    RUNTIME_DATA / "evidence/structured_evidence_docs_full_auto/structured_evidence_docs_full_auto/relations",
    RUNTIME_DATA / "evidence/structured_evidence_docs",
]

GRAPH_NODE_PATH = RUNTIME_DATA / "kag_runtime/nodes_kag.json"
GRAPH_EDGE_PATH = RUNTIME_DATA / "kag_runtime/edges_kag.json"

QA_CHUNK_PATHS = [
    RUNTIME_DATA / "evidence/unstructured_extract_staging/outputs/v1u_stage1_qa_chunks.jsonl",
]


STOPWORDS = set("""
的 了 和 是 在 对 为 与 及 或 等 中 由 向 将 以 于 从 该 其 并 已 有 进行 提出 支持 服务 企业 科技 金融 甘肃 什么 哪些 哪家 多少 采用 模式 方案
""".split())


def norm(s):
    s = str(s or "")
    s = re.sub(r"\s+", "", s)
    s = s.replace("（", "(").replace("）", ")").replace("“", "").replace("”", "")
    return s


def name_match(a, b):
    aa, bb = norm(a), norm(b)
    return bool(aa and bb and (aa in bb or bb in aa))


def tokenize(text):
    text = str(text or "")
    toks = []

    for m in re.findall(r"[A-Za-z0-9]+(?:\.[A-Za-z0-9]+)?", text):
        if len(m) >= 2:
            toks.append(m.lower())

    for block in re.findall(r"[\u4e00-\u9fff]+", text):
        if len(block) <= 1:
            continue
        if len(block) <= 8 and block not in STOPWORDS:
            toks.append(block)
        for i in range(len(block) - 1):
            gram = block[i:i+2]
            if gram not in STOPWORDS:
                toks.append(gram)
        for i in range(len(block) - 2):
            gram = block[i:i+3]
            if gram not in STOPWORDS:
                toks.append(gram)

    return toks


def load_corpus():
    docs = []

    # 1) V1-U light evidence cards.
    for d in EVIDENCE_DIRS:
        if not d.exists():
            continue
        for p in sorted(d.glob("*.txt")):
            text = p.read_text(encoding="utf-8", errors="ignore")
            docs.append({
                "doc_id": str(p.relative_to(BASE)),
                "title": p.name,
                "text": text,
                "kind": "light_evidence_card",
            })

    # 2) Full structured evidence chunks.
    for d in STRUCTURED_EVIDENCE_DIRS:
        if not d.exists():
            continue
        kind = "structured_full_auto_relation" if d.name == "relations" else "structured_full_auto_node"
        for p in sorted(d.rglob("*.txt")):
            text = p.read_text(encoding="utf-8", errors="ignore")
            docs.append({
                "doc_id": str(p.relative_to(BASE)),
                "title": p.name,
                "text": text,
                "kind": kind,
            })

    # 3) V1-U QA chunks.
    for p in QA_CHUNK_PATHS:
        if not p.exists():
            continue
        with open(p, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                text = obj.get("text", "") or obj.get("content", "") or ""
                title = obj.get("title", "") or obj.get("doc_title", "") or f"qa_chunk_{idx}"
                docs.append({
                    "doc_id": obj.get("chunk_id", f"{p.name}:{idx}"),
                    "title": title,
                    "text": text,
                    "kind": "qa_chunk",
                })

    return docs


FACT_RE = re.compile(
    r'(?P<from_type>[A-Za-z]+)「(?P<from_name>[^」]+)」\s*-\[(?P<edge_type>[A-Za-z]+)(?:[^\]]*)\]->\s*(?P<to_type>[A-Za-z]+)「(?P<to_name>[^」]+)」'
)


def _as_list(obj):
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        for k in ("nodes", "edges", "data", "items", "records"):
            if isinstance(obj.get(k), list):
                return obj.get(k)
    return []


def _pick(d, keys, default=""):
    if not isinstance(d, dict):
        return default
    for k in keys:
        v = d.get(k)
        if v not in (None, ""):
            return v
    return default


def _short_type(t):
    t = str(t or "").strip().strip("`")
    if "." in t:
        t = t.split(".")[-1]
    return t


def _load_graph_json_facts():
    """
    从 nodes_kag.json + edges_kag.json 直接构建完整结构化事实。
    这样 V8 的本地 KAG fallback 不再只依赖 light evidence cards。
    """
    facts = []

    if not GRAPH_NODE_PATH.exists() or not GRAPH_EDGE_PATH.exists():
        return facts

    try:
        nodes_obj = json.loads(GRAPH_NODE_PATH.read_text(encoding="utf-8"))
        edges_obj = json.loads(GRAPH_EDGE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return facts

    nodes = _as_list(nodes_obj)
    edges = _as_list(edges_obj)

    id_to_name = {}
    id_to_type = {}

    for n in nodes:
        if not isinstance(n, dict):
            continue

        props = n.get("properties", {}) if isinstance(n.get("properties", {}), dict) else {}

        nid = _pick(n, ["id", "node_id", "nodeId", "spgId", "bizId", "entityId"]) or _pick(props, ["id", "node_id", "nodeId", "spgId", "bizId", "entityId"])
        name = _pick(n, ["name", "title", "entityName"]) or _pick(props, ["name", "title", "entityName"])
        ntype = _pick(n, ["type", "label", "entityType", "category"]) or _pick(props, ["type", "label", "entityType", "category"])

        labels = n.get("labels")
        if not ntype and isinstance(labels, list) and labels:
            ntype = labels[0]

        nid = str(nid or "").strip()
        if nid:
            id_to_name[nid] = str(name or nid).strip()
            id_to_type[nid] = _short_type(ntype)

    for e in edges:
        if not isinstance(e, dict):
            continue

        props = e.get("properties", {}) if isinstance(e.get("properties", {}), dict) else {}

        src = (
            _pick(e, ["from", "fromId", "source", "sourceId", "start", "startId", "src", "srcId"])
            or _pick(props, ["from", "fromId", "source", "sourceId", "start", "startId", "src", "srcId"])
        )
        dst = (
            _pick(e, ["to", "toId", "target", "targetId", "end", "endId", "dst", "dstId"])
            or _pick(props, ["to", "toId", "target", "targetId", "end", "endId", "dst", "dstId"])
        )
        edge_type = (
            _pick(e, ["type", "label", "relation", "relationType", "edgeType", "name"])
            or _pick(props, ["type", "label", "relation", "relationType", "edgeType", "name"])
        )

        src = str(src or "").strip()
        dst = str(dst or "").strip()
        edge_type = str(edge_type or "").strip()

        if not src or not dst or not edge_type:
            continue

        from_name = id_to_name.get(src, src)
        to_name = id_to_name.get(dst, dst)

        from_type = _short_type(
            _pick(e, ["fromType", "sourceType", "srcType", "startType"])
            or _pick(props, ["fromType", "sourceType", "srcType", "startType"])
            or id_to_type.get(src, "")
        )
        to_type = _short_type(
            _pick(e, ["toType", "targetType", "dstType", "endType"])
            or _pick(props, ["toType", "targetType", "dstType", "endType"])
            or id_to_type.get(dst, "")
        )

        raw = f'{from_type}「{from_name}」-[{edge_type}]->{to_type}「{to_name}」'

        facts.append({
            "from_type": from_type,
            "from_name": from_name,
            "edge_type": edge_type,
            "to_type": to_type,
            "to_name": to_name,
            "doc_id": str(GRAPH_EDGE_PATH.relative_to(BASE)),
            "title": "edges_kag.json",
            "kind": "structured_graph_json_full",
            "raw": raw,
        })

    return facts


def parse_facts(docs):
    facts = []
    seen = set()

    # 1) Parse explicit triple-style facts from light evidence cards / qa chunks.
    for doc in docs:
        text = doc["text"]
        for m in FACT_RE.finditer(text):
            fact = m.groupdict()
            fact["doc_id"] = doc["doc_id"]
            fact["title"] = doc["title"]
            fact["kind"] = doc["kind"]
            fact["raw"] = m.group(0)

            key = (
                fact.get("from_type", ""),
                fact.get("from_name", ""),
                fact.get("edge_type", ""),
                fact.get("to_type", ""),
                fact.get("to_name", ""),
            )
            if key not in seen:
                seen.add(key)
                facts.append(fact)

    # 2) Add complete structured graph facts from nodes_kag.json + edges_kag.json.
    for fact in _load_graph_json_facts():
        key = (
            fact.get("from_type", ""),
            fact.get("from_name", ""),
            fact.get("edge_type", ""),
            fact.get("to_type", ""),
            fact.get("to_name", ""),
        )
        if key not in seen:
            seen.add(key)
            facts.append(fact)

    return facts


def build_index(docs):
    doc_counts = []
    df = Counter()

    for doc in docs:
        full = "\n".join([doc.get("title", ""), doc.get("text", "")])
        counts = Counter(tokenize(full))
        doc_counts.append(counts)
        for t in counts:
            df[t] += 1

    return doc_counts, df


def retrieve(query, docs, doc_counts, df, topk=8):
    n = len(docs)
    q_counts = Counter(tokenize(query))
    scored = []

    for doc, counts in zip(docs, doc_counts):
        score = 0.0
        for t, qtf in q_counts.items():
            tf = counts.get(t, 0)
            if tf <= 0:
                continue
            idf = math.log((n + 1) / (df.get(t, 0) + 1)) + 1.0
            score += (1 + math.log(tf)) * idf * (1 + math.log(qtf))

        # 强化完整实体命中
        for entity in re.findall(r"[\u4e00-\u9fffA-Za-z0-9（）()]+(?:公司|银行|分行|方案|通知|贷款|贷)", query):
            if entity and entity in (doc.get("title", "") + doc.get("text", "")):
                score += 15.0

        if score > 0:
            scored.append((score, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:topk]


def unique(vals):
    out = []
    for v in vals:
        v = str(v or "").strip()
        if v and v not in out:
            out.append(v)
    return out


def facts_by_edge(facts, edge):
    return [f for f in facts if f.get("edge_type") == edge]


def answer_from_facts(qtype, subject, facts):
    subject = str(subject or "").strip()
    answers = []

    if qtype == "enterprise_loan_support":
        loan_to_ent = [
            f for f in facts_by_edge(facts, "loanToEnterprise")
            if name_match(f["to_name"], subject)
        ]
        loan_events = [f["from_name"] for f in loan_to_ent]
        for le in loan_events:
            for f in facts_by_edge(facts, "issuesLoan"):
                if name_match(f["to_name"], le):
                    answers.append(f["from_name"])

    elif qtype == "institution_loan_enterprise":
        issue_loan = [
            f for f in facts_by_edge(facts, "issuesLoan")
            if name_match(f["from_name"], subject)
        ]
        loan_events = [f["to_name"] for f in issue_loan]
        for le in loan_events:
            for f in facts_by_edge(facts, "loanToEnterprise"):
                if name_match(f["from_name"], le):
                    answers.append(f["to_name"])

    elif qtype == "freeqa_institution_product_overview":
        for f in facts_by_edge(facts, "providesProduct"):
            if name_match(f["from_name"], subject):
                answers.append(f["to_name"])

    elif qtype == "product_provider":
        for f in facts_by_edge(facts, "providesProduct"):
            if name_match(f["to_name"], subject):
                answers.append(f["from_name"])

    elif qtype == "policy_supports_product":
        for f in facts_by_edge(facts, "supports"):
            if name_match(f["from_name"], subject):
                answers.append(f["to_name"])

    elif qtype == "product_supported_by_policies":
        for f in facts_by_edge(facts, "supports"):
            if name_match(f["to_name"], subject):
                answers.append(f["from_name"])

    elif qtype == "agency_issues_policy":
        for f in facts_by_edge(facts, "issues"):
            if name_match(f["from_name"], subject):
                answers.append(f["to_name"])

    elif qtype == "policy_issued_by_agency":
        for f in facts_by_edge(facts, "issues"):
            if name_match(f["to_name"], subject):
                answers.append(f["from_name"])

    return unique(answers)


def format_answer(qtype, subject, answers):
    if not answers:
        return f"未从 KAG evidence cards 中解析到“{subject}”的明确答案。"

    joined = "、".join(answers)

    if qtype == "enterprise_loan_support":
        return f"根据 KAG evidence cards，{subject}获得贷款支持的金融机构包括：{joined}。"
    if qtype == "institution_loan_enterprise":
        return f"根据 KAG evidence cards，{subject}通过贷款事件支持的企业包括：{joined}。"
    if qtype == "freeqa_institution_product_overview":
        return f"根据 KAG evidence cards，{subject}提供的科技金融产品包括：{joined}。"
    if qtype == "product_provider":
        return f"根据 KAG evidence cards，{subject}由以下金融机构提供：{joined}。"
    if qtype == "policy_supports_product":
        return f"根据 KAG evidence cards，{subject}支持的科技金融产品或工具包括：{joined}。"
    if qtype == "product_supported_by_policies":
        return f"根据 KAG evidence cards，支持{subject}的政策包括：{joined}。"
    if qtype == "agency_issues_policy":
        return f"根据 KAG evidence cards，{subject}发布或制定的科技金融相关政策包括：{joined}。"
    if qtype == "policy_issued_by_agency":
        return f"根据 KAG evidence cards，{subject}由以下部门发布或制定：{joined}。"

    return f"根据 KAG evidence cards，{subject}相关答案包括：{joined}。"


def split_gold(s):
    return [x.strip() for x in str(s or "").split("||") if x.strip()]


def judge(answer, gold_items):
    ans = norm(answer)
    hits, misses = [], []
    for g in gold_items:
        if norm(g) in ans:
            hits.append(g)
        else:
            misses.append(g)
    return len(misses) == 0, hits, misses


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--name", default="kag_evidence_autonomous")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--topk", type=int, default=8)
    args = ap.parse_args()

    in_path = Path(args.input)
    if not in_path.is_absolute():
        in_path = BASE / in_path

    df = pd.read_csv(in_path).fillna("")
    if args.limit > 0:
        df = df.head(args.limit).copy()

    docs = load_corpus()
    facts = parse_facts(docs)
    doc_counts, doc_df = build_index(docs)

    print("[INFO] docs:", len(docs))
    print("[INFO] parsed facts:", len(facts))

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_csv = OUT_DIR / f"{args.name}_results_{ts}.csv"
    out_md = OUT_DIR / f"{args.name}_summary_{ts}.md"

    rows = []
    for i, r in df.iterrows():
        qid = str(r.get("question_id", f"Q{i+1:03d}"))
        question = str(r.get("question", "")).strip()
        qtype = str(r.get("question_type", "")).strip()
        subject = str(r.get("subject_name", "")).strip()
        gold = split_gold(r.get("gold_items", ""))

        scored = retrieve(question + " " + subject, docs, doc_counts, doc_df, topk=args.topk)
        top_doc_ids = " || ".join([f"{score:.2f}|{doc['doc_id']}" for score, doc in scored[:args.topk]])

        answers = answer_from_facts(qtype, subject, facts)
        answer = format_answer(qtype, subject, answers)

        ok, hits, misses = judge(answer, gold)

        print(f"[{len(rows)+1}/{len(df)}] {qid} {'PASS' if ok else 'FAIL'} {question}")
        if misses:
            print("  missing:", "||".join(misses))

        rows.append({
            "question_id": qid,
            "question": question,
            "question_type": qtype,
            "subject_name": subject,
            "gold_items": "||".join(gold),
            "kag_evidence_answer": answer,
            "kag_parsed_answers": "||".join(answers),
            "pass": int(ok),
            "hit_gold_items": "||".join(hits),
            "miss_gold_items": "||".join(misses),
            "top_docs": top_doc_ids,
            "answer_source": "kag_evidence_cards_autonomous",
        })

    res = pd.DataFrame(rows)
    res.to_csv(out_csv, index=False, encoding="utf-8-sig")

    total = len(res)
    passed = int(res["pass"].sum())
    acc = passed / total if total else 0

    lines = []
    lines.append(f"# KAG Evidence Autonomous Eval: {args.name}\n")
    lines.append(f"- input: `{in_path}`")
    lines.append(f"- docs: {len(docs)}")
    lines.append(f"- parsed_facts: {len(facts)}")
    lines.append(f"- total: {total}")
    lines.append(f"- passed: {passed}")
    lines.append(f"- failed: {total - passed}")
    lines.append(f"- accuracy: {acc:.4f}")
    lines.append(f"- results: `{out_csv}`\n")

    lines.append("## By question_type\n")
    if total:
        by = res.groupby("question_type")["pass"].agg(["count", "sum", "mean"]).reset_index()
        by.columns = ["question_type", "total", "passed", "accuracy"]
        lines.append(by.to_markdown(index=False))

    failed = res[res["pass"] == 0]
    lines.append("\n## Failed cases\n")
    if len(failed):
        lines.append(failed[["question_id", "question", "question_type", "gold_items", "miss_gold_items", "kag_evidence_answer"]].to_markdown(index=False))
    else:
        lines.append("No failed cases.")

    out_md.write_text("\n".join(lines), encoding="utf-8")

    print("\n[DONE]")
    print("results:", out_csv)
    print("summary:", out_md)
    print(f"accuracy: {passed}/{total} = {acc:.4f}")


if __name__ == "__main__":
    main()
