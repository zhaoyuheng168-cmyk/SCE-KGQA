# -*- coding: utf-8 -*-
"""
真实自由问答测试集 v4：分类型 Precision / Recall / F1 评测口径

原则：
1. 不修改 V8/V7；
2. 不覆盖原始评测结果；
3. 封闭题沿用原 gold_items_eval；
4. 泛关系题使用图谱可验证 acceptable_set；
5. 最终统一输出 1800 总体 Accuracy / Precision / Recall / F1。
"""

import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import pandas as pd


ROOT = Path("/root/work/GansuTechFinance_KGQA_RELEASE_RUNTIME")
RESULT_DIR = ROOT / "app/retrieval_only/tests/results/真实自由问答测试集_v1评测结果"
INPUT_CSV = RESULT_DIR / "真实自由问答测试集_v1评测结果.csv"

NODES_JSON = ROOT / "app/builder/data/nodes_kag.json"
EDGES_JSON = ROOT / "app/builder/data/edges_kag.json"

OUT_DIR = RESULT_DIR / "eval_mode_v4_precision_f1"
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_SUMMARY_MD = OUT_DIR / "eval_mode_v4_summary.md"
OUT_SUMMARY_CSV = OUT_DIR / "eval_mode_v4_summary.csv"
OUT_PER_Q_CSV = OUT_DIR / "eval_mode_v4_per_question.csv"
OUT_ITEM_DETAIL_CSV = OUT_DIR / "eval_mode_v4_item_detail.csv"


GENERIC_CATEGORIES = {
    "开放自由改写综合问答",
    "研究型增强-关系改写问答",
}

GENERIC_TERMS = [
    "相关结果",
    "可核验结果",
    "可验证答案",
    "关系对象",
    "关系结果",
    "能查到哪些对象",
    "能关联到哪些结果",
    "关联到哪些结果",
    "系统里能给出哪些答案",
    "直接关联的答案",
    "直接关联",
    "图谱结果",
    "匹配到哪些答案项",
    "可返回结果",
    "主要对象",
    "核心对象",
    "关联了哪些内容",
    "只看图谱",
    "当前图谱",
    "当前系统",
]


def norm_text(x: Any) -> str:
    if x is None:
        return ""
    if isinstance(x, float) and math.isnan(x):
        return ""
    s = str(x).strip()
    for a, b in [
        ("　", ""),
        (" ", ""),
        ("\t", ""),
        ("\n", ""),
        ("（", "("),
        ("）", ")"),
        ("“", ""),
        ("”", ""),
        ("《", ""),
        ("》", ""),
        ("，", ","),
        ("。", "."),
        ("：", ":"),
        ("；", ";"),
    ]:
        s = s.replace(a, b)
    return s.lower()


def as_bool(x: Any) -> bool:
    if x is None:
        return False
    if isinstance(x, bool):
        return x
    if isinstance(x, (int, float)) and not (isinstance(x, float) and math.isnan(x)):
        return int(x) == 1
    s = str(x).strip().lower()
    return s in {"1", "true", "yes", "y", "是", "通过", "pass", "passed"}


def parse_items(x: Any) -> List[str]:
    if x is None:
        return []
    if isinstance(x, float) and math.isnan(x):
        return []
    if isinstance(x, list):
        return [str(i).strip() for i in x if str(i).strip()]

    s = str(x).strip()
    if not s:
        return []

    if s.startswith("[") and s.endswith("]"):
        try:
            arr = json.loads(s)
            if isinstance(arr, list):
                return [str(i).strip() for i in arr if str(i).strip()]
        except Exception:
            pass

    s = s.replace("｜｜", "||")
    parts = re.split(r"\s*(?:\|\||;;|；；|\n)\s*", s)
    return [p.strip() for p in parts if p.strip()]


