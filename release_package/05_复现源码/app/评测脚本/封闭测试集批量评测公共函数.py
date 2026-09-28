# -*- coding: utf-8 -*-
"""
封闭测试集批量评测公共函数。

本版本指标：
1. 问题级准确率：通过题数 / 可判定题数
2. 答案项级召回率：命中的 gold 答案项数 / gold 答案项总数
3. 答案项级精确率：命中的系统预测答案项数 / 系统预测答案项总数
4. 答案项级 F1：Precision 和 Recall 的调和平均
5. 拒答准确率：正确拒答题数 / 应拒答题数
"""

import csv
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed


ROOT = Path("/root/work/GansuTechFinance_KGQA_RELEASE_RUNTIME")
TEST_ROOT = ROOT / "app/tests/normaltests"
RESULT_ROOT = ROOT / "app/retrieval_only/tests/normaltests评测结果"

MAX_WORKERS = int(os.environ.get("EVAL_WORKERS", "4"))
TIMEOUT_SECONDS = int(os.environ.get("EVAL_TIMEOUT", "240"))


def read_csv_auto(path: Path):
    for enc in ["utf-8-sig", "utf-8", "gb18030"]:
        try:
            with path.open("r", encoding=enc, newline="") as f:
                return list(csv.DictReader(f))
        except Exception:
            pass
    raise RuntimeError(f"无法读取 CSV：{path}")


def pick_col(row, candidates):
    for c in candidates:
        if c in row:
            return c
    return None


def is_noise_gold_item(x: str) -> bool:
    if x is None:
        return True

    t = str(x).strip()
    if not t:
        return True

    if re.fullmatch(r"A\d+", t, flags=re.I):
        return True

    if re.fullmatch(r"\d+(\.\d+)?", t):
        return True

    noise_keywords = [
        "按当前", "实例骨架", "修订题单", "结构化源", "chunk修正",
        "重建", "备注", "说明", "来源", "证据", "置信", "credit",
        "测试集2扩展", "覆盖多题型", "扩展到25题"
    ]
    return any(k in t for k in noise_keywords)


def norm_text(s: str) -> str:
    if s is None:
        return ""

    s = str(s).strip()
    s = re.sub(r"\s+", "", s)
    s = s.replace("　", "")
    s = s.replace("（", "(").replace("）", ")")
    s = s.replace("“", "").replace("”", "").replace('"', "")
    s = s.replace("。", "").replace("，", "").replace(",", "")
    s = s.replace("、", "").replace("；", "").replace(";", "")
    s = s.replace("产业细分", "")
    return s.lower()


def gold_variants(item: str):
    if item is None:
        return []

    raw = str(item).strip()
    if not raw or is_noise_gold_item(raw):
        return []

    variants = [raw]

    s = raw.replace("（", "(").replace("）", ")")
    m = re.match(r"^(.*?)\((.*?)\)$", s)
    if m:
        main = m.group(1).strip()
        alias = m.group(2).strip()
        if main:
            variants.append(main)
        if alias:
            variants.append(alias)

    if "产业细分" in raw:
        variants.append(raw.replace("产业细分", "").strip())

    out = []
    for v in variants:
        if v and v not in out and not is_noise_gold_item(v):
            out.append(v)

    return out


def split_items(s: str):
    if not s:
        return []

    parts = re.split(r"\|\||;|；|,|，|、|\n", str(s).strip())
    out = []

    for x in parts:
        x = x.strip()
        if not x or is_noise_gold_item(x):
            continue
        if x not in out:
            out.append(x)

    return out


def split_gold_items(s: str):
    out = []
    for x in split_items(s):
        for v in gold_variants(x):
            if v and v not in out:
                out.append(v)
    return out


