# -*- coding: utf-8 -*-
import os
import re
import sys
import time
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ANSWER_SCRIPT = PROJECT_ROOT / "app/retrieval_only/scripts/answer_hybrid_v8_graph_kag_fallback.py"
TEST_DIR = PROJECT_ROOT / "app/tests/generated_eval_sets"
OUT_ROOT = PROJECT_ROOT / "app/retrieval_only/tests/generated_eval_sets评测结果"


QUESTION_COLS = [
    "question", "query", "问题", "问句", "用户问题", "自然问法",
    "question_text", "q"
]

GOLD_COLS = [
    "gold_items", "gold_answer", "gold_answers", "reference_answer",
    "参考答案", "标准答案", "答案", "answer", "expected_answer",
    "expected_answers", "gold"
]

TYPE_COLS = [
    "type", "category", "类别", "题型", "question_type", "测试类型"
]


REFUSAL_KEYWORDS = [
    "拒答", "无法回答", "不能回答", "无答案", "查不到", "不应回答"
]

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
]


def pick_col(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    lower_map = {str(c).lower(): c for c in df.columns}
    for c in candidates:
        if c.lower() in lower_map:
            return lower_map[c.lower()]
    return None


def norm_text(s):
    if s is None:
        return ""
    s = str(s)
    s = s.replace("\ufeff", "")
    s = s.replace("“", "").replace("”", "").replace('"', "").replace("'", "")
    s = re.sub(r"\s+", "", s)
    s = s.replace("，", ",").replace("；", ";").replace("：", ":")
    return s.lower()


def split_items(s):
    if s is None:
        return []
    s = str(s).strip()
    if not s or s.lower() == "nan":
        return []

    # 兼容简单列表字符串
    s = s.strip()
    s = s.strip("[]")
    s = s.replace("'", "").replace('"', "")

    if "||" in s:
        parts = s.split("||")
    elif "|" in s:
        parts = s.split("|")
    elif "；" in s:
        parts = s.split("；")
    elif ";" in s:
        parts = s.split(";")
    elif "\n" in s:
        parts = s.splitlines()
    else:
        # 不按中文逗号强拆，防止长政策标题被拆坏
        parts = [s]

    out = []
    for x in parts:
        x = str(x).strip()
        x = x.strip("[]()（）【】\"'“” ")
        if x and x.lower() != "nan":
            out.append(x)
    return out


def expected_refusal(row, gold_col):
    pool = ""
    if gold_col:
        pool += str(row.get(gold_col, "")) + " "
    for c in row.index:
        if any(k in str(c).lower() for k in ["拒答", "refusal", "should_refuse"]):
            pool += str(row.get(c, "")) + " "
    pool_lower = pool.lower().strip()
    return any(k in pool for k in REFUSAL_KEYWORDS) or pool_lower in {"true", "1", "yes"}


def system_refused(text):
    return any(p in text for p in SYSTEM_REFUSAL_PATTERNS)


def extract_section(text, name):
    pat = rf"===== {re.escape(name)} =====\n(.*?)(?=\n===== |\Z)"
    m = re.search(pat, text, flags=re.S)
    return m.group(1).strip() if m else ""


def extract_meta(raw):
    meta = {}
    for key in [
        "route", "final_route", "answer_source", "intent_source",
        "kag_used", "question_type", "subject"
    ]:
        m = re.search(rf"^{key}\s*=\s*(.*)$", raw, flags=re.M)
        if m:
            meta[key] = m.group(1).strip()

    for key in ["graph_answers", "kag_answers"]:
        m = re.search(rf"^{key}\s*=\s*(.*)$", raw, flags=re.M)
        if m:
            meta[key] = m.group(1).strip()

    meta["answer_section"] = extract_section(raw, "ANSWER")
    meta["cypher_section"] = extract_section(raw, "CYPHER")
    meta["kag_evidence_section"] = extract_section(raw, "KAG EVIDENCE")
    return meta


def extract_pred_items(meta):
    items = []

    for key in ["graph_answers", "kag_answers"]:
        val = meta.get(key, "")
        items.extend(split_items(val))

    if not items:
        ans = meta.get("answer_section", "")
        m = re.search(r"包括[:：](.*?)(?:。|\n|$)", ans)
        if m:
            tmp = m.group(1)
            tmp = tmp.replace("、", "||").replace("，", "||").replace(",", "||")
            items.extend(split_items(tmp))

    seen = set()
    out = []
    for x in items:
        nx = norm_text(x)
        if nx and nx not in seen:
            seen.add(nx)
            out.append(x)
    return out


def run_one(idx, row, question_col, gold_col, raw_dir, timeout=120):
    q = str(row.get(question_col, "")).strip()
    gold_raw = str(row.get(gold_col, "")).strip() if gold_col else ""
    gold_items = split_items(gold_raw)
    exp_refuse = expected_refusal(row, gold_col)

    result = {
        "row_index": idx,
        "question": q,
        "gold_raw": gold_raw,
        "gold_items": "||".join(gold_items),
        "expected_refusal": int(exp_refuse),
        "error": "",
    }

    if not q:
        result["error"] = "empty question"
        result["passed"] = 0
        return result

    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("GTF_LEVEL2_SUBJECT_SOURCE", "graph")
    env.setdefault("GTF_ENABLE_KAG_FALLBACK", "1")
    env.setdefault("GTF_ENABLE_V8_KAG_MULTIHOP_PLANNER", "1")

    cmd = [sys.executable, str(ANSWER_SCRIPT), q]

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
        )
        raw = proc.stdout or ""
        result["returncode"] = proc.returncode
    except subprocess.TimeoutExpired as e:
        raw = e.stdout if isinstance(e.stdout, str) else ""
        result["returncode"] = -999
        result["error"] = f"timeout after {timeout}s"

    raw_file = raw_dir / f"{idx:04d}.log"
    raw_file.write_text(raw, encoding="utf-8", errors="ignore")
    result["raw_log"] = str(raw_file)

    meta = extract_meta(raw)
    pred_items = extract_pred_items(meta)

    answer_pool = "\n".join([
        raw,
        meta.get("answer_section", ""),
        meta.get("graph_answers", ""),
        meta.get("kag_answers", ""),
    ])
    norm_pool = norm_text(answer_pool)

    hit_items = []
    missing_items = []

    for g in gold_items:
        ng = norm_text(g)
        if ng and ng in norm_pool:
            hit_items.append(g)
        else:
            missing_items.append(g)

    refused = system_refused(answer_pool)

    if exp_refuse:
        passed = refused
    elif gold_items:
        passed = len(missing_items) == 0
    else:
        passed = False

    pred_norms = [norm_text(x) for x in pred_items if norm_text(x)]
    gold_norms = [norm_text(x) for x in gold_items if norm_text(x)]

    pred_hit = 0
    for p in pred_norms:
        if any((p in g or g in p) for g in gold_norms):
            pred_hit += 1

    result.update({
        "passed": int(passed),
        "system_refused": int(refused),
        "gold_count": len(gold_items),
        "hit_count": len(hit_items),
        "missing_count": len(missing_items),
        "missing_gold_items": "||".join(missing_items),
        "pred_items": "||".join(pred_items),
        "pred_count": len(pred_norms),
        "pred_hit_count": pred_hit,
        "answer_section": meta.get("answer_section", ""),
        "cypher": meta.get("cypher_section", ""),
        "kag_evidence": meta.get("kag_evidence_section", ""),
        "route": meta.get("route", ""),
        "final_route": meta.get("final_route", ""),
        "answer_source": meta.get("answer_source", ""),
        "intent_source": meta.get("intent_source", ""),
        "kag_used": meta.get("kag_used", ""),
        "question_type": meta.get("question_type", ""),
        "subject": meta.get("subject", ""),
    })

    return result