def load_json_records(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ["nodes", "edges", "data", "records", "items"]:
            if isinstance(data.get(key), list):
                return [x for x in data[key] if isinstance(x, dict)]
        vals = list(data.values())
        if vals and all(isinstance(v, dict) for v in vals):
            return vals
    return []


def pick(d: Dict[str, Any], keys: List[str], default: Any = "") -> Any:
    for k in keys:
        if k in d and d[k] not in [None, ""]:
            return d[k]
    return default


def clean_type(t: Any) -> str:
    if t is None:
        return ""
    if isinstance(t, list):
        t = t[0] if t else ""
    s = str(t).strip()
    if not s:
        return ""
    return s.split(".")[-1].split("/")[-1]


class GraphIndex:
    def __init__(self, nodes_path: Path, edges_path: Path):
        self.id_to_name: Dict[str, str] = {}
        self.name_to_types: Dict[str, Set[str]] = defaultdict(set)
        self.norm_to_name: Dict[str, str] = {}

        self.out_edges: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
        self.in_edges: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
        self.undir: Dict[str, Set[str]] = defaultdict(set)

        self._load_nodes(nodes_path)
        self._load_edges(edges_path)

    def _load_nodes(self, path: Path):
        for n in load_json_records(path):
            node_id = str(pick(n, ["id", "node_id", "uid", "spg_id", "key"], "")).strip()
            name = str(pick(n, ["name", "title", "node_name", "label"], "")).strip()
            typ = pick(n, ["type", "node_type", "label_type", "category", "schema", "class"], "")

            if not typ and isinstance(n.get("labels"), list) and n["labels"]:
                typ = n["labels"][0]

            typ = clean_type(typ)
            if not name:
                continue

            nn = norm_text(name)
            self.norm_to_name.setdefault(nn, name)
            if typ:
                self.name_to_types[nn].add(typ)

            if node_id:
                self.id_to_name[node_id] = name

    def _resolve_ref(self, ref: Any) -> str:
        if isinstance(ref, dict):
            name = pick(ref, ["name", "title", "node_name"], "")
            if name:
                return str(name).strip()
            ref = pick(ref, ["id", "node_id", "uid", "spg_id", "key"], "")

        s = str(ref).strip()
        return self.id_to_name.get(s, s)

    def _load_edges(self, path: Path):
        for e in load_json_records(path):
            src = pick(e, ["source", "src", "from", "start", "start_id", "from_id", "source_id", "head", "subject"], "")
            dst = pick(e, ["target", "dst", "to", "end", "end_id", "to_id", "target_id", "tail", "object"], "")
            rel = pick(e, ["type", "edge_type", "relation", "predicate", "label", "name"], "")

            src_name = self._resolve_ref(src)
            dst_name = self._resolve_ref(dst)
            rel_name = clean_type(rel)

            ns = norm_text(src_name)
            nt = norm_text(dst_name)
            if not ns or not nt:
                continue

            self.out_edges[ns].append((rel_name, nt))
            self.in_edges[nt].append((rel_name, ns))
            self.undir[ns].add(nt)
            self.undir[nt].add(ns)

    def find_name_norm(self, name: str) -> str:
        nn = norm_text(name)
        if nn in self.norm_to_name:
            return nn

        cands = []
        for k in self.norm_to_name:
            if k and (k in nn or nn in k):
                cands.append(k)
        if cands:
            return sorted(cands, key=len, reverse=True)[0]
        return nn

    def types_of(self, name_norm: str) -> Set[str]:
        return set(self.name_to_types.get(name_norm, set()))

    def out_targets(self, a: str, rels: Set[str]) -> Set[str]:
        return {t for r, t in self.out_edges.get(a, []) if r in rels}

    def in_sources(self, a: str, rels: Set[str]) -> Set[str]:
        return {s for r, s in self.in_edges.get(a, []) if r in rels}

    def direct_neighbors(self, a: str) -> Set[str]:
        return set(self.undir.get(a, set()))

    def build_acceptable_set(self, subject: str, question: str) -> Tuple[Set[str], str]:
        s = self.find_name_norm(subject)
        if not s:
            return set(), "no_subject"

        q = str(question or "")
        st = self.types_of(s)

        supports = {"supports"}
        provides = {"providesProduct"}
        serves = {"servesEnterprise"}
        located = {"locatedIn"}
        industry = {"belongsToIndustry"}
        feature = {"hasFeature"}
        target_ent = {"targetsEnterprise", "benefitsEnterprise"}
        issue_rels = {"issues", "issuedBy", "publishes", "releasedBy"}
        loan_rels = {"loanToEnterprise", "issuesLoan", "grantsLoan"}

        direct_only = any(x in q for x in ["直接", "一跳", "直接关联", "关系边"])
        ask_product = any(x in q for x in ["产品", "工具", "贷款"])
        ask_policy = any(x in q for x in ["政策", "依据", "文件"])
        ask_inst = any(x in q for x in ["机构", "银行", "提供方"])
        ask_region = any(x in q for x in ["地区", "区域", "城市", "地市"])
        ask_industry = any(x in q for x in ["行业", "产业"])
        ask_feature = any(x in q for x in ["企业特征", "资质", "哪类企业", "企业类型", "支持对象", "服务对象"])
        ask_enterprise = any(x in q for x in ["企业", "客户", "服务对象"])

        asked_specific = any([ask_product, ask_policy, ask_inst, ask_region, ask_industry, ask_feature, ask_enterprise])

        acc: Set[str] = set()

        if direct_only:
            acc |= self.direct_neighbors(s)
            return acc, "direct_neighbors"

        if "FinancialProduct" in st:
            providers = self.in_sources(s, provides)
            policies = self.in_sources(s, supports)
            ents = self.out_targets(s, serves)

            if not asked_specific or ask_inst:
                acc |= providers
            if not asked_specific or ask_policy:
                acc |= policies
            if not asked_specific or ask_enterprise:
                acc |= ents

            if ask_region or ask_industry or ask_feature or not asked_specific:
                for e in ents:
                    if ask_region or not asked_specific:
                        acc |= self.out_targets(e, located)
                    if ask_industry or not asked_specific:
                        acc |= self.out_targets(e, industry)
                    if ask_feature or not asked_specific:
                        acc |= self.out_targets(e, feature)

            return acc, "product_relation_set"

        if "Policy" in st:
            fps = self.out_targets(s, supports)
            ents = self.out_targets(s, target_ent)
            issuers = self.out_targets(s, issue_rels) | self.in_sources(s, issue_rels)

            if not asked_specific or ask_product:
                acc |= fps
            if not asked_specific or ask_enterprise:
                acc |= ents
            if not asked_specific or ask_inst:
                acc |= issuers

            # policy -> product -> enterprise -> region/industry/feature
            for fp in fps:
                fp_ents = self.out_targets(fp, serves)
                if ask_enterprise or not asked_specific:
                    acc |= fp_ents
                for e in fp_ents:
                    if ask_region or not asked_specific:
                        acc |= self.out_targets(e, located)
                    if ask_industry or not asked_specific:
                        acc |= self.out_targets(e, industry)
                    if ask_feature or not asked_specific:
                        acc |= self.out_targets(e, feature)

            for e in ents:
                if ask_region or not asked_specific:
                    acc |= self.out_targets(e, located)
                if ask_industry or not asked_specific:
                    acc |= self.out_targets(e, industry)
                if ask_feature or not asked_specific:
                    acc |= self.out_targets(e, feature)

            return acc, "policy_relation_set"

        if "Enterprise" in st:
            if not asked_specific or ask_region:
                acc |= self.out_targets(s, located)
            if not asked_specific or ask_industry:
                acc |= self.out_targets(s, industry)
            if not asked_specific or ask_feature:
                acc |= self.out_targets(s, feature)

            products = self.in_sources(s, serves)
            if not asked_specific or ask_product:
                acc |= products

            for fp in products:
                if not asked_specific or ask_inst:
                    acc |= self.in_sources(fp, provides)
                if not asked_specific or ask_policy:
                    acc |= self.in_sources(fp, supports)

            # 贷款事件兜底
            loan_events = self.in_sources(s, loan_rels)
            for le in loan_events:
                acc |= self.direct_neighbors(le)

            return acc, "enterprise_relation_set"

        if "FinancialInstitution" in st:
            fps = self.out_targets(s, provides)
            if not asked_specific or ask_product:
                acc |= fps
            if not asked_specific or ask_enterprise:
                for fp in fps:
                    acc |= self.out_targets(fp, serves)

            return acc, "institution_relation_set"

        # 其他类型主体：保守使用直接邻接
        acc |= self.direct_neighbors(s)
        return acc, "fallback_direct_neighbors"


def is_generic_row(row: pd.Series) -> bool:
    final_route = str(row.get("final_route", "") or "")
    category = str(row.get("category", "") or "")
    question = str(row.get("question", "") or "")

    if final_route == "relation_json_generic_fallback":
        return True

    if category in GENERIC_CATEGORIES and any(t in question for t in GENERIC_TERMS):
        return True

    return False


def set_intersection_count(a: Set[str], b: Set[str]) -> int:
    return len(a & b)


def safe_prf(hit: int, pred: int, gold: int) -> Tuple[float, float, float]:
    p = hit / pred if pred else 0.0
    r = hit / gold if gold else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f1


def main():
    if not INPUT_CSV.exists():
        raise FileNotFoundError(f"missing input csv: {INPUT_CSV}")

    print(f"[INFO] input csv: {INPUT_CSV}")
    print(f"[INFO] nodes: {NODES_JSON}")
    print(f"[INFO] edges: {EDGES_JSON}")

    df = pd.read_csv(INPUT_CSV)
    graph = GraphIndex(NODES_JSON, EDGES_JSON)

    total = len(df)

    original_pass = 0
    v4_pass = 0
    refusal_total = 0
    refusal_pass = 0

    # 原始 strict item-level
    strict_hit_total = 0
    strict_pred_total = 0
    strict_gold_total = 0

    # v4 item-level
    v4_hit_total = 0
    v4_pred_total = 0
    v4_gold_total = 0

    # 泛关系单独统计
    generic_total = 0
    generic_original_pass = 0
    generic_v4_pass = 0
    generic_hit_total = 0
    generic_pred_total = 0
    generic_gold_total = 0

    rows = []
    details = []

    for idx, row in df.iterrows():
        question = str(row.get("question", "") or "")
        subject = str(row.get("system_subject", "") or row.get("subject", "") or "")
        final_route = str(row.get("final_route", "") or "")
        category = str(row.get("category", "") or "")

        pred_items_raw = parse_items(row.get("pred_items", ""))
        gold_items_raw = parse_items(row.get("gold_items_eval", ""))

        pred_set = {norm_text(x) for x in pred_items_raw if norm_text(x)}
        gold_set = {norm_text(x) for x in gold_items_raw if norm_text(x)}

        row_original_pass = int(as_bool(row.get("passed", False)))
        original_pass += row_original_pass

        should_refuse = as_bool(row.get("should_refuse", False))
        system_refused = as_bool(row.get("system_refused", False)) or final_route in {"refuse", "unsupported"}

        generic = is_generic_row(row)

        # 原始 strict item 指标：所有非拒答题按原 gold 统计
        if not should_refuse:
            strict_hit = set_intersection_count(pred_set, gold_set)
            strict_pred = len(pred_set)
            strict_gold = len(gold_set)

            strict_hit_total += strict_hit
            strict_pred_total += strict_pred
            strict_gold_total += strict_gold
        else:
            strict_hit = strict_pred = strict_gold = 0

        eval_mode = "strict_original"
        acceptable_set: Set[str] = set()
        acceptable_reason = ""
        v4_hit = strict_hit
        v4_pred = strict_pred
        v4_gold = strict_gold
        row_v4_pass = row_original_pass

        if should_refuse:
            eval_mode = "refusal"
            refusal_total += 1
            row_v4_pass = int(system_refused)
            refusal_pass += row_v4_pass
            v4_hit = v4_pred = v4_gold = 0

        elif generic:
            eval_mode = "generic_graph_valid"
            generic_total += 1
            generic_original_pass += row_original_pass

            acceptable_set, acceptable_reason = graph.build_acceptable_set(subject, question)

            # 泛关系 item hit：预测项只要在 acceptable_set 中，即算命中
            v4_hit = set_intersection_count(pred_set, acceptable_set)
            v4_pred = len(pred_set)
            v4_gold = len(acceptable_set)

            p, r, f1 = safe_prf(v4_hit, v4_pred, v4_gold)

            # 泛关系问题级通过：
            # 1. 有主体；
            # 2. 有预测；
            # 3. precision >= 0.80；
            # 4. 如果 acceptable_set 非空，至少命中一个；
            # 5. 若原 gold 有值，尽量至少命中原核心 gold；但若图谱有效率很高，也允许通过。
            core_hit = set_intersection_count(pred_set, gold_set)
            core_ok = True
            if gold_set:
                core_ok = core_hit >= 1 or p >= 0.95

            row_v4_pass = int(
                bool(subject.strip())
                and v4_pred > 0
                and p >= 0.80
                and (v4_hit >= 1 if v4_gold > 0 else False)
                and core_ok
            )

            generic_v4_pass += row_v4_pass
            generic_hit_total += v4_hit
            generic_pred_total += v4_pred
            generic_gold_total += v4_gold

            for item in pred_items_raw:
                ni = norm_text(item)
                details.append({
                    "row_index": row.get("row_index", idx),
                    "question_id": row.get("question_id", ""),
                    "category": category,
                    "question": question,
                    "subject": subject,
                    "pred_item": item,
                    "pred_item_norm": ni,
                    "is_v4_hit": int(ni in acceptable_set),
                    "acceptable_reason": acceptable_reason,
                    "final_route": final_route,
                })

        else:
            eval_mode = "strict_original"
            row_v4_pass = row_original_pass

        if not should_refuse:
            v4_hit_total += v4_hit
            v4_pred_total += v4_pred
            v4_gold_total += v4_gold

        v4_pass += row_v4_pass

        row_out = row.to_dict()
        row_out.update({
            "eval_mode_v4": eval_mode,
            "original_pass": row_original_pass,
            "v4_pass": row_v4_pass,
            "strict_hit_count_v4": strict_hit,
            "strict_pred_count_v4": strict_pred,
            "strict_gold_count_v4": strict_gold,
            "v4_hit_count": v4_hit,
            "v4_pred_count": v4_pred,
            "v4_gold_count": v4_gold,
            "acceptable_reason": acceptable_reason,
            "acceptable_count": len(acceptable_set),
        })
        rows.append(row_out)

    strict_p, strict_r, strict_f1 = safe_prf(strict_hit_total, strict_pred_total, strict_gold_total)
    v4_p, v4_r, v4_f1 = safe_prf(v4_hit_total, v4_pred_total, v4_gold_total)
    gen_p, gen_r, gen_f1 = safe_prf(generic_hit_total, generic_pred_total, generic_gold_total)

    original_acc = original_pass / total if total else 0.0
    v4_acc = v4_pass / total if total else 0.0
    refusal_acc = refusal_pass / refusal_total if refusal_total else 0.0
    generic_original_acc = generic_original_pass / generic_total if generic_total else 0.0
    generic_v4_acc = generic_v4_pass / generic_total if generic_total else 0.0

    summary = {
        "total": total,
        "original_question_accuracy": original_acc,
        "v4_question_accuracy": v4_acc,
        "original_strict_precision": strict_p,
        "original_strict_recall": strict_r,
        "original_strict_f1": strict_f1,
        "v4_precision": v4_p,
        "v4_recall": v4_r,
        "v4_f1": v4_f1,
        "generic_question_count": generic_total,
        "generic_original_accuracy": generic_original_acc,
        "generic_v4_accuracy": generic_v4_acc,
        "generic_v4_precision": gen_p,
        "generic_v4_recall": gen_r,
        "generic_v4_f1": gen_f1,
        "refusal_total": refusal_total,
        "refusal_accuracy": refusal_acc,
        "strict_hit_total": strict_hit_total,
        "strict_pred_total": strict_pred_total,
        "strict_gold_total": strict_gold_total,
        "v4_hit_total": v4_hit_total,
        "v4_pred_total": v4_pred_total,
        "v4_gold_total": v4_gold_total,
    }

    pd.DataFrame(rows).to_csv(OUT_PER_Q_CSV, index=False, encoding="utf-8-sig")
    pd.DataFrame(details).to_csv(OUT_ITEM_DETAIL_CSV, index=False, encoding="utf-8-sig")
    pd.DataFrame([summary]).to_csv(OUT_SUMMARY_CSV, index=False, encoding="utf-8-sig")

    md = []
    md.append("# 真实自由问答分类型 Precision / Recall / F1 评测 v4\n\n")
    md.append("## 总体指标\n\n")
    md.append(f"- 总题数：{total}\n")
    md.append(f"- 原始问题级准确率：{original_acc:.2%}\n")
    md.append(f"- v4 分类型问题级准确率：{v4_acc:.2%}\n")
    md.append(f"- 原始 Strict Precision：{strict_p:.2%}\n")
    md.append(f"- 原始 Strict Recall：{strict_r:.2%}\n")
    md.append(f"- 原始 Strict F1：{strict_f1:.2%}\n")
    md.append(f"- v4 Precision：{v4_p:.2%}\n")
    md.append(f"- v4 Recall：{v4_r:.2%}\n")
    md.append(f"- v4 F1：{v4_f1:.2%}\n")
    md.append(f"- 拒答准确率：{refusal_acc:.2%}\n\n")

    md.append("## 泛关系题指标\n\n")
    md.append(f"- 泛关系题数量：{generic_total}\n")
    md.append(f"- 泛关系原始准确率：{generic_original_acc:.2%}\n")
    md.append(f"- 泛关系 v4 准确率：{generic_v4_acc:.2%}\n")
    md.append(f"- 泛关系 v4 Precision：{gen_p:.2%}\n")
    md.append(f"- 泛关系 v4 Recall：{gen_r:.2%}\n")
    md.append(f"- 泛关系 v4 F1：{gen_f1:.2%}\n\n")

    md.append("## 评测口径说明\n\n")
    md.append("- 封闭式结构化问答、多跳查询、规则推理题：仍按人工 `gold_items_eval` 严格匹配。\n")
    md.append("- 泛关系问答：预测答案项只要与题目主体存在预定义图谱关系路径，即计为有效命中。\n")
    md.append("- 拒答题：按系统是否拒答判定，不纳入答案项 Precision/Recall/F1。\n")
    md.append("- 本脚本不修改 V8/V7，不覆盖原始结果，只新增 v4 评测文件。\n\n")

    md.append("## 输出文件\n\n")
    md.append(f"- summary csv：`{OUT_SUMMARY_CSV}`\n")
    md.append(f"- per question：`{OUT_PER_Q_CSV}`\n")
    md.append(f"- item detail：`{OUT_ITEM_DETAIL_CSV}`\n")

    OUT_SUMMARY_MD.write_text("".join(md), encoding="utf-8")

    print("\n===== DONE =====")
    print(f"summary_md: {OUT_SUMMARY_MD}")
    print(f"summary_csv: {OUT_SUMMARY_CSV}")
    print(f"per_question_csv: {OUT_PER_Q_CSV}")
    print(f"item_detail_csv: {OUT_ITEM_DETAIL_CSV}")

    print("\n===== SUMMARY =====")
    for k, v in summary.items():
        if isinstance(v, float):
            print(f"{k}: {v:.6f}")
        else:
            print(f"{k}: {v}")


if __name__ == "__main__":
    main()