def build_gold_map(gold_rows):
    gold_map = {}

    if not gold_rows:
        return gold_map

    id_candidates = ["question_id", "id", "qid", "编号", "ID"]

    # 如果有 answer_text，优先只读 answer_text，避免 notes/weight/answer_id 被误当答案
    answer_candidates_normal = [
        "gold_items", "gold", "gold_answer", "gold_answers",
        "expected_answer", "answer", "answers", "标准答案", "参考答案",
        "reference_answer", "answer_key_points"
    ]

    alias_candidates = ["aliases", "alias", "别名", "简称"]

    first = gold_rows[0]
    id_col = pick_col(first, id_candidates)

    if not id_col:
        for idx, row in enumerate(gold_rows, start=1):
            vals = []
            for _, v in row.items():
                if v is not None and str(v).strip():
                    vals.extend(split_gold_items(v))
            gold_map[str(idx)] = vals
        return gold_map

    for row in gold_rows:
        qid = str(row.get(id_col, "")).strip()
        if not qid:
            continue

        vals = []

        if "answer_text" in row:
            vals.extend(split_gold_items(row.get("answer_text", "")))
            for ac in alias_candidates:
                if ac in row:
                    vals.extend(split_gold_items(row.get(ac, "")))
        else:
            found_answer_col = False
            for c in answer_candidates_normal:
                if c in row:
                    found_answer_col = True
                    vals.extend(split_gold_items(row.get(c, "")))

            if not found_answer_col:
                for k, v in row.items():
                    if k == id_col:
                        continue
                    if v is not None and str(v).strip():
                        vals.extend(split_gold_items(v))

        if vals:
            gold_map.setdefault(qid, [])
            for v in vals:
                if v not in gold_map[qid]:
                    gold_map[qid].append(v)

    return gold_map


def build_gold_groups(gold_items):
    """
    将 gold_items 合并成答案组，避免主名/简称/括号别名被当成多个必答项。
    例如：
    中国银行甘肃省分行
    中国银行甘肃省分行（中行甘肃省分行）
    中行甘肃省分行
    会被合并为一个答案项组。
    """
    groups = []

    for item in gold_items:
        variants = gold_variants(item)
        norms = set(norm_text(v) for v in variants if norm_text(v))
        if not norms:
            continue

        merged = False
        for g in groups:
            if g["norms"] & norms:
                g["items"].append(item)
                g["variants"].extend([v for v in variants if v not in g["variants"]])
                g["norms"].update(norms)
                merged = True
                break

        if not merged:
            groups.append({
                "items": [item],
                "variants": list(dict.fromkeys(variants)),
                "norms": norms,
            })

    return groups


def group_hit_by_answer_pool(group, answer_pool_norm):
    for v in group["variants"]:
        nv = norm_text(v)
        if nv and nv in answer_pool_norm:
            return True
    return False


def split_predicted_items(graph_answers, kag_answers):
    pred = []

    for s in [graph_answers, kag_answers]:
        for x in split_items(s):
            if x and x not in pred:
                pred.append(x)

    return pred


def predicted_item_hits_gold(pred_item, gold_groups):
    npred = norm_text(pred_item)
    if not npred:
        return False

    for g in gold_groups:
        for nv in g["norms"]:
            if not nv:
                continue
            if npred == nv or nv in npred or npred in nv:
                return True

    return False


def f1_score(p, r):
    if p + r == 0:
        return 0.0
    return 2 * p * r / (p + r)


def infer_must_refuse(row, gold_items):
    raw = str(row.get("must_refuse", "")).strip().lower()
    if raw in ["1", "true", "yes", "y", "是"]:
        return True

    markers = [
        "应拒答", "拒答", "无结果", "未检索到", "没有检索到",
        "当前图谱未", "不在当前图谱", "无法回答", "无法确定",
        "不存在", "unsupported"
    ]

    joined = "||".join(str(x) for x in gold_items)
    return any(m in joined for m in markers)


def run_v8(question: str, log_path: Path):
    cmd = ["bash", "scripts/run_v8_demo.sh", question]

    p = subprocess.run(
        cmd,
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=TIMEOUT_SECONDS,
    )

    text = p.stdout
    log_path.write_text(text, encoding="utf-8")
    return text


def extract_field(text: str, name: str) -> str:
    m = re.search(rf"^{re.escape(name)}\s*=\s*(.*)$", text, re.M)
    return m.group(1).strip() if m else ""


def extract_answer(text: str) -> str:
    m = re.search(r"===== ANSWER =====\n(.*?)(?:\n===== CYPHER =====|\Z)", text, re.S)
    return m.group(1).strip() if m else ""