def safe_pct(a, b):
    if not b:
        return 0.0
    return round(a / b * 100, 2)


def write_report(out_md, report_title, df_out, question_col, gold_col, type_col):
    judged_df = df_out[(df_out["gold_count"] > 0) | (df_out["expected_refusal"] == 1)]
    total = len(df_out)
    judged = len(judged_df)
    passed = int(judged_df["passed"].sum()) if judged else 0

    non_refuse = judged_df[judged_df["expected_refusal"] == 0]

    gold_total = int(non_refuse["gold_count"].sum()) if len(non_refuse) else 0
    hit_total = int(non_refuse["hit_count"].sum()) if len(non_refuse) else 0

    pred_total = int(non_refuse["pred_count"].sum()) if len(non_refuse) else 0
    pred_hit_total = int(non_refuse["pred_hit_count"].sum()) if len(non_refuse) else 0

    recall = hit_total / gold_total if gold_total else 0
    precision = pred_hit_total / pred_total if pred_total else 0
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0

    refuse_df = judged_df[judged_df["expected_refusal"] == 1]
    refusal_total = len(refuse_df)
    refusal_ok = int(refuse_df["passed"].sum()) if refusal_total else 0

    lines = []
    lines.append(f"# {report_title}")
    lines.append("")
    lines.append("## 1. 基本信息")
    lines.append("")
    lines.append(f"- 总题数：{total}")
    lines.append(f"- judged题数：{judged}")
    lines.append(f"- 问题列：`{question_col}`")
    lines.append(f"- Gold列：`{gold_col}`")
    lines.append("")
    lines.append("## 2. 核心指标")
    lines.append("")
    lines.append(f"- 通过题数：{passed}")
    lines.append(f"- 问题级准确率：{safe_pct(passed, judged):.2f}%")
    lines.append(f"- 答案项级召回率：{recall * 100:.2f}%")
    lines.append(f"- 答案项级精确率：{precision * 100:.2f}%")
    lines.append(f"- 答案项级 F1：{f1 * 100:.2f}%")
    lines.append(f"- 拒答准确率：{safe_pct(refusal_ok, refusal_total):.2f}%")
    lines.append("")
    lines.append("## 3. 路由分布")
    lines.append("")

    for col in ["final_route", "answer_source", "intent_source", "kag_used"]:
        if col in df_out.columns:
            lines.append(f"### {col}")
            lines.append("")
            lines.append("| 值 | 数量 |")
            lines.append("|---|---:|")
            vc = df_out[col].fillna("").astype(str).value_counts().head(30)
            for k, v in vc.items():
                lines.append(f"| {k or '(empty)'} | {v} |")
            lines.append("")

    if type_col and type_col in df_out.columns:
        lines.append("## 4. 按题型统计")
        lines.append("")
        lines.append("| 题型 | judged总数 | 通过 | 问题级准确率 |")
        lines.append("|---|---:|---:|---:|")
        for t, g in df_out.groupby(type_col):
            gj = g[(g["gold_count"] > 0) | (g["expected_refusal"] == 1)]
            gt = len(gj)
            gp = int(gj["passed"].sum()) if gt else 0
            lines.append(f"| {t} | {gt} | {gp} | {safe_pct(gp, gt):.2f}% |")
        lines.append("")

    fail_df = judged_df[judged_df["passed"] == 0]

    lines.append("## 5. 失败题清单")
    lines.append("")
    if len(fail_df) == 0:
        lines.append("无失败题。")
    else:
        lines.append("| row_index | question | missing_gold_items | final_route | answer_source |")
        lines.append("|---:|---|---|---|---|")
        for _, r in fail_df.head(80).iterrows():
            q = str(r.get("question", "")).replace("|", "｜")
            miss = str(r.get("missing_gold_items", "")).replace("|", "｜")
            fr = str(r.get("final_route", "")).replace("|", "｜")
            ans = str(r.get("answer_source", "")).replace("|", "｜")
            lines.append(f"| {r.get('row_index')} | {q} | {miss} | {fr} | {ans} |")

    out_md.write_text("\n".join(lines), encoding="utf-8")


