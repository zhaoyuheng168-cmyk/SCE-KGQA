# -*- coding: utf-8 -*-
"""
真实自由问答测试集 v1 批量评测脚本。

输入：
    app/tests/测试集/真实自由问答测试集_v1.csv

输出：
    app/retrieval_only/tests/results/真实自由问答测试集_v1评测结果/
        真实自由问答测试集_v1评测结果.csv
        真实自由问答测试集_v1评测报告.md
        raw_logs/
"""

from __future__ import annotations

import csv
import os
import re
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ANSWER_SCRIPT = PROJECT_ROOT / "app/retrieval_only/scripts/answer_hybrid_v8_graph_kag_fallback.py"
DEFAULT_TEST_CSV = PROJECT_ROOT / "app/tests/测试集/真实自由问答测试集_v1.csv"
TEST_CSV = Path(os.environ.get("EVAL_TEST_CSV", str(DEFAULT_TEST_CSV)))
if not TEST_CSV.is_absolute():
    TEST_CSV = PROJECT_ROOT / TEST_CSV
MAX_WORKERS = int(os.environ.get("EVAL_WORKERS", "4"))
TIMEOUT_SECONDS = int(os.environ.get("EVAL_TIMEOUT", "180"))
EVAL_LIMIT = int(os.environ.get("EVAL_LIMIT", "0"))
RESUME_EXISTING_RAW = str(os.environ.get("EVAL_RESUME_EXISTING_RAW", "")).strip().lower() in {
    "1",
    "true",
    "yes",
    "y",
}

RESULT_DIR_NAME = os.environ.get("EVAL_RESULT_DIR_NAME", "真实自由问答测试集_v1评测结果")
if EVAL_LIMIT > 0:
    RESULT_DIR_NAME = f"真实自由问答测试集_v1前{EVAL_LIMIT}题冒烟评测结果"

OUT_DIR = PROJECT_ROOT / "app/retrieval_only/tests/results" / RESULT_DIR_NAME
RAW_DIR = OUT_DIR / "raw_logs"
OUT_CSV = OUT_DIR / f"{RESULT_DIR_NAME}.csv"
OUT_MD = OUT_DIR / f"{RESULT_DIR_NAME}.md"

SYSTEM_REFUSAL_PATTERNS = [
    "无法回答",
    "不能回答",
    "未找到",
    "没有找到",
    "没有检索到",
    "当前图谱中未找到",
    "当前知识库中未找到",
    "不在当前图谱",
    "不在当前知识库",
    "证据不足",
    "无法从当前",
    "超出当前",
]


def _neo4j_endpoint():
    uri = os.environ.get("GTF_NEO4J_URI", "bolt://127.0.0.1:7688")
    parsed = urlparse(uri)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 7687
    return uri, host, port


def check_neo4j_preflight():
    if str(os.environ.get("GTF_SKIP_NEO4J_PREFLIGHT", "")).strip().lower() in {"1", "true", "yes"}:
        print("[WARN] GTF_SKIP_NEO4J_PREFLIGHT=1，跳过 Neo4j 预检。")
        return
    uri, host, port = _neo4j_endpoint()
    try:
        with socket.create_connection((host, port), timeout=5):
            return
    except OSError as e:
        raise RuntimeError(
            f"Neo4j 预检失败：无法连接 {uri} ({host}:{port})。"
            "请先运行 scripts/start_services.sh 并 source scripts/加载运行环境变量.sh，"
            "确认服务可用后再跑批量评测。"
        ) from e