def is_refusal_answer(answer: str) -> bool:
    markers = [
        "无法回答", "无法确定", "未检索到", "没有检索到",
        "当前图谱未", "不在当前图谱", "拒绝", "路径缺失",
        "graph_path_missing", "unsupported", "暂不支持", "当前暂不支持该问句模板"
    ]
    return any(x in str(answer) for x in markers)


def evaluate_one_question(testset_name, idx, total, row, gold_map, log_dir):
    q_col = pick_col(row, ["question", "query", "问题", "Question", "用户问题", "input", "prompt"])
    id_col = pick_col(row, ["question_id", "id", "qid", "编号", "ID"])

    question = str(row.get(q_col, "")).strip() if q_col else ""
    qid = str(row.get(id_col, "")).strip() if id_col else str(idx)

    if not question:
        return None

    gold_items = gold_map.get(qid, [])
    gold_groups = build_gold_groups(gold_items)
    must_refuse = infer_must_refuse(row, gold_items)

    safe_qid = re.sub(r"[^0-9A-Za-z_\-一-龥]+", "_", qid)[:80]
    log_path = log_dir / f"{idx:04d}_{safe_qid}.txt"

    print(f"[{testset_name}] [{idx}/{total}] {qid} {question}")

    try:
        output = run_v8(question, log_path)

        question_type = extract_field(output, "question_type")
        subject = extract_field(output, "subject")
        route = extract_field(output, "route")
        final_route = extract_field(output, "final_route")
        answer_source = extract_field(output, "answer_source")
        kag_used = extract_field(output, "kag_used")
        graph_answers = extract_field(output, "graph_answers")
        kag_answers = extract_field(output, "kag_answers")
        answer = extract_answer(output)

        answer_pool = "||".join([answer or "", graph_answers or "", kag_answers or ""])
        answer_pool_norm = norm_text(answer_pool)

        pred_items = split_predicted_items(graph_answers, kag_answers)

        gold_hit_count = 0
        missing_gold_groups = []

        for g in gold_groups:
            if group_hit_by_answer_pool(g, answer_pool_norm):
                gold_hit_count += 1
            else:
                missing_gold_groups.append("/".join(g["variants"]))

        pred_hit_count = 0
        for p in pred_items:
            if predicted_item_hits_gold(p, gold_groups):
                pred_hit_count += 1

        gold_count = len(gold_groups)
        pred_count = len(pred_items)

        item_recall = gold_hit_count / gold_count if gold_count else 0.0
        item_precision = pred_hit_count / pred_count if pred_count else 0.0
        item_f1 = f1_score(item_precision, item_recall)

        refusal_correct = 0

        if must_refuse:
            refusal_correct = int(
                is_refusal_answer(answer)
                or final_route in ["refuse", "graph_path_missing", "unsupported"]
            )
            pass_flag = refusal_correct
            eval_type = "refusal"
        else:
            if gold_count:
                pass_flag = int(len(missing_gold_groups) == 0)
                eval_type = "gold_contains"
            else:
                pass_flag = 0
                eval_type = "no_gold"

        return {
            "testset": testset_name,
            "question_index": idx,
            "question_id": qid,
            "question": question,

            "gold_items": "||".join(gold_items),
            "gold_item_count": gold_count,
            "gold_item_hit_count": gold_hit_count,
            "missing_gold_items": "||".join(missing_gold_groups),

            "pred_items": "||".join(pred_items),
            "pred_item_count": pred_count,
            "pred_item_hit_count": pred_hit_count,

            "item_recall": item_recall,
            "item_precision": item_precision,
            "item_f1": item_f1,

            "answer": answer,
            "question_type": question_type,
            "subject": subject,
            "route": route,
            "final_route": final_route,
            "answer_source": answer_source,
            "kag_used": kag_used,
            "graph_answers": graph_answers,
            "kag_answers": kag_answers,

            "must_refuse": int(must_refuse),
            "refusal_correct": refusal_correct,
            "eval_type": eval_type,
            "pass": pass_flag,
            "log_file": str(log_path),
            "original_question_row_json": json.dumps(row, ensure_ascii=False),
        }

    except Exception as e:
        return {
            "testset": testset_name,
            "question_index": idx,
            "question_id": qid,
            "question": question,
            "gold_items": "||".join(gold_items),
            "gold_item_count": len(gold_groups),
            "gold_item_hit_count": 0,
            "missing_gold_items": "||".join(["/".join(g["variants"]) for g in gold_groups]),
            "pred_items": "",
            "pred_item_count": 0,
            "pred_item_hit_count": 0,
            "item_recall": 0.0,
            "item_precision": 0.0,
            "item_f1": 0.0,
            "answer": "",
            "question_type": "",
            "subject": "",
            "route": "",
            "final_route": "",
            "answer_source": "",
            "kag_used": "",
            "graph_answers": "",
            "kag_answers": "",
            "must_refuse": int(must_refuse),
            "refusal_correct": 0,
            "eval_type": "error",
            "pass": 0,
            "log_file": str(log_path),
            "error": str(e),
            "original_question_row_json": json.dumps(row, ensure_ascii=False),
        }


