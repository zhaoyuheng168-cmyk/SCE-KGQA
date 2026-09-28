# -*- coding: utf-8 -*-
"""
真实自由问答 relation-valid 分层指标分析 v2

用途：
- 不调用 V8
- 不调用 LLM
- 不重新跑 1800
- 只读取已有评测 CSV + nodes_kag.json + edges_kag.json
- 判断 pred_items 中 gold 外的答案项是否仍有图谱关系证据支撑

核心口径：
1. strict：只认 gold_items_eval。
2. relation-valid：如果预测项在 gold 中，或者预测项和 subject 之间存在图谱直接边/受控多跳路径，则认为该预测项有效。
3. Top-K：只看预测列表前 K 项。
"""

import json
import re
from pathlib import Path
from collections import defaultdict, deque

import pandas as pd


BASE = Path("/root/work/GansuTechFinance_KGQA_RELEASE_RUNTIME")
RESULT_CSV = BASE / "app/retrieval_only/tests/results/真实自由问答测试集_v1评测结果/真实自由问答测试集_v1评测结果.csv"
NODES_JSON = BASE / "app/builder/data/nodes_kag.json"
EDGES_JSON = BASE / "app/builder/data/edges_kag.json"

OUT_DIR = BASE / "app/retrieval_only/tests/results/真实自由问答测试集_v1评测结果/relation_valid_v2"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def norm(s):
    s = str(s or "")
    s = re.sub(r"\s+", "", s)
    s = s.replace("（", "(").replace("）", ")")
    s = s.replace("“", "").replace("”", "").replace('"', "")
    return s.strip()


def split_items(x):
    """
    兼容多种分隔符：
    || ｜｜ 、 ， , ; ；
    """
    x = str(x or "").strip()
    if not x or x.lower() == "nan":
        return []
    # 先统一常见分隔符
    x = x.replace("｜｜", "||").replace("｜", "||")
    parts = re.split(r"\|\||[、,，;；]\s*", x)
    out = []
    for p in parts:
        p = str(p or "").strip()
        if p and p not in out:
            out.append(p)
    return out


def pick_col(df, candidates, required=False):
    for c in candidates:
        if c in df.columns:
            return c
    if required:
        raise RuntimeError(f"Cannot find required column from {candidates}. Available columns={list(df.columns)}")
    return None


def short_type(t):
    t = str(t or "").strip().strip("`")
    if "." in t:
        return t.split(".")[-1]
    return t


def load_graph():
    print(f"[INFO] load nodes: {NODES_JSON}")
    print(f"[INFO] load edges: {EDGES_JSON}")

    nodes = json.loads(NODES_JSON.read_text(encoding="utf-8"))
    edges = json.loads(EDGES_JSON.read_text(encoding="utf-8"))

    id_to_name = {}
    id_to_type = {}
    name_to_ids = defaultdict(set)
    adj = defaultdict(list)

    for n in nodes:
        if not isinstance(n, dict):
            continue
        nid = str(n.get("id", "") or "").strip()
        name = str(n.get("name", "") or n.get("properties", {}).get("name", "") or "").strip()
        ntype = str(
            n.get("label", "")
            or n.get("type", "")
            or n.get("properties", {}).get("label", "")
            or n.get("properties", {}).get("type", "")
            or ""
        ).strip()
        ntype = short_type(ntype)
        if not nid:
            continue
        id_to_name[nid] = name
        id_to_type[nid] = ntype
        if name:
            name_to_ids[name].add(nid)
            name_to_ids[norm(name)].add(nid)

    for e in edges:
        if not isinstance(e, dict):
            continue
        src = str(e.get("from", "") or e.get("source", "") or e.get("start", "") or "").strip()
        dst = str(e.get("to", "") or e.get("target", "") or e.get("end", "") or "").strip()
        rel = str(
            e.get("type")
            or e.get("label")
            or e.get("relation")
            or e.get("properties", {}).get("relationType")
            or ""
        ).strip()

        if not src or not dst or not rel:
            continue

        src_type = short_type(e.get("fromType") or e.get("sourceType") or id_to_type.get(src, ""))
        dst_type = short_type(e.get("toType") or e.get("targetType") or id_to_type.get(dst, ""))

        item = {
            "src": src,
            "dst": dst,
            "rel": rel,
            "src_type": src_type or id_to_type.get(src, ""),
            "dst_type": dst_type or id_to_type.get(dst, ""),
            "src_name": id_to_name.get(src, ""),
            "dst_name": id_to_name.get(dst, ""),
        }
        adj[src].append({**item, "direction": "out", "other": dst})
        adj[dst].append({**item, "direction": "in", "other": src})

    print(f"[INFO] graph loaded: nodes={len(id_to_name)}, edge_nodes={len(adj)}")
    return id_to_name, id_to_type, name_to_ids, adj


