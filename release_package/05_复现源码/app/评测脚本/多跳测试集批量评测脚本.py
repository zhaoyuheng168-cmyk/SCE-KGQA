# -*- coding: utf-8 -*-
"""
多跳测试集批量评测脚本。

输入：
    app/tests/normaltests/多跳测试集.csv

输出：
    app/retrieval_only/tests/normaltests评测结果/多跳测试集评测结果/
        - 多跳测试集评测结果.csv
        - 多跳测试集评测结果.md
        - raw_logs/

评测逻辑：
1. 调用 V8 主问答入口；
2. 解析 question_type、route、final_route、graph_answers、CYPHER；
3. 从 CYPHER 中提取 targets 查询段；
4. 将 CYPHER 重新提交到 Neo4j 执行；
5. 根据 Cypher 是否为多跳、Neo4j 是否返回答案、是否安全拒答、是否单跳退化进行判定。
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

from neo4j import GraphDatabase


ROOT = Path("/root/work/GansuTechFinance_KGQA_RELEASE_RUNTIME")
TEST_FILE = ROOT / "app/tests/normaltests/多跳测试集.csv"
RESULT_DIR = ROOT / "app/retrieval_only/tests/normaltests评测结果/多跳测试集评测结果"
LOG_DIR = RESULT_DIR / "raw_logs"

MAX_WORKERS = int(os.environ.get("EVAL_WORKERS", "4"))
TIMEOUT_SECONDS = int(os.environ.get("EVAL_TIMEOUT", "240"))

NEO4J_URI = os.environ.get("GTF_NEO4J_URI", "bolt://127.0.0.1:7688")
NEO4J_USER = os.environ.get("GTF_NEO4J_USER", "neo4j")
NEO4J_DATABASE = os.environ.get("GTF_NEO4J_DATABASE", "neo4j")


def read_env_password():
    env_file = ROOT / "config/neo4j_runtime.env"
    if not env_file.exists():
        return ""

    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        if line.startswith("GTF_NEO4J_PASSWORD="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


NEO4J_PASSWORD = os.environ.get("GTF_NEO4J_PASSWORD") or read_env_password()


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


def norm_subject(s: str):
    if s is None:
        return ""
    s = str(s).strip()
    s = re.sub(r"\s+", "", s)
    s = s.replace("　", "")
    s = s.replace("（", "(").replace("）", ")")
    s = s.replace("“", "").replace("”", "")
    return s


def cypher_literal(s: str):
    s = "" if s is None else str(s)
    return "'" + s.replace("\\", "\\\\").replace("'", "\\'") + "'"


def split_subject_parts(subject: str):
    if not subject:
        return []
    parts = re.split(r"\s*/\s*|\s*[|｜]\s*", str(subject))
    out = []
    for p in parts:
        p = p.strip()
        if p and p not in out:
            out.append(p)
    return out


def extract_quoted_text(question: str):
    if not question:
        return ""
    m = re.search(r"[“\"']([^”\"']{2,80})[”\"']", str(question))
    return m.group(1).strip() if m else ""


def infer_policy_from_question(question: str):
    if not question:
        return ""

    quoted = extract_quoted_text(question)
    if quoted and re.search(r"政策|方案|计划|通知|公告|办法|条例|意见|措施|工作", quoted):
        return quoted

    # 多跳测试题常把政策长名直接放在问题前半段，截到政策标题后缀即可。
    m = re.search(
        r"([\u4e00-\u9fa5A-Za-z0-9（）()《》·\-]{4,80}?"
        r"(?:实施方案|工作方案|试点任务的通知|通知|公告|办法|条例|意见|措施|计划|方案))",
        str(question),
    )
    return m.group(1).strip("，,。？? ") if m else ""


def build_cypher_param_values(subject: str, question: str = "", row=None):
    """
    新版 V8 多跳 Cypher 会输出 $agency/$policy/$product 等命名参数。
    老评测器只替换 $subject，导致这些查询无法执行；这里仅补齐执行参数，
    不改变系统回答和路由逻辑。
    """
    row = row or {}
    parts = split_subject_parts(subject)
    subject_norm = norm_subject(subject)

    values = {
        "subject": subject,
        "subject_norm": subject_norm,
    }

    if parts:
        values["subject_part_1"] = parts[0]
        values["agency"] = parts[0]
        values["institution"] = parts[0]
        values["product"] = parts[0]
        values["enterprise"] = parts[0]
        values["region"] = parts[0]
        values["industry"] = parts[0]
        values["feature"] = parts[0]

    if len(parts) >= 2:
        values["policy"] = parts[1]
        values["subject_part_2"] = parts[1]
    else:
        inferred_policy = infer_policy_from_question(question)
        if inferred_policy:
            values["policy"] = inferred_policy

    # 如果测试集未来补了结构化列，优先作为对应参数的补充来源。
    column_aliases = {
        "agency": ["agency", "agency_name", "government_agency", "issuer", "发文机构", "发布机构"],
        "institution": ["institution", "institution_name", "financial_institution", "机构", "金融机构"],
        "policy": ["policy", "policy_name", "政策", "政策名称"],
        "product": ["product", "product_name", "金融产品", "产品"],
        "enterprise": ["enterprise", "enterprise_name", "企业"],
        "region": ["region", "region_name", "地区"],
        "industry": ["industry", "industry_name", "行业"],
        "feature": ["feature", "feature_name", "企业特征", "特征"],
    }
    for param, cols in column_aliases.items():
        for col in cols:
            if col in row and str(row.get(col, "")).strip():
                values[param] = str(row.get(col, "")).strip()
                break

    return values


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


def extract_cypher_block(text: str):
    m = re.search(
        r"===== CYPHER =====\n(.*?)(?:\n===== KAG EVIDENCE ANSWER =====|\n===== KAG EVIDENCE =====|\Z)",
        text,
        re.S,
    )
    return m.group(1).strip() if m else ""


def extract_target_cypher(cypher_block: str):
    """
    V8 多跳输出通常包含：
        -- targets --
        MATCH ...
        RETURN DISTINCT t.name AS answer

        -- products --
        ...

        -- enterprises --
        ...

    评测答案时只执行 targets 段。
    """
    if not cypher_block.strip():
        return ""

    if "-- targets --" in cypher_block:
        part = cypher_block.split("-- targets --", 1)[1]
        part = re.split(r"\n--\s*[^-\n]+?\s*--", part, maxsplit=1)[0]
        return part.strip()

    # 没有 targets 段时，尝试清理注释行后执行整个块
    lines = []
    for line in cypher_block.splitlines():
        if line.strip().startswith("--"):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def prepare_cypher_for_execution(cypher: str, subject: str, question: str = "", row=None):
    param_values = build_cypher_param_values(subject, question, row)
    prepared = cypher

    for name in sorted(param_values.keys(), key=len, reverse=True):
        prepared = re.sub(
            rf"\${re.escape(name)}\b",
            cypher_literal(param_values[name]),
            prepared,
        )

    return prepared


def has_unresolved_params(cypher: str):
    return bool(re.search(r"\$[A-Za-z_][A-Za-z0-9_]*", cypher))


def is_execution_error_text(text: str):
    markers = [
        "command not found",
        "cypher-shell",
        "Traceback",
        "Exception",
        "ERROR",
        "Failed",
        "Neo.ClientError",
        "ServiceUnavailable",
        "AuthError",
        "bash:",
    ]
    s = str(text or "")
    return any(m in s for m in markers)


def stringify_neo4j_value(value):
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return str(value).strip()
    if isinstance(value, (list, tuple, set)):
        return "||".join(
            x for x in (stringify_neo4j_value(v) for v in value)
            if x and not is_execution_error_text(x)
        )
    if isinstance(value, dict):
        for key in ("name", "answer", "title", "id"):
            if key in value:
                return stringify_neo4j_value(value.get(key))
        return json.dumps(value, ensure_ascii=False)
    if hasattr(value, "get"):
        for key in ("name", "answer", "title", "id"):
            try:
                got = value.get(key)
            except Exception:
                got = None
            if got:
                return stringify_neo4j_value(got)
    return str(value).strip()


def execute_cypher(cypher: str):
    """
    通过 Neo4j Python driver 直接执行，避免依赖容器内 cypher-shell。
    返回 answers 列表和原始输出。
    """
    if not NEO4J_PASSWORD:
        return [], "ERROR: 未读取到 GTF_NEO4J_PASSWORD"

    if not cypher.strip():
        return [], "ERROR: empty cypher"

    if has_unresolved_params(cypher):
        return [], f"ERROR: unresolved cypher params in query:\n{cypher}"

    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        with driver:
            with driver.session(database=NEO4J_DATABASE) as session:
                rows = session.run(cypher, timeout=TIMEOUT_SECONDS).data()
    except Exception as e:
        return [], f"ERROR: Neo4j driver execution failed: {type(e).__name__}: {e}"

    answers = []
    for row in rows:
        values = [row.get("answer")] if "answer" in row else list(row.values())
        for value in values:
            text = stringify_neo4j_value(value).strip().strip('"').strip("'").strip()
            if not text or is_execution_error_text(text):
                continue
            for item in re.split(r"\|\|", text):
                item = item.strip()
                if item and item not in answers and not is_execution_error_text(item):
                    answers.append(item)

    raw = json.dumps(rows[:50], ensure_ascii=False, default=str)
    if len(rows) > 50:
        raw += f"\n... truncated, total_rows={len(rows)}"

    return answers, raw


def cypher_has_multihop(cypher: str):
    """
    粗判是否为多跳 Cypher：
    - 至少包含多个 MATCH；
    - 或者关系箭头/关系段数量达到 2 个以上；
    """
    if not cypher:
        return False

    match_count = len(re.findall(r"\bMATCH\b", cypher, flags=re.I))
    rel_count = len(re.findall(r"-\s*\[[^\]]*\]\s*->|<-\s*\[[^\]]*\]\s*-", cypher))

    return match_count >= 2 or rel_count >= 2


def infer_expected_target_type(row, question_type):
    raw = ""
    for c in ["target_type", "expected_target_type", "目标类型"]:
        if c in row and str(row.get(c, "")).strip():
            raw = str(row.get(c, "")).strip()
            break

    if raw:
        return raw

    qt = question_type or ""
    if "region" in qt:
        return "Region"
    if "industry" in qt:
        return "IndustrySegment"
    if "feature" in qt:
        return "QualificationCreditFeature"
    if "product" in qt:
        return "FinancialProduct"
    if "enterprise" in qt:
        return "Enterprise"

    q = str(row.get("question", ""))
    if "地区" in q:
        return "Region"
    if "行业" in q or "产业" in q:
        return "IndustrySegment"
    if "特征" in q or "资质" in q:
        return "QualificationCreditFeature"
    if "产品" in q:
        return "FinancialProduct"
    if "企业" in q:
        return "Enterprise"

    return ""


def target_type_ok(cypher: str, expected_target_type: str):
    """
    主要检查 targets 查询段里是否出现目标类型标签。
    """
    if not expected_target_type:
        return 1

    type_map = {
        "Region": ["Region", "地区"],
        "IndustrySegment": ["IndustrySegment", "行业", "产业"],
        "QualificationCreditFeature": ["QualificationCreditFeature", "资质", "特征"],
        "FinancialProduct": ["FinancialProduct", "产品"],
        "Enterprise": ["Enterprise", "企业"],
    }

    keys = type_map.get(expected_target_type, [expected_target_type])
    return int(any(k in cypher for k in keys))


def is_safe_refuse(answer, final_route, route):
    markers = [
        "无法回答", "无法确定", "未检索到", "没有检索到",
        "当前图谱未", "不在当前图谱", "路径缺失",
        "graph_path_missing", "unsupported", "暂不支持", "当前暂不支持"
    ]
    return int(
        final_route in ["graph_path_missing", "refuse", "unsupported"]
        or "refuse" in str(route)
        or any(m in str(answer) for m in markers)
    )


def norm_item(s: str):
    if s is None:
        return ""
    s = str(s).strip()
    s = re.sub(r"\s+", "", s)
    s = s.replace("　", "")
    s = s.replace("（", "(").replace("）", ")")
    s = s.replace("“", "").replace("”", "")
    s = s.replace("，", "").replace(",", "").replace("、", "")
    return s.lower()


def split_gold_items(row):
    """
    如果多跳测试集中未来补充了 gold_items，则做弱覆盖判断。
    当前大多数多跳题 gold_items 为空。
    """
    for c in ["gold_items", "gold", "gold_answer", "reference_answer", "expected_answer", "参考答案"]:
        if c in row and str(row.get(c, "")).strip():
            s = str(row.get(c, "")).strip()
            parts = re.split(r"\|\||;|；|,|，|、|\n", s)
            out = []
            for x in parts:
                x = x.strip()
                if x and x not in out:
                    out.append(x)
            return out
    return []


def weak_gold_coverage(gold_items, cypher_answers):
    """
    如果答案很多，只要覆盖一部分 gold，即可认为答案方向正确。
    没有 gold 时，只看 cypher_answers 是否非空。
    """
    if not gold_items:
        return int(len(cypher_answers) > 0), ""

    ans_norm = "||".join(norm_item(x) for x in cypher_answers)
    hit = []
    miss = []

    for g in gold_items:
        ng = norm_item(g)
        if ng and ng in ans_norm:
            hit.append(g)
        else:
            miss.append(g)

    return int(len(hit) > 0), "||".join(miss)


def evaluate_one(idx, total, row):
    q_col = pick_col(row, ["question", "query", "问题", "Question", "用户问题"])
    question = str(row.get(q_col, "")).strip() if q_col else ""
    qid_col = pick_col(row, ["question_id", "id", "qid", "编号", "ID"])
    qid = str(row.get(qid_col, "")).strip() if qid_col else str(idx)

    safe_qid = re.sub(r"[^0-9A-Za-z_\-一-龥]+", "_", qid)[:80]
    log_path = LOG_DIR / f"{idx:04d}_{safe_qid}.txt"

    print(f"[多跳测试集] [{idx}/{total}] {qid} {question}")

    try:
        output = run_v8(question, log_path)

        actual_question_type = extract_field(output, "question_type")
        subject = extract_field(output, "subject")
        route = extract_field(output, "route")
        final_route = extract_field(output, "final_route")
        answer_source = extract_field(output, "answer_source")
        graph_answers = extract_field(output, "graph_answers")
        kag_answers = extract_field(output, "kag_answers")
        answer = extract_answer(output)
        cypher_block = extract_cypher_block(output)
        target_cypher = extract_target_cypher(cypher_block)

        prepared_cypher = prepare_cypher_for_execution(target_cypher, subject, question, row)
        unresolved_params = int(has_unresolved_params(prepared_cypher))

        cypher_answers = []
        cypher_raw_output = ""

        if target_cypher and not unresolved_params:
            cypher_answers, cypher_raw_output = execute_cypher(prepared_cypher)
        elif target_cypher:
            cypher_raw_output = "ERROR: Cypher contains unresolved params"

        expected_target_type = infer_expected_target_type(row, actual_question_type)
        target_ok = target_type_ok(target_cypher, expected_target_type)

        gold_items = split_gold_items(row)
        weak_cover, weak_missing_gold = weak_gold_coverage(gold_items, cypher_answers)

        is_multihop_recognized = int(actual_question_type.startswith("multi_hop_"))
        is_multihop_planned = int("multihop" in route or "multihop" in final_route or "kag_planned_multihop" in route)
        cypher_returned = int(bool(target_cypher.strip()))
        cypher_multihop = int(cypher_has_multihop(target_cypher))
        cypher_executed = int(len(cypher_answers) > 0)
        safe_refuse = is_safe_refuse(answer, final_route, route)

        # 单跳误退化：没有识别多跳，且没有安全拒答，但给了普通图谱/证据答案
        is_singlehop_degraded = int(
            not is_multihop_recognized
            and not safe_refuse
            and final_route not in ["graph_path_missing", "unsupported", "refuse"]
        )

        is_multihop_success = int(
            is_multihop_recognized
            and is_multihop_planned
            and cypher_returned
            and cypher_multihop
            and cypher_executed
            and target_ok
            and weak_cover
        )

        pass_flag = int(is_multihop_success or safe_refuse)

        if is_multihop_success:
            judgement = "多跳执行成功"
        elif safe_refuse:
            judgement = "安全拒答成功"
        elif is_singlehop_degraded:
            judgement = "单跳误退化失败"
        elif not is_multihop_recognized:
            judgement = "多跳识别失败"
        elif cypher_returned and not cypher_executed:
            judgement = "Cypher未返回目标答案"
        else:
            judgement = "多跳处理失败"

        return {
            "question_index": idx,
            "question_id": qid,
            "question": question,

            "expected_target_type": expected_target_type,
            "actual_question_type": actual_question_type,
            "subject": subject,
            "route": route,
            "final_route": final_route,
            "answer_source": answer_source,

            "answer": answer,
            "graph_answers": graph_answers,
            "kag_answers": kag_answers,

            "cypher_block": cypher_block,
            "target_cypher": target_cypher,
            "prepared_cypher": prepared_cypher,
            "cypher_raw_output": cypher_raw_output,
            "cypher_answers": "||".join(cypher_answers),
            "cypher_answer_count": len(cypher_answers),
            "unresolved_params": unresolved_params,

            "gold_items": "||".join(gold_items),
            "weak_gold_coverage": weak_cover,
            "weak_missing_gold": weak_missing_gold,

            "is_multihop_recognized": is_multihop_recognized,
            "is_multihop_planned": is_multihop_planned,
            "cypher_returned": cypher_returned,
            "cypher_has_multihop": cypher_multihop,
            "cypher_executed_with_answer": cypher_executed,
            "target_type_ok": target_ok,
            "is_safe_refuse": safe_refuse,
            "is_singlehop_degraded": is_singlehop_degraded,
            "is_multihop_success": is_multihop_success,
            "pass": pass_flag,
            "judgement": judgement,
            "log_file": str(log_path),
            "original_row_json": json.dumps(row, ensure_ascii=False),
        }

    except Exception as e:
        return {
            "question_index": idx,
            "question_id": qid,
            "question": question,
            "pass": 0,
            "judgement": f"error: {e}",
            "log_file": str(log_path),
            "original_row_json": json.dumps(row, ensure_ascii=False),
        }


def rate(n, d):
    return n / d if d else 0.0


def write_outputs(results):
    results = sorted(results, key=lambda x: int(x.get("question_index", 0)))

    csv_path = RESULT_DIR / "多跳测试集评测结果.csv"

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
    passed = sum(int(r.get("pass", 0)) for r in results)
    recognized = sum(int(r.get("is_multihop_recognized", 0)) for r in results)
    planned = sum(int(r.get("is_multihop_planned", 0)) for r in results)
    cypher_returned = sum(int(r.get("cypher_returned", 0)) for r in results)
    cypher_multihop = sum(int(r.get("cypher_has_multihop", 0)) for r in results)
    executed = sum(int(r.get("cypher_executed_with_answer", 0)) for r in results)
    safe_refuse = sum(int(r.get("is_safe_refuse", 0)) for r in results)
    singlehop_degraded = sum(int(r.get("is_singlehop_degraded", 0)) for r in results)
    multihop_success = sum(int(r.get("is_multihop_success", 0)) for r in results)

    md_path = RESULT_DIR / "多跳测试集评测结果.md"

    md = []
    md.append("# 多跳测试集评测结果\n\n")
    md.append(f"评测时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    md.append(f"- 测试集文件：`{TEST_FILE}`\n")
    md.append(f"- 结果 CSV：`{csv_path}`\n")
    md.append(f"- 原始日志目录：`{LOG_DIR}`\n")
    md.append(f"- 并发数：{MAX_WORKERS}\n\n")

    md.append("## 一、总体指标\n\n")
    md.append(f"- 总题数：{total}\n")
    md.append(f"- 通过题数：{passed}\n")
    md.append(f"- 多跳有效处理率：{rate(passed, total):.2%}\n")
    md.append(f"- 多跳执行成功题数：{multihop_success}\n")
    md.append(f"- 安全拒答成功题数：{safe_refuse}\n\n")

    md.append("## 二、链路指标\n\n")
    md.append(f"- 多跳识别率：{rate(recognized, total):.2%}（{recognized}/{total}）\n")
    md.append(f"- 多跳规划率：{rate(planned, total):.2%}（{planned}/{total}）\n")
    md.append(f"- Cypher 返回率：{rate(cypher_returned, total):.2%}（{cypher_returned}/{total}）\n")
    md.append(f"- 多跳 Cypher 占比：{rate(cypher_multihop, total):.2%}（{cypher_multihop}/{total}）\n")
    md.append(f"- Cypher 执行返回答案率：{rate(executed, total):.2%}（{executed}/{total}）\n")
    md.append(f"- 单跳误退化率：{rate(singlehop_degraded, total):.2%}（{singlehop_degraded}/{total}）\n\n")

    md.append("## 三、判定说明\n\n")
    md.append(
        "本测试集当前主要用于评估多跳问题识别、路径规划、Cypher 生成、Neo4j 路径执行和安全拒答能力。"
        "由于多跳测试集不一定提供完整人工标准答案，本轮不采用严格答案全集匹配；"
        "若系统返回多跳 Cypher，并且该 Cypher 在 Neo4j 中执行后能够返回目标类型答案，则判定为多跳执行成功。"
        "若当前图谱路径缺失但系统能够安全拒答，也判定为有效处理。\n\n"
    )

    md.append("## 四、失败样例\n\n")
    failed = [r for r in results if int(r.get("pass", 0)) == 0]
    if not failed:
        md.append("无失败样例。\n")
    else:
        for r in failed[:30]:
            md.append(f"### {r.get('question_id')}：{r.get('question')}\n\n")
            md.append(f"- judgement：{r.get('judgement')}\n")
            md.append(f"- actual_question_type：`{r.get('actual_question_type', '')}`\n")
            md.append(f"- route：`{r.get('route', '')}`\n")
            md.append(f"- final_route：`{r.get('final_route', '')}`\n")
            md.append(f"- cypher_answer_count：{r.get('cypher_answer_count', '')}\n")
            md.append(f"- cypher_answers：{str(r.get('cypher_answers', ''))[:500]}\n")
            md.append(f"- answer：{str(r.get('answer', '')).replace(chr(10), ' ')[:500]}\n\n")

    md_path.write_text("".join(md), encoding="utf-8")

    print("\n==== 多跳测试集 done ====")
    print("csv:", csv_path)
    print("md:", md_path)
    print("total:", total)
    print("passed:", passed)
    print("多跳有效处理率:", f"{rate(passed, total):.2%}")
    print("多跳识别率:", f"{rate(recognized, total):.2%}")
    print("多跳规划率:", f"{rate(planned, total):.2%}")
    print("Cypher返回率:", f"{rate(cypher_returned, total):.2%}")
    print("Cypher执行返回答案率:", f"{rate(executed, total):.2%}")
    print("安全拒答成功题数:", safe_refuse)
    print("单跳误退化率:", f"{rate(singlehop_degraded, total):.2%}")


def main():
    if RESULT_DIR.exists():
        shutil.rmtree(RESULT_DIR)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    rows = read_csv_auto(TEST_FILE)
    total = len(rows)

    print("开始批量评测：多跳测试集")
    print(f"并发数 EVAL_WORKERS = {MAX_WORKERS}")
    print(f"单题超时 EVAL_TIMEOUT = {TIMEOUT_SECONDS}s")
    print(f"Neo4j URI = {NEO4J_URI}")
    print(f"Neo4j database = {NEO4J_DATABASE}")

    results = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        future_map = {
            ex.submit(evaluate_one, idx, total, row): idx
            for idx, row in enumerate(rows, start=1)
        }

        for fut in as_completed(future_map):
            results.append(fut.result())

    write_outputs(results)


if __name__ == "__main__":
    main()