def rate(n, d):
    return n / d if d else 0.0


def write_outputs(testset_name, out_dir, log_dir, results):
    results = [r for r in results if r is not None]
    results = sorted(results, key=lambda x: int(x.get("question_index", 0)))

    csv_path = out_dir / f"{testset_name}评测结果.csv"

    fieldnames = []
    for r in results:
        for k in r.keys():
            if k not in fieldnames:
                fieldnames.append(k)

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(results)

    total = len(results)
    judged = sum(1 for r in results if r.get("eval_type") != "no_gold")
    passed = sum(int(r.get("pass", 0)) for r in results)
    question_accuracy = rate(passed, judged)

    gold_total = sum(int(r.get("gold_item_count", 0)) for r in results if r.get("eval_type") == "gold_contains")
    gold_hit = sum(int(r.get("gold_item_hit_count", 0)) for r in results if r.get("eval_type") == "gold_contains")

    pred_total = sum(int(r.get("pred_item_count", 0)) for r in results if r.get("eval_type") == "gold_contains")
    pred_hit = sum(int(r.get("pred_item_hit_count", 0)) for r in results if r.get("eval_type") == "gold_contains")

    item_recall = rate(gold_hit, gold_total)
    item_precision = rate(pred_hit, pred_total)
    item_f1 = f1_score(item_precision, item_recall)

    refusal_total = sum(1 for r in results if int(r.get("must_refuse", 0)) == 1)
    refusal_correct = sum(int(r.get("refusal_correct", 0)) for r in results if int(r.get("must_refuse", 0)) == 1)
    refusal_accuracy = rate(refusal_correct, refusal_total)

    graph_first = sum(1 for r in results if r.get("route") == "graph_first")
    structured_graph = sum(1 for r in results if "structured_graph" in str(r.get("final_route", "")))
    kag_used_count = sum(1 for r in results if str(r.get("kag_used", "")).lower() == "true")

    md_path = out_dir / f"{testset_name}评测结果.md"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    md = []
    md.append(f"# {testset_name}评测结果\n\n")
    md.append(f"评测时间：{now}\n\n")
    md.append("## 一、评测对象\n\n")
    md.append(f"- 测试集目录：`{TEST_ROOT / testset_name}`\n")
    md.append(f"- 结果 CSV：`{csv_path}`\n")
    md.append(f"- 原始日志目录：`{log_dir}`\n")
    md.append(f"- 并发数：{MAX_WORKERS}\n\n")

    md.append("## 二、总体指标\n\n")
    md.append(f"- 总题数：{total}\n")
    md.append(f"- 可判定题数：{judged}\n")
    md.append(f"- 通过题数：{passed}\n")
    md.append(f"- 问题级准确率：{question_accuracy:.2%}\n\n")

    md.append("## 三、答案项级指标\n\n")
    md.append(f"- 标准答案项总数：{gold_total}\n")
    md.append(f"- 命中标准答案项数：{gold_hit}\n")
    md.append(f"- 系统预测答案项总数：{pred_total}\n")
    md.append(f"- 命中预测答案项数：{pred_hit}\n")
    md.append(f"- 答案项级召回率：{item_recall:.2%}\n")
    md.append(f"- 答案项级精确率：{item_precision:.2%}\n")
    md.append(f"- 答案项级 F1：{item_f1:.2%}\n\n")

    md.append("## 四、拒答指标\n\n")
    md.append(f"- 应拒答题数：{refusal_total}\n")
    md.append(f"- 正确拒答题数：{refusal_correct}\n")
    if refusal_total:
        md.append(f"- 拒答准确率：{refusal_accuracy:.2%}\n\n")
    else:
        md.append("- 拒答准确率：无应拒答题\n\n")

    md.append("## 五、路由统计\n\n")
    md.append(f"- graph_first 路由题数：{graph_first}\n")
    md.append(f"- structured_graph 相关 final_route 题数：{structured_graph}\n")
    md.append(f"- 使用 KAG evidence 辅助题数：{kag_used_count}\n\n")

    md.append("## 六、失败样例\n\n")
    failed = [r for r in results if int(r.get("pass", 0)) == 0]
    if not failed:
        md.append("无失败样例。\n")
    else:
        for r in failed[:30]:
            md.append(f"### {r.get('question_id')}：{r.get('question')}\n\n")
            md.append(f"- route：`{r.get('route')}`\n")
            md.append(f"- final_route：`{r.get('final_route')}`\n")
            md.append(f"- answer_source：`{r.get('answer_source')}`\n")
            md.append(f"- gold_items：{r.get('gold_items')}\n")
            md.append(f"- pred_items：{r.get('pred_items')}\n")
            md.append(f"- missing_gold_items：{r.get('missing_gold_items')}\n")
            md.append(f"- item_recall：{float(r.get('item_recall', 0)):.2%}\n")
            md.append(f"- item_precision：{float(r.get('item_precision', 0)):.2%}\n")
            ans = str(r.get("answer", "")).replace("\n", " ")
            md.append(f"- answer：{ans[:500]}\n\n")

    md_path.write_text("".join(md), encoding="utf-8")

    print(f"\n==== {testset_name} done ====")
    print("csv:", csv_path)
    print("md:", md_path)
    print("total:", total)
    print("judged:", judged)
    print("passed:", passed)
    print("question_accuracy:", f"{question_accuracy:.2%}")
    print("item_recall:", f"{item_recall:.2%}")
    print("item_precision:", f"{item_precision:.2%}")
    print("item_f1:", f"{item_f1:.2%}")
    if refusal_total:
        print("refusal_accuracy:", f"{refusal_accuracy:.2%}")
    else:
        print("refusal_accuracy: N/A")

    return {
        "testset": testset_name,
        "total": total,
        "judged": judged,
        "passed": passed,
        "question_accuracy": question_accuracy,
        "gold_total": gold_total,
        "gold_hit": gold_hit,
        "pred_total": pred_total,
        "pred_hit": pred_hit,
        "item_recall": item_recall,
        "item_precision": item_precision,
        "item_f1": item_f1,
        "refusal_total": refusal_total,
        "refusal_correct": refusal_correct,
        "refusal_accuracy": refusal_accuracy,
        "csv_path": str(csv_path),
        "md_path": str(md_path),
    }