def get_ids_by_name(name, name_to_ids):
    """
    优先精确匹配，其次规范化匹配，再做轻量包含匹配。
    包含匹配不要太激进，避免近名误判。
    """
    name = str(name or "").strip()
    if not name:
        return set()

    ids = set()
    ids |= set(name_to_ids.get(name, set()))
    ids |= set(name_to_ids.get(norm(name), set()))
    if ids:
        return ids

    n_name = norm(name)
    if len(n_name) >= 4:
        for k, v in name_to_ids.items():
            nk = norm(k)
            if nk and (nk == n_name or nk in n_name or n_name in nk):
                ids |= set(v)

    return ids


def edge_valid(subject, pred, name_to_ids, adj):
    sids = get_ids_by_name(subject, name_to_ids)
    pids = get_ids_by_name(pred, name_to_ids)
    if not sids or not pids:
        return False, ""

    for sid in sids:
        for e in adj.get(sid, []):
            if e.get("other") in pids:
                return True, f"direct:{e.get('rel')}"

    return False, ""


def controlled_path_valid(subject, pred, name_to_ids, adj, id_to_type, max_depth=3):
    """
    受控多跳证据，不是任意路径。
    允许典型 KGQA 语义链：
    - Policy -> supports -> Product -> servesEnterprise -> Enterprise -> Region/Industry/Feature
    - Policy -> targetsEnterprise -> Enterprise -> Region/Industry/Feature
    - Product -> servesEnterprise -> Enterprise -> Region/Industry/Feature
    - Institution -> providesProduct -> Product
    - Institution -> issuesLoan -> LoanEvent -> loanToEnterprise -> Enterprise
    - Enterprise <- loanToEnterprise <- LoanEvent <- issuesLoan <- Institution
    - Enterprise <- servesEnterprise <- Product
    - Enterprise -> hasFeature / locatedIn / belongsToIndustry
    """
    sids = get_ids_by_name(subject, name_to_ids)
    pids = get_ids_by_name(pred, name_to_ids)
    if not sids or not pids:
        return False, ""

    allowed_rels = {
        "supports",
        "providesProduct",
        "servesEnterprise",
        "targetsEnterprise",
        "hasFeature",
        "locatedIn",
        "belongsToIndustry",
        "issuesLoan",
        "loanToEnterprise",
        "potentiallyMatchesPolicy",
        "potentiallyMatchesProduct",
        "fitsEnterpriseFeature",
        "hasCoverageIndustry",
        "hasCoverageRegion",
        "issues",
    }

    # BFS，但是只允许白名单关系，深度最多 3。
    for sid in sids:
        q = deque()
        q.append((sid, [], 0))
        seen = {sid}
        while q:
            cur, path, depth = q.popleft()
            if depth >= max_depth:
                continue

            for e in adj.get(cur, []):
                rel = e.get("rel")
                nxt = e.get("other")
                if not nxt or rel not in allowed_rels:
                    continue

                new_path = path + [rel]
                if nxt in pids:
                    return True, "path:" + "->".join(new_path)

                if nxt not in seen:
                    seen.add(nxt)
                    q.append((nxt, new_path, depth + 1))

    return False, ""