def run_special_eval(input_csv_name, output_dir_name, report_title):
    csv_path = TEST_DIR / input_csv_name
    if not csv_path.exists():
        raise FileNotFoundError(f"测试集不存在：{csv_path}")

    out_dir = OUT_ROOT / output_dir_name
    raw_dir = out_dir / "raw_logs"
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(csv_path, encoding="utf-8-sig")

    question_col = pick_col(df, QUESTION_COLS)
    gold_col = pick_col(df, GOLD_COLS)
    type_col = pick_col(df, TYPE_COLS)

    if not question_col:
        raise RuntimeError(f"未识别到问题列。当前列：{list(df.columns)}")

    print(f"[INFO] 输入测试集: {csv_path}")
    print(f"[INFO] 输出目录: {out_dir}")
    print(f"[INFO] 总题数: {len(df)}")
    print(f"[INFO] question_col = {question_col}")
    print(f"[INFO] gold_col = {gold_col}")
    print(f"[INFO] type_col = {type_col}")

    workers = int(os.environ.get("EVAL_WORKERS", "4"))
    timeout = int(os.environ.get("EVAL_TIMEOUT", "120"))

    rows = []
    start = time.time()

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {
            ex.submit(run_one, int(i), row, question_col, gold_col, raw_dir, timeout): int(i)
            for i, row in df.iterrows()
        }

        done = 0
        for fut in as_completed(futs):
            done += 1
            try:
                rows.append(fut.result())
            except Exception as e:
                rows.append({
                    "row_index": futs[fut],
                    "question": "",
                    "passed": 0,
                    "error": repr(e),
                    "gold_count": 0,
                    "expected_refusal": 0,
                })

            if done % 10 == 0 or done == len(futs):
                print(f"[INFO] progress {done}/{len(futs)}")

    eval_df = pd.DataFrame(rows).sort_values("row_index")

    merged = df.reset_index().rename(columns={"index": "row_index"}).merge(
        eval_df,
        on="row_index",
        how="left",
        suffixes=("", "_eval")
    )

    safe_name = output_dir_name.replace("/", "_")
    out_csv = out_dir / f"{safe_name}.csv"
    out_md = out_dir / f"{safe_name}.md"

    merged.to_csv(out_csv, index=False, encoding="utf-8-sig")
    write_report(out_md, report_title, merged, question_col, gold_col, type_col)

    print("[DONE] 评测完成")
    print(f"[DONE] CSV: {out_csv}")
    print(f"[DONE] MD : {out_md}")
    print(f"[DONE] 用时: {time.time() - start:.1f}s")