def read_rows(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def norm_text(s: str) -> str:
    s = str(s or "")
    s = s.replace("\ufeff", "")
    s = s.replace("“", "").replace("”", "").replace('"', "").replace("'", "")
    s = re.sub(r"\s+", "", s)
    s = s.replace("（", "(").replace("）", ")")
    for ch in ["。", "，", ",", "、", "；", ";", "：", ":", "《", "》", "【", "】"]:
        s = s.replace(ch, "")
    return s.lower()


def split_items(s: str):
    s = str(s or "").strip()
    if not s or s == "拒答":
        return []
    parts = re.split(r"\|\||\||;|；|\n", s)
    out = []
    for x in parts:
        x = x.strip()
        if x and x not in out:
            out.append(x)
    return out


def extract_section(text: str, name: str) -> str:
    pat = rf"===== {re.escape(name)} =====\n(.*?)(?=\n===== |\Z)"
    m = re.search(pat, text or "", flags=re.S)
    return m.group(1).strip() if m else ""


def extract_meta(raw: str):
    meta = {}
    keys = [
        "query", "question_type", "subject", "route", "intent_source",
        "final_route", "answer_source", "kag_used", "graph_answers", "kag_answers",
    ]
    for key in keys:
        m = re.search(rf"^{key}\s*=\s*(.*)$", raw or "", flags=re.M)
        if m:
            meta[key] = m.group(1).strip()
    meta["answer_section"] = extract_section(raw, "ANSWER")
    meta["cypher_section"] = extract_section(raw, "CYPHER")
    meta["kag_evidence_answer"] = extract_section(raw, "KAG EVIDENCE ANSWER")
    meta["kag_evidence"] = extract_section(raw, "KAG EVIDENCE")
    return meta


def extract_pred_items(meta):
    items = []
    for key in ["graph_answers", "kag_answers"]:
        items.extend(split_items(meta.get(key, "")))

    if not items:
        ans = meta.get("answer_section", "")
        m = re.search(r"包括[:：](.*?)(?:。|\n|$)", ans)
        if m:
            tmp = m.group(1).replace("、", "||").replace("，", "||").replace(",", "||")
            items.extend(split_items(tmp))

    seen = set()
    out = []
    for x in items:
        nx = norm_text(x)
        if nx and nx not in seen:
            seen.add(nx)
            out.append(x)
    return out


def parse_bool_flag(x) -> bool:
    """Parse common yes/no style flags from CSV safely."""
    s = str(x).strip().lower()
    return s in {"1", "true", "yes", "y", "是", "对", "需要", "should_refuse"}


def system_refused(text: str) -> bool:
    return any(p in text for p in SYSTEM_REFUSAL_PATTERNS)


def run_one(idx: int, row: dict):
    question = str(row.get("question", "")).strip()
    should_refuse = parse_bool_flag(row.get("should_refuse", "0"))
    gold_items = split_items(row.get("gold_items", ""))

    result = {
        "row_index": idx,
        "question_id": row.get("question_id", ""),
        "question": question,
        "category": row.get("category", ""),
        "difficulty": row.get("difficulty", ""),
        "relation_path": row.get("relation_path", ""),
        "should_refuse": int(should_refuse),
        "gold_items_eval": "||".join(gold_items),
        "gold_count": len(gold_items),
        "error": "",
    }

    raw_file = RAW_DIR / f"{idx + 1:04d}_{result['question_id']}.log"
    raw = ""
    if RESUME_EXISTING_RAW and raw_file.exists() and raw_file.stat().st_size > 0:
        raw = raw_file.read_text(encoding="utf-8", errors="ignore")
        result["returncode"] = 0
        result["resumed_from_raw_log"] = 1
    else:
        result["resumed_from_raw_log"] = 0

    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("GTF_LEVEL2_SUBJECT_SOURCE", "graph")
    env.setdefault("GTF_ENABLE_KAG_FALLBACK", "1")
    env.setdefault("GTF_ENABLE_V7_FALLBACK", "0")
    env.setdefault("GTF_ENABLE_V8_KAG_MULTIHOP_PLANNER", "1")
    env.setdefault("GTF_ENABLE_EMBEDDING", "1")
    env.setdefault("GTF_ENABLE_ENTITY_EMBEDDING_GROUNDING", "1")
    env.setdefault("GTF_ENABLE_EMBEDDING_ENTITY_CANDIDATES", "1")
    env.setdefault("GTF_ENABLE_EMBEDDING_RELATION_FALLBACK", "1")
    env.setdefault("GTF_ENABLE_EMBEDDING_ANSWER_RERANK", "1")
    env.setdefault("GTF_EMBEDDING_MODEL_NAME", "runtime_data/models/bge-small-zh-v1.5")

    if not result["resumed_from_raw_log"]:
        try:
            proc = subprocess.run(
                [sys.executable, str(ANSWER_SCRIPT), question],
                cwd=str(PROJECT_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=TIMEOUT_SECONDS,
                env=env,
            )
            raw = proc.stdout or ""
            result["returncode"] = proc.returncode
        except subprocess.TimeoutExpired as e:
            raw = e.stdout if isinstance(e.stdout, str) else ""
            result["returncode"] = -999
            result["error"] = f"timeout after {TIMEOUT_SECONDS}s"
        raw_file.write_text(raw, encoding="utf-8", errors="ignore")
    result["raw_log"] = str(raw_file)

    meta = extract_meta(raw)
    pred_items = extract_pred_items(meta)

    answer_pool = "\n".join([
        raw,
        meta.get("answer_section", ""),
        meta.get("graph_answers", ""),
        meta.get("kag_answers", ""),
        meta.get("kag_evidence_answer", ""),
    ])
    norm_pool = norm_text(answer_pool)

    hit_items, missing_items = [], []
    for g in gold_items:
        ng = norm_text(g)
        if ng and ng in norm_pool:
            hit_items.append(g)
        else:
            missing_items.append(g)

    pred_norms = [norm_text(x) for x in pred_items if norm_text(x)]
    gold_norms = [norm_text(x) for x in gold_items if norm_text(x)]
    pred_hit_count = 0
    for p in pred_norms:
        if any(p in g or g in p for g in gold_norms):
            pred_hit_count += 1

    refused = system_refused(answer_pool)
    if should_refuse:
        passed = refused
    else:
        passed = bool(gold_items) and not missing_items

    result.update({
        "passed": int(passed),
        "system_refused": int(refused),
        "hit_count": len(hit_items),
        "missing_count": len(missing_items),
        "missing_gold_items": "||".join(missing_items),
        "pred_items": "||".join(pred_items),
        "pred_count": len(pred_norms),
        "pred_hit_count": pred_hit_count,
        "answer_section": meta.get("answer_section", ""),
        "route": meta.get("route", ""),
        "final_route": meta.get("final_route", ""),
        "answer_source": meta.get("answer_source", ""),
        "intent_source": meta.get("intent_source", ""),
        "kag_used": meta.get("kag_used", ""),
        "system_question_type": meta.get("question_type", ""),
        "system_subject": meta.get("subject", ""),
    })
    return result


def pct(a, b):
    return round(a / b * 100, 2) if b else 0.0


def write_csv(rows, out_csv: Path):
    fieldnames = []
    for r in rows:
        for k in r:
            if k not in fieldnames:
                fieldnames.append(k)
    with out_csv.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_report(rows):
    total = len(rows)
    judged = [r for r in rows if r.get("should_refuse") == 1 or r.get("gold_count", 0) > 0]
    passed = sum(int(r.get("passed", 0)) for r in judged)

    non_refuse = [r for r in judged if r.get("should_refuse") == 0]
    gold_total = sum(int(r.get("gold_count", 0)) for r in non_refuse)
    hit_total = sum(int(r.get("hit_count", 0)) for r in non_refuse)
    pred_total = sum(int(r.get("pred_count", 0)) for r in non_refuse)
    pred_hit_total = sum(int(r.get("pred_hit_count", 0)) for r in non_refuse)
    recall = hit_total / gold_total if gold_total else 0.0
    precision = pred_hit_total / pred_total if pred_total else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0

    refuse_rows = [r for r in judged if r.get("should_refuse") == 1]
    refusal_ok = sum(int(r.get("passed", 0)) for r in refuse_rows)

    lines = [
        "# 真实自由问答测试集 v1 评测报告",
        "",
        "## 1. 基本信息",
        "",
        f"- 总题数：{total}",
        f"- 可判定题数：{len(judged)}",
        f"- 评测脚本：`app/评测脚本/真实自由问答测试集批量评测_v1.py`",
        f"- 测试集：`app/tests/测试集/真实自由问答测试集_v1.csv`",
        "",
        "## 2. 核心指标",
        "",
        f"- 通过题数：{passed}",
        f"- 问题级准确率：{pct(passed, len(judged)):.2f}%",
        f"- 答案项级召回率：{recall * 100:.2f}%",
        f"- 答案项级精确率：{precision * 100:.2f}%",
        f"- 答案项级 F1：{f1 * 100:.2f}%",
        f"- 拒答准确率：{pct(refusal_ok, len(refuse_rows)):.2f}%",
        "",
        "## 3. 按题型统计",
        "",
        "| 题型 | 总数 | 通过 | 准确率 |",
        "|---|---:|---:|---:|",
    ]

    categories = sorted(set(r.get("category", "") for r in rows))
    for cat in categories:
        sub = [r for r in rows if r.get("category", "") == cat]
        sp = sum(int(r.get("passed", 0)) for r in sub)
        lines.append(f"| {cat} | {len(sub)} | {sp} | {pct(sp, len(sub)):.2f}% |")

    lines.extend([
        "",
        "## 4. 按难度统计",
        "",
        "| 难度 | 总数 | 通过 | 准确率 |",
        "|---|---:|---:|---:|",
    ])
    for diff in sorted(set(r.get("difficulty", "") for r in rows)):
        sub = [r for r in rows if r.get("difficulty", "") == diff]
        sp = sum(int(r.get("passed", 0)) for r in sub)
        lines.append(f"| {diff} | {len(sub)} | {sp} | {pct(sp, len(sub)):.2f}% |")

    lines.extend([
        "",
        "## 5. 路由分布",
        "",
    ])
    for col in ["final_route", "answer_source", "intent_source", "kag_used"]:
        counts = {}
        for r in rows:
            v = str(r.get(col, "") or "(empty)")
            counts[v] = counts.get(v, 0) + 1
        lines.append(f"### {col}")
        lines.append("")
        lines.append("| 值 | 数量 |")
        lines.append("|---|---:|")
        for k, v in sorted(counts.items(), key=lambda x: x[1], reverse=True)[:30]:
            lines.append(f"| {k} | {v} |")
        lines.append("")

    failed = [r for r in rows if int(r.get("passed", 0)) == 0]
    lines.extend([
        "## 6. 失败样例",
        "",
    ])
    if not failed:
        lines.append("无失败题。")
    else:
        lines.append("| 题号 | 题型 | 问题 | 缺失答案 | final_route |")
        lines.append("|---|---|---|---|---|")
        for r in failed[:100]:
            q = str(r.get("question", "")).replace("|", "｜")
            miss = str(r.get("missing_gold_items", "")).replace("|", "｜")
            lines.append(
                f"| {r.get('question_id')} | {r.get('category')} | {q} | {miss} | {r.get('final_route', '')} |"
            )

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def main():
    if not TEST_CSV.exists():
        raise FileNotFoundError(f"测试集不存在，请先运行生成脚本：{TEST_CSV}")

    check_neo4j_preflight()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    rows = read_rows(TEST_CSV)
    if EVAL_LIMIT > 0:
        rows = rows[:EVAL_LIMIT]
    print(f"[INFO] 测试集: {TEST_CSV}")
    print(f"[INFO] 输出目录: {OUT_DIR}")
    print(f"[INFO] 总题数: {len(rows)}")
    print(f"[INFO] workers={MAX_WORKERS}, timeout={TIMEOUT_SECONDS}s")
    print(f"[INFO] resume_existing_raw={int(RESUME_EXISTING_RAW)}")

    start = time.time()
    results = []
    task_rows = list(enumerate(rows))
    if RESUME_EXISTING_RAW:
        pending = []
        resumed = 0
        for idx, row in task_rows:
            qid = row.get("question_id", "")
            raw_file = RAW_DIR / f"{idx + 1:04d}_{qid}.log"
            if raw_file.exists() and raw_file.stat().st_size > 0:
                results.append(run_one(idx, row))
                resumed += 1
            else:
                pending.append((idx, row))
        task_rows = pending
        print(f"[INFO] resume reused raw logs: {resumed}")
        print(f"[INFO] resume pending new runs: {len(task_rows)}")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = {ex.submit(run_one, idx, row): idx for idx, row in task_rows}
        done = 0
        for fut in as_completed(futs):
            done += 1
            try:
                results.append(fut.result())
            except Exception as e:
                results.append({
                    "row_index": futs[fut],
                    "passed": 0,
                    "error": repr(e),
                })
            total_done = len(results)
            if done % 20 == 0 or done == len(task_rows):
                print(f"[INFO] progress {total_done}/{len(rows)}")

    results.sort(key=lambda x: int(x.get("row_index", 0)))
    write_csv(results, OUT_CSV)
    write_report(results)

    print("[DONE] 评测完成")
    print(f"[DONE] CSV: {OUT_CSV}")
    print(f"[DONE] MD : {OUT_MD}")
    print(f"[DONE] 用时: {time.time() - start:.1f}s")


if __name__ == "__main__":
    main()