def is_relation_valid(subject, pred, gold_set_norm, name_to_ids, adj, id_to_type):
    """
    pred 若在 gold 中，天然 valid；
    否则看图谱直接边或受控路径。
    """
    if norm(pred) in gold_set_norm:
        return True, "gold"

    ok, reason = edge_valid(subject, pred, name_to_ids, adj)
    if ok:
        return True, reason

    ok, reason = controlled_path_valid(subject, pred, name_to_ids, adj, id_to_type, max_depth=3)
    if ok:
        return True, reason

    return False, ""


def prf(hit, pred, gold):
    p = hit / pred if pred else 0.0
    r = hit / gold if gold else 0.0
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f


def summarize(df, name):
    total = len(df)
    pass_col = pick_col(df, ["passed", "pass", "is_pass", "question_pass"])
    if pass_col:
        qacc = pd.to_numeric(df[pass_col], errors="coerce").fillna(0).mean()
    else:
        qacc = float("nan")

    strict_hit = df["strict_hit_count"].sum()
    strict_pred = df["pred_count_calc"].sum()
    strict_gold = df["gold_count_calc"].sum()
    sp, sr, sf = prf(strict_hit, strict_pred, strict_gold)

    rv_valid = df["relation_valid_count"].sum()
    rv_pred = df["pred_count_calc"].sum()
    rvp = rv_valid / rv_pred if rv_pred else 0.0

    rv5_valid = df["relation_valid_at5_count"].sum()
    rv5_pred = df["pred_at5_count"].sum()
    rvp5 = rv5_valid / rv5_pred if rv5_pred else 0.0

    rv10_valid = df["relation_valid_at10_count"].sum()
    rv10_pred = df["pred_at10_count"].sum()
    rvp10 = rv10_valid / rv10_pred if rv10_pred else 0.0

    s = {
        "name": name,
        "total": total,
        "question_accuracy": qacc,
        "strict_precision": sp,
        "strict_recall": sr,
        "strict_f1": sf,
        "relation_valid_precision": rvp,
        "relation_valid_precision@5": rvp5,
        "relation_valid_precision@10": rvp10,
        "avg_pred_count": df["pred_count_calc"].mean() if total else 0,
        "avg_relation_valid_count": df["relation_valid_count"].mean() if total else 0,
    }
    return s