def eval_closed_testset_batch(testset_name: str):
    print(f"开始批量评测：{testset_name}")
    print(f"并发数 EVAL_WORKERS = {MAX_WORKERS}")
    print(f"单题超时 EVAL_TIMEOUT = {TIMEOUT_SECONDS}s")

    test_dir = TEST_ROOT / testset_name
    q_path = test_dir / "questions.csv"
    g_path = test_dir / "gold_answers.csv"

    if not q_path.exists():
        raise FileNotFoundError(f"找不到问题文件：{q_path}")
    if not g_path.exists():
        raise FileNotFoundError(f"找不到标准答案文件：{g_path}")

    out_dir = RESULT_ROOT / f"{testset_name}评测结果"
    if out_dir.exists():
        shutil.rmtree(out_dir)

    log_dir = out_dir / "raw_logs"
    out_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    questions = read_csv_auto(q_path)
    gold_rows = read_csv_auto(g_path)
    gold_map = build_gold_map(gold_rows)

    tasks = []
    total = len(questions)

    for idx, row in enumerate(questions, start=1):
        tasks.append((testset_name, idx, total, row, gold_map, log_dir))

    results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        future_map = {ex.submit(evaluate_one_question, *task): task for task in tasks}
        for fut in as_completed(future_map):
            results.append(fut.result())

    return write_outputs(testset_name, out_dir, log_dir, results)