def main():
    if not RESULT_CSV.exists():
        raise RuntimeError(f"Missing result csv: {RESULT_CSV}")
    if not NODES_JSON.exists() or not EDGES_JSON.exists():
        raise RuntimeError("Missing nodes_kag.json or edges_kag.json")

    df = pd.read_csv(RESULT_CSV, encoding="utf-8-sig")
    print(f"[INFO] rows={len(df)}, cols={list(df.columns)}")

    id_col = pick_col(df, ["qid", "id", "question_id", "题号"])
    q_col = pick_col(df, ["question", "query", "问题"], required=True)
    cat_col = pick_col(df, ["category", "题型", "type"])
    subject_col = pick_col(df, ["system_subject", "subject", "subject_name", "主体"])
    gold_col = pick_col(df, ["gold_items_eval", "gold_items", "gold", "标准答案"], required=True)
    pred_col = pick_col(df, ["pred_items", "graph_answers", "answer_items", "预测答案"], required=True)
    final_route_col = pick_col(df, ["final_route"])
    answer_source_col = pick_col(df, ["answer_source"])
    intent_source_col = pick_col(df, ["intent_source"])

    id_to_name, id_to_type, name_to_ids, adj = load_graph()

    rows = []
    valid_items_rows = []

    for i, row in df.iterrows():
        qid = row.get(id_col, i) if id_col else i
        question = row.get(q_col, "")
        subject = row.get(subject_col, "") if subject_col else ""
        if not str(subject or "").strip():
            # 部分结果 CSV 可能 subject 为空，尝试从问题里找最长图谱实体。
            # 离线脚本不做复杂主体识别，只做轻量匹配。
            qn = norm(question)
            best = ""
            for name in name_to_ids.keys():
                if not isinstance(name, str):
                    continue
                nn = norm(name)
                if len(nn) >= 4 and nn in qn and len(nn) > len(norm(best)):
                    best = name
            subject = best

        gold_items = split_items(row.get(gold_col, ""))
        pred_items = split_items(row.get(pred_col, ""))

        gold_set_norm = {norm(x) for x in gold_items if norm(x)}
        strict_hits = [p for p in pred_items if norm(p) in gold_set_norm]

        rv_valid_items = []
        rv_reasons = []
        for rank, p in enumerate(pred_items, start=1):
            ok, reason = is_relation_valid(subject, p, gold_set_norm, name_to_ids, adj, id_to_type)
            if ok:
                rv_valid_items.append(p)
                rv_reasons.append(f"{p}=>{reason}")
                valid_items_rows.append({
                    "qid": qid,
                    "question": question,
                    "subject": subject,
                    "pred_item": p,
                    "rank": rank,
                    "valid": 1,
                    "reason": reason,
                })
            else:
                valid_items_rows.append({
                    "qid": qid,
                    "question": question,
                    "subject": subject,
                    "pred_item": p,
                    "rank": rank,
                    "valid": 0,
                    "reason": "",
                })

        pred_at5 = pred_items[:5]
        pred_at10 = pred_items[:10]

        rv_at5 = 0
        for p in pred_at5:
            ok, _ = is_relation_valid(subject, p, gold_set_norm, name_to_ids, adj, id_to_type)
            rv_at5 += int(ok)

        rv_at10 = 0
        for p in pred_at10:
            ok, _ = is_relation_valid(subject, p, gold_set_norm, name_to_ids, adj, id_to_type)
            rv_at10 += int(ok)

        new_row = row.to_dict()
        new_row.update({
            "qid_eval": qid,
            "subject_eval": subject,
            "gold_count_calc": len(gold_items),
            "pred_count_calc": len(pred_items),
            "strict_hit_count": len(strict_hits),
            "relation_valid_count": len(rv_valid_items),
            "relation_valid_precision_row": len(rv_valid_items) / len(pred_items) if pred_items else 0.0,
            "relation_valid_at5_count": rv_at5,
            "pred_at5_count": len(pred_at5),
            "relation_valid_precision@5_row": rv_at5 / len(pred_at5) if pred_at5 else 0.0,
            "relation_valid_at10_count": rv_at10,
            "pred_at10_count": len(pred_at10),
            "relation_valid_precision@10_row": rv_at10 / len(pred_at10) if pred_at10 else 0.0,
            "relation_valid_items": "||".join(rv_valid_items),
            "relation_valid_reasons": "||".join(rv_reasons[:50]),
        })
        rows.append(new_row)

    out = pd.DataFrame(rows)
    valid_detail = pd.DataFrame(valid_items_rows)

    # 总体和关键子集
    summaries = []
    summaries.append(summarize(out, "ALL"))

    if cat_col:
        for cat, g in out.groupby(cat_col, dropna=False):
            summaries.append(summarize(g, f"category={cat}"))

    if final_route_col:
        for route, g in out.groupby(final_route_col, dropna=False):
            summaries.append(summarize(g, f"final_route={route}"))

    # 开放泛关系关键子集
    if final_route_col:
        g = out[out[final_route_col].astype(str).str.contains("relation_json_generic_fallback", na=False)]
        if len(g):
            summaries.append(summarize(g, "SUBSET=relation_json_generic_fallback"))

    if cat_col:
        open_mask = out[cat_col].astype(str).str.contains("开放自由|研究型增强", regex=True, na=False)
        g = out[open_mask]
        if len(g):
            summaries.append(summarize(g, "SUBSET=open_and_research_generic"))

        closed_mask = ~out[cat_col].astype(str).str.contains("开放自由|研究型增强|边界拒答|歧义", regex=True, na=False)
        g = out[closed_mask]
        if len(g):
            summaries.append(summarize(g, "SUBSET=closed_templates"))

    summary_df = pd.DataFrame(summaries)

    # 输出
    out_csv = OUT_DIR / "relation_valid_per_question_v2.csv"
    detail_csv = OUT_DIR / "relation_valid_pred_item_detail_v2.csv"
    summary_csv = OUT_DIR / "relation_valid_summary_v2.csv"
    report_md = OUT_DIR / "relation_valid_summary_v2.md"

    out.to_csv(out_csv, index=False, encoding="utf-8-sig")
    valid_detail.to_csv(detail_csv, index=False, encoding="utf-8-sig")
    summary_df.to_csv(summary_csv, index=False, encoding="utf-8-sig")

    def pct(x):
        try:
            return f"{float(x) * 100:.2f}%"
        except Exception:
            return ""

    all_s = summary_df[summary_df["name"] == "ALL"].iloc[0]

    lines = []
    lines.append("# 真实自由问答 relation-valid 分层指标 v2\n")
    lines.append("## 总体指标\n")
    lines.append(f"- 总题数：{int(all_s['total'])}")
    lines.append(f"- 问题级准确率：{pct(all_s['question_accuracy'])}")
    lines.append(f"- Strict Precision：{pct(all_s['strict_precision'])}")
    lines.append(f"- Strict Recall：{pct(all_s['strict_recall'])}")
    lines.append(f"- Strict F1：{pct(all_s['strict_f1'])}")
    lines.append(f"- Relation-valid Precision：{pct(all_s['relation_valid_precision'])}")
    lines.append(f"- Relation-valid Precision@5：{pct(all_s['relation_valid_precision@5'])}")
    lines.append(f"- Relation-valid Precision@10：{pct(all_s['relation_valid_precision@10'])}")
    lines.append(f"- 平均预测项数：{all_s['avg_pred_count']:.2f}\n")

    lines.append("## 关键子集\n")
    show = summary_df[
        summary_df["name"].astype(str).str.contains(
            "SUBSET=|final_route=relation_json_generic_fallback|final_route=structured_graph_with_kag_evidence|final_route=rule_reasoning|final_route=structured\\+kag_plan|final_route=structured_graph_kag_planned_multihop",
            regex=True,
            na=False,
        )
    ].copy()

    lines.append("| 子集 | 题数 | QAcc | Strict P | Strict R | Strict F1 | Relation-valid P | RV P@5 | RV P@10 | Avg Pred |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for _, r in show.iterrows():
        lines.append(
            f"| {r['name']} | {int(r['total'])} | {pct(r['question_accuracy'])} | "
            f"{pct(r['strict_precision'])} | {pct(r['strict_recall'])} | {pct(r['strict_f1'])} | "
            f"{pct(r['relation_valid_precision'])} | {pct(r['relation_valid_precision@5'])} | "
            f"{pct(r['relation_valid_precision@10'])} | {r['avg_pred_count']:.2f} |"
        )

    lines.append("\n## 输出文件\n")
    lines.append(f"- per question：`{out_csv}`")
    lines.append(f"- pred item detail：`{detail_csv}`")
    lines.append(f"- summary：`{summary_csv}`")

    report_md.write_text("\n".join(lines), encoding="utf-8")

    print("\n===== DONE =====")
    print(f"report: {report_md}")
    print(f"summary_csv: {summary_csv}")
    print(f"per_question_csv: {out_csv}")
    print(f"pred_item_detail_csv: {detail_csv}")
    print("\n===== ALL SUMMARY =====")
    print(summary_df[summary_df["name"] == "ALL"].to_string(index=False))


if __name__ == "__main__":
    main()
