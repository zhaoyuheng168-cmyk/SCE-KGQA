# -*- coding: utf-8 -*-
import json
import os
import re
import sys
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import requests
from neo4j import GraphDatabase

try:
    import yaml
except Exception:
    yaml = None

try:
    from requests import RequestsDependencyWarning
    warnings.filterwarnings("ignore", category=RequestsDependencyWarning)
except Exception:
    pass


# =========================
# 基础配置
# =========================
NAMESPACE = os.getenv("GTF_NAMESPACE", "GansuTechFinanceDevV1Enhance")
NEO4J_URI = os.getenv("GTF_NEO4J_URI", "bolt://127.0.0.1:7688")
NEO4J_USER = os.getenv("GTF_NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("GTF_NEO4J_PASSWORD", "")
NEO4J_DATABASE = os.getenv("GTF_NEO4J_DATABASE", "neo4j")

SCRIPT_DIR = Path(__file__).resolve().parent
RETRIEVAL_ROOT = SCRIPT_DIR.parent
PROJECT_ROOT = RETRIEVAL_ROOT.parent

CHUNKS_JSONL = RETRIEVAL_ROOT / "index" / "chunks.jsonl"
FULL_META_JSONL = RETRIEVAL_ROOT / "index" / "full_meta.jsonl"
FULL_VECTORS_NPY = RETRIEVAL_ROOT / "index" / "full_vectors.npy"
FULL_NORMS_NPY = RETRIEVAL_ROOT / "index" / "full_norms.npy"
EMBED_CONFIG_YAML = PROJECT_ROOT / "kag_config_chunk_build.yaml"

_DRIVER = None
_CHUNK_ROWS_CACHE = None
_META_ROWS_CACHE = None
_VECTORS_CACHE = None
_NORMS_CACHE = None
_EMBED_CFG_CACHE = None


# =========================
# 正则模式
# =========================
ENTERPRISE_RE = re.compile(
    r"[A-Za-z0-9\u4e00-\u9fa5（）()·\-\s]{2,80}?"
    r"(?:有限责任公司|股份有限公司|有限公司|集团有限公司|集团股份有限公司|集团|合作社)"
)

POLICY_RE = re.compile(
    r"[A-Za-z0-9\u4e00-\u9fa5（）()《》·\-\s]{4,140}?"
    r"(?:通知|规划|意见|方案|办法|细则|措施|计划|公告)"
)

PRODUCT_RE = re.compile(
    r"[A-Za-z0-9\u4e00-\u9fa5（）()·\-\s]{2,60}?"
    r"(?:算力贷|科技贷|科创贷|知贷|e贷|E贷|税e融|政采e贷|政采贷|成长贷|信用贷|贷款|贷)"
)

INSTITUTION_RE = re.compile(
    r"[A-Za-z0-9\u4e00-\u9fa5（）()·\-\s]{2,100}?"
    r"(?:银行(?:甘肃省分行|兰州分行|天水市分行|分行|支行)?|信用社|农村商业银行|农商银行)"
)


# =========================
# CHUNK guard 配置
# 仅对少量高频单跳开放兜底
# =========================
QUESTION_GUARDS = {
    "institution_serves_enterprises": {
        "subject_kind": "institution",
        "target_kind": "enterprise",
        "relation_keywords": ["融资", "贷款", "授信", "支持", "服务", "发放", "扶持", "对接"],
        "path_keywords": ["servesEnterprise", "loanToEnterprise", "issuesLoan", "providesProduct"],
        "require_subject": True,
        "require_relation": True,
        "min_row_score": 78.0,
        "min_candidate_support": 2,
        "max_answers": 20,
    },
    "institution_provides_what_product": {
        "subject_kind": "institution",
        "target_kind": "product",
        "relation_keywords": ["提供", "推出", "上线", "发放", "办理", "创新推出", "开展"],
        "path_keywords": ["providesProduct", "FinancialInstitution_"],
        "require_subject": True,
        "require_relation": True,
        "min_row_score": 75.0,
        "min_candidate_support": 1,
        "max_answers": 10,
    },
    "product_provided_by_institution": {
        "subject_kind": "product",
        "target_kind": "institution",
        "relation_keywords": ["提供", "推出", "上线", "发放", "办理", "创新推出", "开展"],
        "path_keywords": ["providesProduct", "FinancialInstitution_"],
        "require_subject": True,
        "require_relation": True,
        "min_row_score": 75.0,
        "min_candidate_support": 1,
        "max_answers": 10,
    },
    "product_supported_by_policies": {
        "subject_kind": "product",
        "target_kind": "policy",
        "relation_keywords": ["支持", "覆盖支持", "明确", "提出", "纳入", "依据", "鼓励", "实施"],
        "path_keywords": ["supports", "Policy_"],
        "require_subject": True,
        "require_relation": True,
        "min_row_score": 75.0,
        "min_candidate_support": 1,
        "max_answers": 12,
    },
}


# =========================
# Neo4j 工具
# =========================
def label(entity_name: str) -> str:
    return f"`{NAMESPACE}.{entity_name}`"


def full_label_name(entity_name: str) -> str:
    return f"{NAMESPACE}.{entity_name}"


def get_driver():
    global _DRIVER
    if _DRIVER is None:
        if not NEO4J_PASSWORD:
            raise RuntimeError("GTF_NEO4J_PASSWORD 未设置，请先 export。")
        _DRIVER = GraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USER, NEO4J_PASSWORD),
        )
    return _DRIVER


def close_driver():
    global _DRIVER
    if _DRIVER is not None:
        _DRIVER.close()
        _DRIVER = None


def run_cypher(cypher: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    params = params or {}
    driver = get_driver()
    with driver.session(database=NEO4J_DATABASE) as session:
        result = session.run(cypher, params)
        return [dict(record) for record in result]


# =========================
# 通用文本工具
# =========================
def normalize_query_text(text: str) -> str:
    if text is None:
        return ""
    q = str(text).strip()
    q = q.replace("？", "?").replace("（", "(").replace("）", ")")
    q = q.replace("“", '"').replace("”", '"')
    q = re.sub(r"\s+", " ", q)
    return q


def dedup_sorted(values: List[str]) -> List[str]:
    out = []
    seen = set()
    for v in values:
        if v is None:
            continue
        s = str(v).strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return sorted(out)


def dedup_keep_order(values: List[str]) -> List[str]:
    out = []
    seen = set()
    for v in values:
        s = str(v).strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def join_cn(values: List[str]) -> str:
    return "、".join(values)


def make_result(
    query: str,
    question_type: str,
    subject: str,
    route: str,
    answer: str,
    cypher: str,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload = {
        "query": query,
        "question_type": question_type,
        "subject": subject,
        "route": route,
        "answer": answer,
        "cypher": cypher.strip(),
    }
    if extra:
        payload.update(extra)
    return payload


def build_refusal_answer(question_type: str, subject: str) -> str:
    mapping = {
        "institution_provides_what_product": f"当前知识库中未检索到“{subject}”提供相关产品的充分结构化链路或高置信文本证据，无法给出可靠答案。",
        "policy_supports_what_product": f"当前知识库中未检索到“{subject}”支持相关产品的充分结构化链路或高置信文本证据，无法给出可靠答案。",
        "enterprise_belongs_industry": f"当前知识库中未检索到“{subject}”所属产业细分的充分结构化链路或高置信文本证据，无法给出可靠答案。",
        "enterprise_has_feature": f"当前知识库中未检索到“{subject}”资质信息的充分结构化链路或高置信文本证据，无法给出可靠答案。",
        "enterprise_targeted_by_policies": f"当前知识库中未检索到“{subject}”被政策覆盖支持的充分结构化链路或高置信文本证据，无法给出可靠答案。",
        "product_provided_by_institution": f"当前知识库中未检索到“{subject}”对应提供机构的充分结构化链路或高置信文本证据，无法给出可靠答案。",
        "product_supported_by_policies": f"当前知识库中未检索到“{subject}”被相关政策支持的充分结构化链路或高置信文本证据，无法给出可靠答案。",
        "institution_serves_enterprises": f"当前知识库中未检索到“{subject}”支持相关企业的充分结构化链路或高置信文本证据，无法给出可靠答案。",
        "path_policy_product_institution": f"当前知识库中未检索到“{subject}”对应多跳路径的充分结构化证据，无法给出可靠答案。",
        "path_institution_product_policy": f"当前知识库中未检索到“{subject}”对应多跳路径的充分结构化证据，无法给出可靠答案。",
        "path_policy_enterprise_feature": f"当前知识库中未检索到“{subject}”对应多跳路径的充分结构化证据，无法给出可靠答案。",
        "path_policy_enterprise_industry": f"当前知识库中未检索到“{subject}”对应多跳路径的充分结构化证据，无法给出可靠答案。",
        "path_institution_product_enterprise": f"当前知识库中未检索到“{subject}”对应多跳路径的充分结构化证据，无法给出可靠答案。",
        "path_enterprise_institution_product": f"当前知识库中未检索到“{subject}”对应多跳路径的充分结构化证据，无法给出可靠答案。",
        "freeqa_institution_product_overview": f"当前知识库中未检索到“{subject}”相关机构产品概览的充分结构化证据，无法给出可靠答案。",
        "freeqa_enterprise_profile": f"当前知识库中未检索到“{subject}”企业画像的充分结构化证据，无法给出可靠答案。",
        "freeqa_policy_product_enterprise_overview": f"当前知识库中未检索到“{subject}”政策—产品—企业链路概览的充分结构化证据，无法给出可靠答案。",
    }
    if question_type in mapping:
        return mapping[question_type]
    if subject:
        return f"当前知识库中未检索到“{subject}”的充分结构化链路或高置信文本证据，无法给出可靠答案。"
    return "当前知识库中未检索到充分结构化链路或高置信文本证据，无法给出可靠答案。"


def make_refusal_result(
    query: str,
    parsed: Dict[str, Any],
    cypher: str = "",
    reason: str = "unsupported_relation_or_no_evidence",
) -> Dict[str, Any]:
    question_type = parsed.get("question_type", "")
    subject = parsed.get("subject", "")
    answer = build_refusal_answer(question_type, subject)
    return make_result(
        query=query,
        question_type=question_type,
        subject=subject,
        route="refuse",
        answer=answer,
        cypher=cypher,
        extra={"is_refusal": True, "refuse_reason": reason},
    )


def _cypher_norm_expr(expr: str) -> str:
    out = f"coalesce({expr}, '')"
    for ch in ["“", "”", '"', "‘", "’", "'", "（", "）", "(", ")", "《", "》", " ", "　", "—", "-", "－", "–", "：", ":", "，", ",", "、", "\t", "\n", "\r"]:
        out = f"replace({out}, {json.dumps(ch, ensure_ascii=False)}, '')"
    return out


def _cypher_name_match(var_expr: str, param_expr: str) -> str:
    left = _cypher_norm_expr(var_expr)
    right = _cypher_norm_expr(param_expr)
    return f"({left} = {right} OR {left} CONTAINS {right} OR {right} CONTAINS {left})"


def _first_nonempty(obj: Dict[str, Any], keys: List[str], default: str = "") -> str:
    for k in keys:
        v = obj.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    meta = obj.get("metadata")
    if isinstance(meta, dict):
        for k in keys:
            v = meta.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
    return default


def _clean_entity_text(value: str) -> str:
    s = str(value).strip()
    s = s.strip("：:；;，,。. ")
    s = re.sub(r"^事实\d+\s*[:：]\s*", "", s)
    return s


def _contains_any(text: str, keywords: List[str]) -> bool:
    return any(k and k in text for k in keywords)


def _topk_indices_desc(scores: np.ndarray, k: int) -> np.ndarray:
    if len(scores) == 0:
        return np.array([], dtype=int)
    k = min(k, len(scores))
    idx = np.argpartition(-scores, k - 1)[:k]
    idx = idx[np.argsort(-scores[idx])]
    return idx


# =========================
# CHUNK / META / VECTORS 加载
# =========================
def load_chunk_rows() -> List[Dict[str, Any]]:
    global _CHUNK_ROWS_CACHE
    if _CHUNK_ROWS_CACHE is not None:
        return _CHUNK_ROWS_CACHE

    rows: List[Dict[str, Any]] = []
    if not CHUNKS_JSONL.exists():
        _CHUNK_ROWS_CACHE = rows
        return rows

    with CHUNKS_JSONL.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except Exception:
                continue

            text = _first_nonempty(raw, ["text", "content", "chunk_text", "body"])
            if not text:
                continue

            path = _first_nonempty(
                raw,
                ["source_path", "rel_path", "path", "doc_path", "source", "source_rel_path"],
                default=f"chunk_{idx:05d}",
            )
            chunk_id = _first_nonempty(raw, ["chunk_id", "id"], default=f"chunk_{idx:05d}")
            doc_type = _first_nonempty(raw, ["doc_type", "type"], default="unknown")

            rows.append(
                {
                    "path": path,
                    "chunk_id": chunk_id,
                    "doc_type": doc_type,
                    "text": text,
                }
            )

    _CHUNK_ROWS_CACHE = rows
    return rows


def load_meta_rows() -> List[Dict[str, Any]]:
    global _META_ROWS_CACHE
    if _META_ROWS_CACHE is not None:
        return _META_ROWS_CACHE

    chunk_rows = load_chunk_rows()
    rows: List[Dict[str, Any]] = []

    if FULL_META_JSONL.exists():
        with FULL_META_JSONL.open("r", encoding="utf-8") as f:
            for idx, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                except Exception:
                    raw = {}

                text = _first_nonempty(raw, ["text", "content", "chunk_text", "body"])
                path = _first_nonempty(
                    raw,
                    ["source_path", "rel_path", "path", "doc_path", "source", "source_rel_path"],
                )
                chunk_id = _first_nonempty(raw, ["chunk_id", "id"])
                doc_type = _first_nonempty(raw, ["doc_type", "type"], default="unknown")

                if not text and idx < len(chunk_rows):
                    text = chunk_rows[idx]["text"]
                if not path and idx < len(chunk_rows):
                    path = chunk_rows[idx]["path"]
                if not chunk_id and idx < len(chunk_rows):
                    chunk_id = chunk_rows[idx]["chunk_id"]
                if doc_type == "unknown" and idx < len(chunk_rows):
                    doc_type = chunk_rows[idx]["doc_type"]

                rows.append(
                    {
                        "path": path or f"chunk_{idx:05d}",
                        "chunk_id": chunk_id or f"chunk_{idx:05d}",
                        "doc_type": doc_type,
                        "text": text or "",
                    }
                )
    else:
        rows = chunk_rows

    _META_ROWS_CACHE = rows
    return rows


def load_vectors() -> Optional[np.ndarray]:
    global _VECTORS_CACHE
    if _VECTORS_CACHE is not None:
        return _VECTORS_CACHE
    if not FULL_VECTORS_NPY.exists():
        return None
    _VECTORS_CACHE = np.load(FULL_VECTORS_NPY)
    return _VECTORS_CACHE


def load_norms() -> Optional[np.ndarray]:
    global _NORMS_CACHE
    if _NORMS_CACHE is not None:
        return _NORMS_CACHE
    if FULL_NORMS_NPY.exists():
        _NORMS_CACHE = np.load(FULL_NORMS_NPY)
        return _NORMS_CACHE
    vectors = load_vectors()
    if vectors is None:
        return None
    _NORMS_CACHE = np.linalg.norm(vectors, axis=1)
    return _NORMS_CACHE


# =========================
# Embedding 配置与查询向量
# =========================
def iter_dicts(x):
    if isinstance(x, dict):
        yield x
        for v in x.values():
            yield from iter_dicts(v)
    elif isinstance(x, list):
        for item in x:
            yield from iter_dicts(item)


def load_embed_cfg() -> Dict[str, str]:
    global _EMBED_CFG_CACHE
    if _EMBED_CFG_CACHE is not None:
        return _EMBED_CFG_CACHE

    candidates = []
    if os.environ.get("KAG_CONFIG"):
        candidates.append(Path(os.environ["KAG_CONFIG"]))
    candidates += [EMBED_CONFIG_YAML, PROJECT_ROOT / "kag_config.yaml"]

    cfg_path = None
    cfg = None
    for p in candidates:
        if p.exists():
            if yaml is None:
                raise RuntimeError("PyYAML 未安装，无法读取 embedding 配置。")
            with p.open("r", encoding="utf-8") as f:
                cfg_path = p
                cfg = yaml.safe_load(f)
                break

    if cfg is None:
        raise FileNotFoundError("未找到可用的配置文件（kag_config_chunk_build.yaml / kag_config.yaml）")

    emb_cfg = None
    for d in iter_dicts(cfg):
        if not isinstance(d, dict):
            continue
        api_key = d.get("api_key")
        base_url = d.get("base_url")
        model = d.get("model") or d.get("name")
        if api_key and base_url and model and "embedding" in str(model).lower():
            emb_cfg = {
                "api_key": str(api_key),
                "base_url": str(base_url).rstrip("/"),
                "model": str(model),
                "vector_dimensions": int(d.get("vector_dimensions") or 1024),
                "cfg_path": str(cfg_path),
            }
            break

    if not emb_cfg:
        raise RuntimeError("Cannot find embedding config in yaml")

    _EMBED_CFG_CACHE = emb_cfg
    return emb_cfg


def embed_query(text: str) -> np.ndarray:
    cfg = load_embed_cfg()
    url = cfg["base_url"] + "/embeddings"
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
    }
    payload = {"model": cfg["model"], "input": [text]}

    resp = requests.post(url, headers=headers, json=payload, timeout=120)
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:1200]}")

    data = resp.json()
    if "data" not in data or not data["data"]:
        raise RuntimeError(f"Bad response: {json.dumps(data, ensure_ascii=False)[:1200]}")

    vec = data["data"][0]["embedding"]
    return np.asarray(vec, dtype=np.float32)


# =========================
# 向量召回 + rerank（仅保留受控兜底）
# =========================
def _institution_aliases(subject: str) -> List[str]:
    subject = subject.strip()
    aliases = [subject]
    branch_suffixes = ["甘肃省分行", "兰州分行", "天水市分行", "分行", "支行"]
    for suffix in branch_suffixes:
        if subject.endswith(suffix):
            base = subject[: -len(suffix)].strip()
            if base:
                aliases.append(base)
    return dedup_keep_order(aliases)


def _product_aliases(subject: str) -> List[str]:
    return dedup_keep_order([subject.strip()])


def build_subject_aliases(question_type: str, subject: str) -> List[str]:
    cfg = QUESTION_GUARDS.get(question_type, {})
    sk = cfg.get("subject_kind", "")
    if sk == "institution":
        return _institution_aliases(subject)
    if sk == "product":
        return _product_aliases(subject)
    return dedup_keep_order([subject.strip()])


def rerank_row(question_type: str, row: Dict[str, Any], parsed: Dict[str, Any]) -> int:
    text = row["text"]
    path = row["path"]
    score = 0

    aliases = build_subject_aliases(question_type, parsed.get("subject", ""))
    if _contains_any(text, aliases):
        score += 10

    cfg = QUESTION_GUARDS.get(question_type, {})
    if _contains_any(text, cfg.get("relation_keywords", [])):
        score += 6
    if _contains_any(path, cfg.get("path_keywords", [])):
        score += 4

    target_kind = cfg.get("target_kind")
    if target_kind == "enterprise" and ENTERPRISE_RE.search(text):
        score += 6
    elif target_kind == "product" and PRODUCT_RE.search(text):
        score += 6
    elif target_kind == "policy" and POLICY_RE.search(text):
        score += 6
    elif target_kind == "institution" and INSTITUTION_RE.search(text):
        score += 6

    if question_type == "institution_serves_enterprises":
        if parsed.get("region_hint") and parsed["region_hint"] in text:
            score += 2
        if parsed.get("tech_hint") and _contains_any(text, ["科技", "科创", "科技型", "高新技术", "专精特新"]):
            score += 2

    return score


def vector_search_top_rows(query: str, topk: int = 50) -> List[Tuple[float, Dict[str, Any]]]:
    vectors = load_vectors()
    norms = load_norms()
    meta_rows = load_meta_rows()
    if vectors is None or norms is None or not meta_rows:
        return []

    qvec = embed_query(query)
    qnorm = float(np.linalg.norm(qvec))
    if qnorm == 0.0:
        return []

    usable_n = min(len(meta_rows), len(vectors), len(norms))
    if usable_n == 0:
        return []

    vectors_use = vectors[:usable_n]
    norms_use = norms[:usable_n]
    meta_use = meta_rows[:usable_n]

    scores = (vectors_use @ qvec) / (norms_use * qnorm + 1e-12)
    top_idx = _topk_indices_desc(scores, topk)

    out = []
    for idx in top_idx:
        row = dict(meta_use[int(idx)])
        out.append((float(scores[int(idx)]), row))
    return out


def clean_line_for_extraction(text: str) -> str:
    s = text.replace("\n", " ")
    s = re.sub(r"事实\d+\s*[:：]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _extract_products_from_text(text: str) -> List[str]:
    text = clean_line_for_extraction(text)
    matches = PRODUCT_RE.findall(text)
    out = []
    for m in matches:
        s = _clean_entity_text(m)
        if len(s) < 2:
            continue
        if any(bad in s for bad in ["银行", "政策", "企业", "机构", "科技金融", "通知", "方案", "规划", "意见", "办法", "措施", "公告"]):
            continue
        if ENTERPRISE_RE.search(s) or POLICY_RE.search(s):
            continue
        out.append(s)
    return dedup_keep_order(out)


def _extract_policies_from_text(text: str) -> List[str]:
    text = clean_line_for_extraction(text)
    matches = POLICY_RE.findall(text)
    out = []
    for m in matches:
        s = _clean_entity_text(m)
        if len(s) < 4:
            continue
        out.append(s)
    return dedup_keep_order(out)


def _extract_enterprises_from_text(text: str) -> List[str]:
    text = clean_line_for_extraction(text)
    matches = ENTERPRISE_RE.findall(text)
    out = []
    for m in matches:
        s = _clean_entity_text(m)
        if len(s) < 4:
            continue
        if any(bad in s for bad in ["通知", "规划", "意见", "方案", "办法", "细则", "措施", "计划", "公告", "覆盖支持"]):
            continue
        if POLICY_RE.search(s):
            continue
        out.append(s)
    return dedup_keep_order(out)


def _extract_institutions_from_text(text: str) -> List[str]:
    text = clean_line_for_extraction(text)
    matches = INSTITUTION_RE.findall(text)
    out = []
    for m in matches:
        s = _clean_entity_text(m)
        if len(s) < 2:
            continue
        if s in {"金融机构", "银行"}:
            continue
        if any(bad in s for bad in ["通知", "规划", "意见", "方案", "办法", "细则", "措施", "计划", "公告"]):
            continue
        out.append(s)
    return dedup_keep_order(out)


def extract_candidates_by_kind(text: str, kind: str) -> List[str]:
    if kind == "enterprise":
        return _extract_enterprises_from_text(text)
    if kind == "policy":
        return _extract_policies_from_text(text)
    if kind == "product":
        return _extract_products_from_text(text)
    if kind == "institution":
        return _extract_institutions_from_text(text)
    return []


def row_subject_match(row: Dict[str, Any], parsed: Dict[str, Any]) -> bool:
    question_type = parsed.get("question_type", "")
    cfg = QUESTION_GUARDS.get(question_type, {})
    if not cfg.get("require_subject", True):
        return True
    text = row["text"]
    path = row["path"]
    aliases = build_subject_aliases(question_type, parsed.get("subject", ""))
    return _contains_any(text, aliases) or _contains_any(path, aliases)


def row_relation_match(row: Dict[str, Any], parsed: Dict[str, Any]) -> bool:
    question_type = parsed.get("question_type", "")
    cfg = QUESTION_GUARDS.get(question_type, {})
    if not cfg.get("require_relation", True):
        return True
    text = row["text"]
    path = row["path"]
    return _contains_any(text, cfg.get("relation_keywords", [])) or _contains_any(path, cfg.get("path_keywords", []))


def filter_candidate_against_subject(candidate: str, parsed: Dict[str, Any]) -> bool:
    subject = parsed.get("subject", "").strip()
    if not candidate or not subject:
        return False
    if candidate == subject:
        return False
    aliases = build_subject_aliases(parsed.get("question_type", ""), subject)
    if candidate in aliases:
        return False
    return True


def retrieve_candidate_rows(query: str, parsed: Dict[str, Any], vector_topk: int = 60, final_topk: int = 20) -> List[Tuple[float, Dict[str, Any]]]:
    question_type = parsed.get("question_type", "")
    vector_hits = vector_search_top_rows(query, topk=vector_topk)
    if not vector_hits:
        return []

    reranked = []
    for vec_score, row in vector_hits:
        lexical = rerank_row(question_type, row, parsed)
        final_score = vec_score * 100.0 + lexical
        reranked.append((final_score, row))

    reranked.sort(key=lambda x: x[0], reverse=True)
    return reranked[:final_topk]


def aggregate_candidates(hits: List[Tuple[float, Dict[str, Any]]], parsed: Dict[str, Any]) -> Tuple[List[str], List[Dict[str, Any]], List[float], int]:
    question_type = parsed.get("question_type", "")
    cfg = QUESTION_GUARDS.get(question_type, {})
    target_kind = cfg.get("target_kind", "")
    min_row_score = float(cfg.get("min_row_score", 75.0))
    min_candidate_support = int(cfg.get("min_candidate_support", 1))
    max_answers = int(cfg.get("max_answers", 10))

    support_map: Dict[str, List[Tuple[float, Dict[str, Any]]]] = {}
    accepted_rows = 0

    for score, row in hits:
        if float(score) < min_row_score:
            continue
        if not row_subject_match(row, parsed):
            continue
        if not row_relation_match(row, parsed):
            continue

        accepted_rows += 1
        candidates = extract_candidates_by_kind(row["text"], target_kind)
        cleaned = []
        for c in candidates:
            c = _clean_entity_text(c)
            if not filter_candidate_against_subject(c, parsed):
                continue
            cleaned.append(c)

        cleaned = dedup_keep_order(cleaned)
        for c in cleaned:
            support_map.setdefault(c, []).append((score, row))

    ranked_candidates = []
    for c, items in support_map.items():
        support_cnt = len(items)
        best_score = max(float(x[0]) for x in items)
        avg_score = sum(float(x[0]) for x in items) / max(1, len(items))
        ranked_candidates.append((support_cnt, avg_score, best_score, c))

    ranked_candidates.sort(key=lambda x: (-x[0], -x[1], -x[2], x[3]))

    final_answers = []
    evidence_rows = []
    evidence_scores = []

    for support_cnt, avg_score, best_score, cand in ranked_candidates:
        if support_cnt < min_candidate_support:
            continue
        final_answers.append(cand)
        items = sorted(support_map[cand], key=lambda x: x[0], reverse=True)
        evidence_rows.append(items[0][1])
        evidence_scores.append(float(items[0][0]))
        if len(final_answers) >= max_answers:
            break

    return dedup_keep_order(final_answers), evidence_rows, evidence_scores, accepted_rows


def _build_evidence_payload(rows: List[Dict[str, Any]], scores: Optional[List[float]] = None) -> Dict[str, Any]:
    evidence_paths = []
    evidence_snippets = []
    retrieval_scores = []

    for i, row in enumerate(rows[:5]):
        snippet = row["text"].strip().replace("\n", " ")
        if len(snippet) > 180:
            snippet = snippet[:180] + "..."
        evidence_paths.append(f"{row['path']}::{row['chunk_id']}")
        evidence_snippets.append(snippet)
        if scores is not None and i < len(scores):
            retrieval_scores.append(round(float(scores[i]), 6))

    return {
        "evidence_paths": evidence_paths,
        "evidence_snippets": evidence_snippets,
        "retrieval_scores": retrieval_scores,
    }


def _build_retrieval_result(
    query: str,
    parsed: Dict[str, Any],
    answer: str,
    evidence_rows: List[Dict[str, Any]],
    scores: Optional[List[float]] = None,
    accepted_rows: int = 0,
) -> Dict[str, Any]:
    extra = _build_evidence_payload(evidence_rows, scores=scores)
    extra["is_refusal"] = False
    extra["accepted_rows"] = accepted_rows
    return make_result(
        query=query,
        question_type=parsed.get("question_type", ""),
        subject=parsed.get("subject", ""),
        route="retrieval_fallback",
        answer=answer,
        cypher="",
        extra=extra,
    )


def make_answer_from_candidates(parsed: Dict[str, Any], answers: List[str]) -> str:
    question_type = parsed.get("question_type", "")
    subject = parsed.get("subject", "")
    region_hint = parsed.get("region_hint", "")
    tech_hint = bool(parsed.get("tech_hint", False))

    if question_type == "institution_serves_enterprises":
        if region_hint and tech_hint:
            return f"{subject}支持的{region_hint}科技企业包括：{join_cn(answers)}。"
        if region_hint:
            return f"{subject}支持的{region_hint}企业包括：{join_cn(answers)}。"
        return f"{subject}支持的企业包括：{join_cn(answers)}。"

    if question_type == "institution_provides_what_product":
        return f"{subject}提供的产品包括：{join_cn(answers)}。"

    if question_type == "product_provided_by_institution":
        return f"{subject}由以下金融机构提供：{join_cn(answers)}。"

    if question_type == "product_supported_by_policies":
        return f"支持{subject}的政策包括：{join_cn(answers)}。"

    return join_cn(answers)


def guarded_retrieval_fallback(query: str, parsed: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    question_type = parsed.get("question_type", "")
    if question_type not in QUESTION_GUARDS:
        return None

    hits = retrieve_candidate_rows(query, parsed, vector_topk=60, final_topk=20)
    if not hits:
        return None

    answers, evidence_rows, evidence_scores, accepted_rows = aggregate_candidates(hits, parsed)
    if not answers:
        return None

    answer = make_answer_from_candidates(parsed, answers)
    return _build_retrieval_result(
        query=query,
        parsed=parsed,
        answer=answer,
        evidence_rows=evidence_rows,
        scores=evidence_scores,
        accepted_rows=accepted_rows,
    )


# =========================
# 关系族注册表
# =========================
RELATION_FAMILIES: Dict[str, Dict[str, Any]] = {
    "institution_provides_what_product": {
        "patterns": [
            r"^(?P<subject>.+?)提供什么产品\??$",
        ],
        "cypher": f"""
        MATCH (fi:{label('FinancialInstitution')})
              -[:providesProduct]->
              (fp:{label('FinancialProduct')})
        WHERE {_cypher_name_match("fi.name", "$name")}
        RETURN DISTINCT fp.name AS answer
        ORDER BY answer
        """,
        "answer_mode": "institution_to_products",
    },
    "policy_supports_what_product": {
        "patterns": [
            r"^(?P<subject>.+?)支持什么产品\??$",
        ],
        "cypher": f"""
        MATCH (s)-[:supports]->(fp:{label('FinancialProduct')})
        WHERE {_cypher_name_match("s.name", "$name")}
          AND any(lbl IN labels(s) WHERE lbl IN $allowed_labels)
        RETURN DISTINCT fp.name AS answer
        ORDER BY answer
        """,
        "answer_mode": "policy_to_products",
        "params_builder": "policy_supports_params",
    },
    "enterprise_belongs_industry": {
        "patterns": [
            r"^(?P<subject>.+?)属于什么产业细分\??$",
            r"^(?P<subject>.+?)属于哪个产业细分\??$",
        ],
        "cypher": f"""
        MATCH (e:{label('Enterprise')})
              -[:belongsToIndustry]->
              (i:{label('IndustrySegment')})
        WHERE {_cypher_name_match("e.name", "$name")}
        RETURN DISTINCT i.name AS answer
        ORDER BY answer
        """,
        "answer_mode": "enterprise_to_industries",
    },
    "enterprise_has_feature": {
        "patterns": [
            r"^(?P<subject>.+?)具有什么资质\??$",
            r"^(?P<subject>.+?)有哪些资质\??$",
            r"^(?P<subject>.+?)具备什么资质\??$",
        ],
        "cypher": f"""
        MATCH (e:{label('Enterprise')})
              -[:hasFeature]->
              (f:{label('QualificationCreditFeature')})
        WHERE {_cypher_name_match("e.name", "$name")}
        RETURN DISTINCT f.name AS answer
        ORDER BY answer
        """,
        "answer_mode": "enterprise_to_features",
    },
    "enterprise_targeted_by_policies": {
        "patterns": [
            r"^(?P<subject>.+?)被哪些政策覆盖支持\??$",
            r"^(?P<subject>.+?)被哪些政策覆盖\??$",
        ],
        "cypher": f"""
        MATCH (p:{label('Policy')})
              -[:targetsEnterprise]->
              (e:{label('Enterprise')})
        WHERE {_cypher_name_match("e.name", "$name")}
        RETURN DISTINCT p.name AS answer
        ORDER BY answer
        """,
        "answer_mode": "enterprise_to_policies",
    },
    "product_provided_by_institution": {
        "patterns": [
            r"^(?P<subject>.+?)由哪家金融机构提供\??$",
            r"^哪家金融机构提供(?P<subject>.+?)\??$",
        ],
        "cypher": f"""
        MATCH (fi:{label('FinancialInstitution')})
              -[:providesProduct]->
              (fp:{label('FinancialProduct')})
        WHERE {_cypher_name_match("fp.name", "$name")}
        RETURN DISTINCT fi.name AS answer
        ORDER BY answer
        """,
        "answer_mode": "product_to_institutions",
    },
    "product_supported_by_policies": {
        "patterns": [
            r"^哪些政策支持(?P<subject>.+?)\??$",
            r"^(?P<subject>.+?)被哪些政策支持\??$",
        ],
        "cypher": f"""
        MATCH (p:{label('Policy')})
              -[:supports]->
              (x)
        WHERE p.name IS NOT NULL
          AND {_cypher_name_match("x.name", "$name")}
        RETURN DISTINCT p.name AS answer
        ORDER BY answer
        """,
        "answer_mode": "product_to_policies",
    },
}


# =========================
# 路径族注册表
# =========================
PATH_FAMILIES: Dict[str, Dict[str, Any]] = {
    "path_policy_product_institution": {
        "patterns": [
            {
                "regex": r"^(?P<subject>.+?)支持的产品中[，,]?哪些由(?P<constraint_institution>.+?)提供\??$",
                "return_mode": "products_filtered_by_institution",
            },
            {
                "regex": r"^(?P<subject>.+?)支持的产品分别由哪些金融机构提供\??$",
                "return_mode": "group_product_to_institutions",
            },
            {
                "regex": r"^(?P<subject>.+?)支持的产品由哪家金融机构提供\??$",
                "return_mode": "group_product_to_institutions",
            },
            {
                "regex": r"^(?P<subject>.+?)支持的产品由哪些金融机构提供\??$",
                "return_mode": "group_product_to_institutions",
            },
        ],
    },
    "path_institution_product_policy": {
        "patterns": [
            {
                "regex": r"^(?P<subject>.+?)提供的产品被哪些政策支持\??$",
                "return_mode": "group_product_to_policies",
            },
        ],
    },
    "path_policy_enterprise_feature": {
        "patterns": [
            {
                "regex": r"^(?P<subject>.+?)覆盖支持的企业具有什么资质\??$",
                "return_mode": "features",
            },
            {
                "regex": r"^(?P<subject>.+?)覆盖支持了哪些资质类型企业\??$",
                "return_mode": "features",
            },
        ],
    },
    "path_policy_enterprise_industry": {
        "patterns": [
            {
                "regex": r"^(?P<subject>.+?)覆盖支持的企业属于哪些产业细分\??$",
                "return_mode": "industries",
            },
            {
                "regex": r"^(?P<subject>.+?)重点覆盖了哪些产业方向企业\??$",
                "return_mode": "industries",
            },
        ],
    },
    "path_institution_product_enterprise": {
        "patterns": [
            {
                "regex": r"^(?P<subject>.+?)(?:通过其产品|提供的产品)服务了哪些企业\??$",
                "return_mode": "enterprises",
            },
        ],
    },
    "path_enterprise_institution_product": {
        "patterns": [
            {
                "regex": r"^(?P<subject>.+?)获得了哪些机构提供的哪些产品支持\??$",
                "return_mode": "institution_product_pairs",
            },
            {
                "regex": r"^(?P<subject>.+?)获得了哪些产品支持\??$",
                "return_mode": "institution_product_pairs",
            },
        ],
    },
}



# =========================
# 自由问答增强族注册表（第一阶段：F1 / F2）
# =========================
FREEQA_FAMILIES: Dict[str, Dict[str, Any]] = {
    "freeqa_institution_product_overview": {
        "patterns": [
            r"^如果我只看(?P<subject>.+?)，?在你这个图里它和哪些科技金融产品联系最紧\??$",
            r"^(?P<subject>.+?)在你这个知识库里，?主要是通过哪些产品参与甘肃科技金融的\??$",
            r"^(?P<subject>.+?)在图里有没有明确产品信息\??$",
            r"^(?P<subject>.+?)在你这个图里有没有明确产品信息\??$",
        ],
    },
    "freeqa_enterprise_profile": {
        "patterns": [
            r"^(?P<subject>.+?)在知识图谱里呈现出的企业画像是什么\??$",
            r"^(?P<subject>.+?)在图里属于什么类型企业，?能否进一步落到科技金融支持链上\??$",
            r"^(?P<subject>.+?)更偏向哪类科技型企业支持对象\??$",
            r"^如果把(?P<subject>.+?)拿出来单独看，它在图里更容易和哪些产品或政策发生联系\??$",
            r"^(?P<subject>.+?)在这套图里更像是被哪类金融产品服务的企业\??$",
        ],
    },
    "freeqa_policy_product_enterprise_overview": {
        "patterns": [
            r"^(?P<subject>.+?)，?最后大概能落到哪些金融产品和企业上\??$",
            r'^从[“”"]?政策[—-]产品[—-]企业[“”"]?这条链看，(?P<subject>.+?)覆盖企业的方式是什么\??$',
            r'^从“政策—产品—企业”这条链看，(?P<subject>.+?)覆盖企业的方式是什么\??$',
        ],
    },
    "freeqa_policy_landing_level": {
        "patterns": [
            r"^(?P<subject>.+?)，?在图里更像是偏政策引导，还是已经能落到具体产品层\??$",
            r"^(?P<subject>.+?)在图里更像是偏政策引导还是已经能落到具体产品层\??$",
        ],
    },
    "freeqa_policy_support_objects_overview": {
        "patterns": [
            r"^(?P<subject>.+?)，?在你的图谱里主要连接到了哪些科技金融支持对象\??$",
            r"^(?P<subject>.+?)在你的图谱里主要连接到了哪些科技金融支持对象\??$",
        ],
    },
    "freeqa_policies_cover_tech_enterprises": {
        "patterns": [
            r"^哪些政策最终能够通过产品链路覆盖到科技型企业\??$",
        ],
    },
    "freeqa_policies_reach_institution": {
        "patterns": [
            r"^哪些政策支持的产品，?最后能进一步连到(?P<constraint_institution>.+?)\??$",
        ],
    },
    "freeqa_featured_enterprise_products_by_institution": {
        "patterns": [
            r"^面向科技型中小企业的金融产品，分别是由哪些金融机构提供的\??$",
        ],
    },
    "freeqa_dual_feature_enterprise_product_match": {
        "patterns": [
            r"^如果一家企业同时具备科技型中小企业和专精特新特征，在你这套图里通常更容易匹配到哪些产品\??$",
        ],
    },
}


# =========================
# 关系族答案与执行
# =========================
def build_relation_params(family: str, subject: str) -> Dict[str, Any]:
    params = {"name": subject}
    if family == "policy_supports_what_product":
        params["allowed_labels"] = [
            full_label_name("Policy"),
            full_label_name("GovernmentAgency"),
            full_label_name("ServicePlatform"),
            full_label_name("FinancialInstitution"),
        ]
    return params


def format_relation_answer(family: str, subject: str, answers: List[str]) -> str:
    if family == "institution_provides_what_product":
        return f"{subject}提供的产品包括：{join_cn(answers)}。"
    if family == "policy_supports_what_product":
        return f"{subject}支持的产品包括：{join_cn(answers)}。"
    if family == "enterprise_belongs_industry":
        return f"{subject}所属的产业细分为：{join_cn(answers)}。"
    if family == "enterprise_has_feature":
        return f"{subject}具备的资质包括：{join_cn(answers)}。"
    if family == "enterprise_targeted_by_policies":
        return f"覆盖支持{subject}的政策包括：{join_cn(answers)}。"
    if family == "product_provided_by_institution":
        return f"{subject}由以下金融机构提供：{join_cn(answers)}。"
    if family == "product_supported_by_policies":
        return f"支持{subject}的政策包括：{join_cn(answers)}。"
    return join_cn(answers)


def run_relation_family(query: str, parsed: Dict[str, Any]) -> Dict[str, Any]:
    family = parsed["question_type"]
    cfg = RELATION_FAMILIES[family]
    subject = parsed["subject"]
    cypher = cfg["cypher"]
    params = build_relation_params(family, subject)
    rows = run_cypher(cypher, params)
    answers = dedup_sorted([row.get("answer") for row in rows])

    if answers:
        answer = format_relation_answer(family, subject, answers)
        return make_result(query, family, subject, "structured", answer, cypher)

    return make_result(query, family, subject, "no_hit", "当前未从结构化链路中抽取到确定答案。", cypher)


def handle_institution_serves_enterprises(query: str, parsed: Dict[str, Any]) -> Dict[str, Any]:
    subject = parsed["subject"]
    region_hint = parsed.get("region_hint", "")
    tech_hint = bool(parsed.get("tech_hint", False))

    tech_filter = ""
    if tech_hint:
        tech_filter = f"""
          AND (
                EXISTS {{
                    MATCH (e)-[:hasFeature]->(f:{label('QualificationCreditFeature')})
                    WHERE f.name CONTAINS '科技'
                }}
                OR e.name CONTAINS '科技'
              )
        """

    cypher_candidates = [
        (
            "path_1_fi_product_enterprise",
            f"""
            MATCH (fi:{label('FinancialInstitution')})
                  -[:providesProduct]->
                  (fp:{label('FinancialProduct')})
                  -[:servesEnterprise]->
                  (e:{label('Enterprise')})
            WHERE {_cypher_name_match("fi.name", "$name")}
              AND (
                    $region = ''
                    OR EXISTS {{
                        MATCH (e)-[:locatedIn]->(r:{label('Region')})
                        WHERE r.name CONTAINS $region
                    }}
                  )
              {tech_filter}
            RETURN DISTINCT e.name AS answer
            ORDER BY answer
            """,
        ),
        (
            "path_2_fi_loan_event_enterprise",
            f"""
            MATCH (fi:{label('FinancialInstitution')})
                  -[:issuesLoan]->
                  (le:{label('LoanEvent')})
                  -[:loanToEnterprise]->
                  (e:{label('Enterprise')})
            WHERE {_cypher_name_match("fi.name", "$name")}
              AND (
                    $region = ''
                    OR EXISTS {{
                        MATCH (e)-[:locatedIn]->(r:{label('Region')})
                        WHERE r.name CONTAINS $region
                    }}
                  )
              {tech_filter}
            RETURN DISTINCT e.name AS answer
            ORDER BY answer
            """,
        ),
        (
            "path_3_fi_direct_enterprise",
            f"""
            MATCH (fi:{label('FinancialInstitution')})
                  -[:servesEnterprise]->
                  (e:{label('Enterprise')})
            WHERE {_cypher_name_match("fi.name", "$name")}
              AND (
                    $region = ''
                    OR EXISTS {{
                        MATCH (e)-[:locatedIn]->(r:{label('Region')})
                        WHERE r.name CONTAINS $region
                    }}
                  )
              {tech_filter}
            RETURN DISTINCT e.name AS answer
            ORDER BY answer
            """,
        ),
    ]

    params = {"name": subject, "region": region_hint or ""}
    merged = []
    hit_cyphers = []

    for tag, cypher in cypher_candidates:
        rows = run_cypher(cypher, params)
        current_answers = dedup_sorted([row.get("answer") for row in rows])
        if current_answers:
            merged.extend(current_answers)
            hit_cyphers.append(f"// {tag}\n{cypher.strip()}")

    answers = dedup_sorted(merged)
    all_cypher = "\n\nUNION PATH\n\n".join([c for _, c in cypher_candidates])

    if answers:
        if region_hint and tech_hint:
            answer = f"{subject}支持的{region_hint}科技企业包括：{join_cn(answers)}。"
        elif region_hint:
            answer = f"{subject}支持的{region_hint}企业包括：{join_cn(answers)}。"
        else:
            answer = f"{subject}支持的企业包括：{join_cn(answers)}。"
        return make_result(
            query,
            "institution_serves_enterprises",
            subject,
            "structured",
            answer,
            "\n\nUNION PATH\n\n".join(hit_cyphers) if hit_cyphers else all_cypher,
        )

    return make_result(
        query,
        "institution_serves_enterprises",
        subject,
        "no_hit",
        "当前未从结构化链路中抽取到确定答案。",
        all_cypher,
    )


# =========================
# 路径族执行器
# =========================
def _match_name_clause(var_name: str) -> str:
    return _cypher_name_match(f"{var_name}.name", "$subject")


def _match_inst_clause(var_name: str) -> str:
    return _cypher_name_match(f"{var_name}.name", "$constraint_institution")


def run_path_policy_product_institution(query: str, parsed: Dict[str, Any]) -> Dict[str, Any]:
    subject = parsed["subject"]
    constraint_institution = parsed.get("constraint_institution", "").strip()
    return_mode = parsed.get("return_mode", "")

    inst_filter = ""
    if constraint_institution:
        inst_filter = f"AND {_match_inst_clause('fi')}"

    cypher = f"""
    MATCH (p:{label('Policy')})
          -[:supports]->
          (fp:{label('FinancialProduct')})
          <-[:providesProduct]-
          (fi:{label('FinancialInstitution')})
    WHERE {_match_name_clause('p')}
      {inst_filter}
    RETURN DISTINCT p.name AS policy_name, fp.name AS product_name, fi.name AS institution_name
    ORDER BY product_name, institution_name
    """
    rows = run_cypher(cypher, {"subject": subject, "constraint_institution": constraint_institution})
    if not rows:
        return make_result(query, parsed["question_type"], subject, "no_hit", "当前未从结构化链路中抽取到确定答案。", cypher)

    if return_mode == "products_filtered_by_institution":
        products = dedup_sorted([r["product_name"] for r in rows if r.get("product_name")])
        answer = f"{subject}支持的、由{constraint_institution}提供的产品包括：{join_cn(products)}。"
        return make_result(query, parsed["question_type"], subject, "structured", answer, cypher)

    mapping: Dict[str, List[str]] = {}
    for r in rows:
        p = r.get("product_name", "")
        fi = r.get("institution_name", "")
        if p and fi:
            mapping.setdefault(p, []).append(fi)

    parts = []
    for product in sorted(mapping.keys()):
        insts = dedup_sorted(mapping[product])
        parts.append(f"{product}由{join_cn(insts)}提供")
    answer = f"{subject}支持的产品对应提供机构包括：{'；'.join(parts)}。"
    return make_result(query, parsed["question_type"], subject, "structured", answer, cypher)


def run_path_institution_product_policy(query: str, parsed: Dict[str, Any]) -> Dict[str, Any]:
    subject = parsed["subject"]
    cypher = f"""
    MATCH (fi:{label('FinancialInstitution')})
          -[:providesProduct]->
          (fp:{label('FinancialProduct')})
          <-[:supports]-
          (p:{label('Policy')})
    WHERE {_match_name_clause('fi')}
    RETURN DISTINCT fi.name AS institution_name, fp.name AS product_name, p.name AS policy_name
    ORDER BY product_name, policy_name
    """
    rows = run_cypher(cypher, {"subject": subject})
    if not rows:
        return make_result(query, parsed["question_type"], subject, "no_hit", "当前未从结构化链路中抽取到确定答案。", cypher)

    mapping: Dict[str, List[str]] = {}
    for r in rows:
        product = r.get("product_name", "")
        policy = r.get("policy_name", "")
        if product and policy:
            mapping.setdefault(product, []).append(policy)

    parts = []
    for product in sorted(mapping.keys()):
        policies = dedup_sorted(mapping[product])
        parts.append(f"{product}被{join_cn(policies)}支持")
    answer = f"{subject}提供的产品对应支持政策包括：{'；'.join(parts)}。"
    return make_result(query, parsed["question_type"], subject, "structured", answer, cypher)


def run_path_policy_enterprise_feature(query: str, parsed: Dict[str, Any]) -> Dict[str, Any]:
    subject = parsed["subject"]
    cypher = f"""
    MATCH (p:{label('Policy')})
          -[:targetsEnterprise]->
          (e:{label('Enterprise')})
          -[:hasFeature]->
          (f:{label('QualificationCreditFeature')})
    WHERE {_match_name_clause('p')}
    RETURN DISTINCT p.name AS policy_name, e.name AS enterprise_name, f.name AS feature_name
    ORDER BY enterprise_name, feature_name
    """
    rows = run_cypher(cypher, {"subject": subject})
    if not rows:
        return make_result(query, parsed["question_type"], subject, "no_hit", "当前未从结构化链路中抽取到确定答案。", cypher)

    features = dedup_sorted([r["feature_name"] for r in rows if r.get("feature_name")])
    answer = f"{subject}覆盖支持企业涉及的资质包括：{join_cn(features)}。"
    return make_result(query, parsed["question_type"], subject, "structured", answer, cypher)


def run_path_policy_enterprise_industry(query: str, parsed: Dict[str, Any]) -> Dict[str, Any]:
    subject = parsed["subject"]
    cypher = f"""
    MATCH (p:{label('Policy')})
          -[:targetsEnterprise]->
          (e:{label('Enterprise')})
          -[:belongsToIndustry]->
          (i:{label('IndustrySegment')})
    WHERE {_match_name_clause('p')}
    RETURN DISTINCT p.name AS policy_name, e.name AS enterprise_name, i.name AS industry_name
    ORDER BY industry_name
    """
    rows = run_cypher(cypher, {"subject": subject})
    if not rows:
        return make_result(query, parsed["question_type"], subject, "no_hit", "当前未从结构化链路中抽取到确定答案。", cypher)

    industries = dedup_sorted([r["industry_name"] for r in rows if r.get("industry_name")])
    answer = f"{subject}覆盖支持企业涉及的产业细分包括：{join_cn(industries)}。"
    return make_result(query, parsed["question_type"], subject, "structured", answer, cypher)


def run_path_institution_product_enterprise(query: str, parsed: Dict[str, Any]) -> Dict[str, Any]:
    subject = parsed["subject"]
    cypher = f"""
    MATCH (fi:{label('FinancialInstitution')})
          -[:providesProduct]->
          (fp:{label('FinancialProduct')})
          -[:servesEnterprise]->
          (e:{label('Enterprise')})
    WHERE {_match_name_clause('fi')}
    RETURN DISTINCT fi.name AS institution_name, fp.name AS product_name, e.name AS enterprise_name
    ORDER BY enterprise_name
    """
    rows = run_cypher(cypher, {"subject": subject})
    if not rows:
        return make_result(query, parsed["question_type"], subject, "no_hit", "当前未从结构化链路中抽取到确定答案。", cypher)

    enterprises = dedup_sorted([r["enterprise_name"] for r in rows if r.get("enterprise_name")])
    answer = f"{subject}通过其产品服务的企业包括：{join_cn(enterprises)}。"
    return make_result(query, parsed["question_type"], subject, "structured", answer, cypher)


def run_path_enterprise_institution_product(query: str, parsed: Dict[str, Any]) -> Dict[str, Any]:
    subject = parsed["subject"]
    cypher = f"""
    MATCH (fi:{label('FinancialInstitution')})
          -[:providesProduct]->
          (fp:{label('FinancialProduct')})
          -[:servesEnterprise]->
          (e:{label('Enterprise')})
    WHERE {_match_name_clause('e')}
    RETURN DISTINCT fi.name AS institution_name, fp.name AS product_name, e.name AS enterprise_name
    ORDER BY institution_name, product_name
    """
    rows = run_cypher(cypher, {"subject": subject})
    if not rows:
        cypher = f"""
        MATCH (fi:{label('FinancialInstitution')})
              -[:issuesLoan]->
              (le:{label('LoanEvent')})
              -[:loanToEnterprise]->
              (e:{label('Enterprise')})
        WHERE {_match_name_clause('e')}
        RETURN DISTINCT fi.name AS institution_name, le.name AS product_name, e.name AS enterprise_name
        ORDER BY institution_name, product_name
        """
        rows = run_cypher(cypher, {"subject": subject})
        if not rows:
            return make_result(query, parsed["question_type"], subject, "no_hit", "当前未从结构化链路中抽取到确定答案。", cypher)

    pairs = []
    for r in rows:
        fi = r.get("institution_name", "")
        prod = r.get("product_name", "")
        if fi and prod:
            pairs.append(f"{fi}提供{prod}")
    pairs = dedup_keep_order(pairs)
    answer = f"{subject}获得的机构产品支持包括：{'；'.join(pairs)}。"
    return make_result(query, parsed["question_type"], subject, "structured", answer, cypher)


def run_freeqa_institution_product_overview(query: str, parsed: Dict[str, Any]) -> Dict[str, Any]:
    subject = parsed["subject"]

    cypher = f"""
    MATCH (fi:{label('FinancialInstitution')})
          -[:providesProduct]->
          (fp:{label('FinancialProduct')})
    WHERE {_match_name_clause('fi')}
    RETURN DISTINCT fi.name AS institution_name, fp.name AS product_name
    ORDER BY product_name
    """
    rows = run_cypher(cypher, {"subject": subject})
    products = dedup_sorted([r.get("product_name") for r in rows if r.get("product_name")])

    if products:
        preview = products[:8]
        answer = f"从当前图谱看，{subject}关联较紧、且有明确结构化链路的科技金融产品包括：{join_cn(preview)}。"
        if len(products) > len(preview):
            answer += f" 其中以这些产品为主，当前共检索到 {len(products)} 类相关产品。"
        else:
            answer += " 这些产品基本可以看作它在当前知识库中的主要科技金融产品。"
        return make_result(query, parsed["question_type"], subject, "structured", answer, cypher)

    return make_result(query, parsed["question_type"], subject, "no_hit", "当前未从结构化链路中抽取到确定答案。", cypher)



def run_freeqa_enterprise_profile(query: str, parsed: Dict[str, Any]) -> Dict[str, Any]:
    subject = parsed["subject"]

    cypher_region = f"""
    MATCH (e:{label('Enterprise')})-[:locatedIn]->(r:{label('Region')})
    WHERE {_match_name_clause('e')}
    RETURN DISTINCT r.name AS answer
    ORDER BY answer
    """
    cypher_industry = f"""
    MATCH (e:{label('Enterprise')})-[:belongsToIndustry]->(i:{label('IndustrySegment')})
    WHERE {_match_name_clause('e')}
    RETURN DISTINCT i.name AS answer
    ORDER BY answer
    """
    cypher_feature = f"""
    MATCH (e:{label('Enterprise')})-[:hasFeature]->(f:{label('QualificationCreditFeature')})
    WHERE {_match_name_clause('e')}
    RETURN DISTINCT f.name AS answer
    ORDER BY answer
    """
    cypher_policy = f"""
    MATCH (p:{label('Policy')})-[:targetsEnterprise]->(e:{label('Enterprise')})
    WHERE {_match_name_clause('e')}
    RETURN DISTINCT p.name AS answer
    ORDER BY answer
    """
    cypher_product = f"""
    MATCH (fi:{label('FinancialInstitution')})-[:providesProduct]->(fp:{label('FinancialProduct')})-[:servesEnterprise]->(e:{label('Enterprise')})
    WHERE {_match_name_clause('e')}
    RETURN DISTINCT fp.name AS answer
    ORDER BY answer
    """

    params = {"subject": subject}
    regions = dedup_sorted([r.get("answer") for r in run_cypher(cypher_region, params)])
    industries = dedup_sorted([r.get("answer") for r in run_cypher(cypher_industry, params)])
    features = dedup_sorted([r.get("answer") for r in run_cypher(cypher_feature, params)])
    policies = dedup_sorted([r.get("answer") for r in run_cypher(cypher_policy, params)])
    products = dedup_sorted([r.get("answer") for r in run_cypher(cypher_product, params)])

    if not (regions or industries or features or policies or products):
        full_cypher = "\n\n-- region --\n" + cypher_region + "\n\n-- industry --\n" + cypher_industry + "\n\n-- feature --\n" + cypher_feature
        return make_result(query, parsed["question_type"], subject, "no_hit", "当前未从结构化链路中抽取到确定答案。", full_cypher)

    parts = []
    if regions:
        parts.append(f"位于{join_cn(regions)}")
    if industries:
        parts.append(f"属于{join_cn(industries)}")
    if features:
        parts.append(f"具有{join_cn(features)}等资质特征")

    answer = f"{subject}在当前知识图谱中的企业画像可概括为："
    if parts:
        answer += "，".join(parts) + "。"
    else:
        answer += "已存在基础企业节点，但画像信息仍不完整。"

    if products:
        answer += f" 从科技金融支持链看，它还与{join_cn(products[:5])}等产品存在服务关联。"
    elif policies:
        answer += f" 从政策覆盖链看，它与{join_cn(policies[:3])}等政策存在覆盖关联。"

    full_cypher = "\n\n-- region --\n" + cypher_region + "\n\n-- industry --\n" + cypher_industry + "\n\n-- feature --\n" + cypher_feature + "\n\n-- policy --\n" + cypher_policy + "\n\n-- product --\n" + cypher_product
    return make_result(query, parsed["question_type"], subject, "structured", answer, full_cypher)



def run_freeqa_policy_product_enterprise_overview(query: str, parsed: Dict[str, Any]) -> Dict[str, Any]:
    subject = parsed["subject"]

    cypher_products = f"""
    MATCH (p:{label('Policy')})-[:supports]->(fp:{label('FinancialProduct')})
    WHERE {_match_name_clause('p')}
    RETURN DISTINCT fp.name AS answer
    ORDER BY answer
    """
    cypher_enterprises = f"""
    MATCH (p:{label('Policy')})-[:supports]->(fp:{label('FinancialProduct')})-[:servesEnterprise]->(e:{label('Enterprise')})
    WHERE {_match_name_clause('p')}
    RETURN DISTINCT e.name AS answer
    ORDER BY answer
    """
    params = {"subject": subject}
    products = dedup_sorted([r.get("answer") for r in run_cypher(cypher_products, params)])
    enterprises = dedup_sorted([r.get("answer") for r in run_cypher(cypher_enterprises, params)])

    if not (products or enterprises):
        full_cypher = "\n\n-- products --\n" + cypher_products + "\n\n-- enterprises --\n" + cypher_enterprises
        return make_result(query, parsed["question_type"], subject, "no_hit", "当前未从结构化链路中抽取到确定答案。", full_cypher)

    answer = f"从当前图谱看，{subject}主要先落到"
    if products:
        answer += f"{join_cn(products[:6])}等金融产品"
    else:
        answer += "相关金融产品"

    if enterprises:
        answer += f"，再通过产品服务链进一步覆盖{join_cn(enterprises[:5])}等企业。"
        if len(enterprises) > 5:
            answer += f" 当前共检索到 {len(enterprises)} 家相关企业。"
    else:
        answer += "，但当前图谱里尚未进一步连到明确企业节点。"

    answer += " 也就是说，它在图里呈现为“政策先支持产品，再由产品连接企业”的覆盖方式。"

    full_cypher = "\n\n-- products --\n" + cypher_products + "\n\n-- enterprises --\n" + cypher_enterprises
    return make_result(query, parsed["question_type"], subject, "structured", answer, full_cypher)



def run_freeqa_policy_landing_level(query: str, parsed: Dict[str, Any]) -> Dict[str, Any]:
    subject = parsed["subject"]

    cypher_products = f"""
    MATCH (p:{label('Policy')})-[:supports]->(fp:{label('FinancialProduct')})
    WHERE {_match_name_clause('p')}
    RETURN DISTINCT fp.name AS answer
    ORDER BY answer
    """
    cypher_enterprises = f"""
    MATCH (p:{label('Policy')})-[:supports]->(fp:{label('FinancialProduct')})-[:servesEnterprise]->(e:{label('Enterprise')})
    WHERE {_match_name_clause('p')}
    RETURN DISTINCT e.name AS answer
    ORDER BY answer
    """
    cypher_direct_enterprises = f"""
    MATCH (p:{label('Policy')})-[:targetsEnterprise]->(e:{label('Enterprise')})
    WHERE {_match_name_clause('p')}
    RETURN DISTINCT e.name AS answer
    ORDER BY answer
    """

    params = {"subject": subject}
    products = dedup_sorted([r.get("answer") for r in run_cypher(cypher_products, params)])
    enterprises = dedup_sorted([r.get("answer") for r in run_cypher(cypher_enterprises, params)])
    direct_enterprises = dedup_sorted([r.get("answer") for r in run_cypher(cypher_direct_enterprises, params)])

    if not (products or enterprises or direct_enterprises):
        full_cypher = (
            "\n\n-- products --\n" + cypher_products +
            "\n\n-- enterprises --\n" + cypher_enterprises +
            "\n\n-- direct_enterprises --\n" + cypher_direct_enterprises
        )
        return make_result(query, parsed["question_type"], subject, "no_hit", "当前未从结构化链路中抽取到确定答案。", full_cypher)

    if products and enterprises:
        answer = (
            f"从当前图谱看，{subject}已经不只是停留在政策引导层，而是能够明确落到具体产品层，"
            f"并进一步通过产品链路覆盖企业。当前可见的产品包括：{join_cn(products[:5])}；"
            f"继续沿产品链路可关联到{join_cn(enterprises[:5])}等企业。"
        )
    elif products:
        answer = (
            f"从当前图谱看，{subject}已经能够明确落到具体产品层，而不只是停留在政策引导层。"
            f"当前直接关联的产品包括：{join_cn(products[:5])}。"
        )
    elif direct_enterprises:
        answer = (
            f"从当前图谱看，{subject}目前更偏向政策覆盖/引导层，已见到它与{join_cn(direct_enterprises[:5])}等企业存在覆盖关联，"
            f"但尚未检索到清晰的产品层连接。"
        )
    else:
        answer = f"从当前图谱看，{subject}当前仍更偏向政策引导层，尚未形成稳定的产品与企业链路。"

    full_cypher = (
        "\n\n-- products --\n" + cypher_products +
        "\n\n-- enterprises --\n" + cypher_enterprises +
        "\n\n-- direct_enterprises --\n" + cypher_direct_enterprises
    )
    return make_result(query, parsed["question_type"], subject, "structured", answer, full_cypher)


def run_freeqa_policy_support_objects_overview(query: str, parsed: Dict[str, Any]) -> Dict[str, Any]:
    subject = parsed["subject"]

    cypher_products = f"""
    MATCH (p:{label('Policy')})-[:supports]->(fp:{label('FinancialProduct')})
    WHERE {_match_name_clause('p')}
    RETURN DISTINCT fp.name AS answer
    ORDER BY answer
    """
    cypher_institutions = f"""
    MATCH (p:{label('Policy')})-[:supports]->(fp:{label('FinancialProduct')})<-[:providesProduct]-(fi:{label('FinancialInstitution')})
    WHERE {_match_name_clause('p')}
    RETURN DISTINCT fi.name AS answer
    ORDER BY answer
    """
    cypher_enterprises = f"""
    MATCH (p:{label('Policy')})-[:supports]->(fp:{label('FinancialProduct')})-[:servesEnterprise]->(e:{label('Enterprise')})
    WHERE {_match_name_clause('p')}
    RETURN DISTINCT e.name AS answer
    ORDER BY answer
    """
    cypher_direct_enterprises = f"""
    MATCH (p:{label('Policy')})-[:targetsEnterprise]->(e:{label('Enterprise')})
    WHERE {_match_name_clause('p')}
    RETURN DISTINCT e.name AS answer
    ORDER BY answer
    """

    params = {"subject": subject}
    products = dedup_sorted([r.get("answer") for r in run_cypher(cypher_products, params)])
    institutions = dedup_sorted([r.get("answer") for r in run_cypher(cypher_institutions, params)])
    enterprises = dedup_sorted([r.get("answer") for r in run_cypher(cypher_enterprises, params)])
    direct_enterprises = dedup_sorted([r.get("answer") for r in run_cypher(cypher_direct_enterprises, params)])

    if not (products or institutions or enterprises or direct_enterprises):
        full_cypher = (
            "\n\n-- products --\n" + cypher_products +
            "\n\n-- institutions --\n" + cypher_institutions +
            "\n\n-- enterprises --\n" + cypher_enterprises +
            "\n\n-- direct_enterprises --\n" + cypher_direct_enterprises
        )
        return make_result(query, parsed["question_type"], subject, "no_hit", "当前未从结构化链路中抽取到确定答案。", full_cypher)

    parts = []
    if products:
        parts.append(f"产品层主要有{join_cn(products[:5])}")
    if institutions:
        parts.append(f"机构层可进一步关联到{join_cn(institutions[:5])}")
    if enterprises:
        parts.append(f"企业层可通过产品链路覆盖{join_cn(enterprises[:5])}等企业")
    elif direct_enterprises:
        parts.append(f"企业覆盖层可见{join_cn(direct_enterprises[:5])}等企业")

    answer = f"在当前图谱里，{subject}主要连接到的科技金融支持对象包括：" + "；".join(parts) + "。"

    full_cypher = (
        "\n\n-- products --\n" + cypher_products +
        "\n\n-- institutions --\n" + cypher_institutions +
        "\n\n-- enterprises --\n" + cypher_enterprises +
        "\n\n-- direct_enterprises --\n" + cypher_direct_enterprises
    )
    return make_result(query, parsed["question_type"], subject, "structured", answer, full_cypher)



def run_freeqa_policies_cover_tech_enterprises(query: str, parsed: Dict[str, Any]) -> Dict[str, Any]:
    cypher = f"""
    MATCH (p:{label('Policy')})-[:supports]->(fp:{label('FinancialProduct')})-[:servesEnterprise]->(e:{label('Enterprise')})
    WHERE EXISTS {{
        MATCH (e)-[:hasFeature]->(f:{label('QualificationCreditFeature')})
        WHERE f.name CONTAINS '科技'
    }}
       OR e.name CONTAINS '科技'
    RETURN DISTINCT p.name AS policy_name, fp.name AS product_name, e.name AS enterprise_name
    ORDER BY policy_name, product_name, enterprise_name
    """
    rows = run_cypher(cypher, {})
    if not rows:
        return make_result(query, parsed["question_type"], "", "no_hit", "当前未从结构化链路中抽取到确定答案。", cypher)

    policy_to_products = {}
    policy_to_enterprises = {}
    for r in rows:
        p_name = (r.get("policy_name") or "").strip()
        fp_name = (r.get("product_name") or "").strip()
        e_name = (r.get("enterprise_name") or "").strip()
        if p_name:
            if fp_name:
                policy_to_products.setdefault(p_name, []).append(fp_name)
            if e_name:
                policy_to_enterprises.setdefault(p_name, []).append(e_name)

    policies = dedup_sorted(list(policy_to_products.keys()) + list(policy_to_enterprises.keys()))
    parts = []
    for policy in policies[:5]:
        products = dedup_sorted(policy_to_products.get(policy, []))
        enterprises = dedup_sorted(policy_to_enterprises.get(policy, []))
        frag = policy
        if products:
            frag += f"可通过{join_cn(products[:3])}"
        if enterprises:
            frag += f"覆盖{join_cn(enterprises[:2])}等科技型企业"
        parts.append(frag)

    answer = f"从当前图谱看，能够通过产品链路覆盖到科技型企业的政策包括：{join_cn(policies[:8])}。"
    if parts:
        answer += " 例如：" + "；".join(parts) + "。"
    if len(policies) > 8:
        answer += f" 当前共检索到 {len(policies)} 项相关政策。"

    return make_result(query, parsed["question_type"], "", "structured", answer, cypher)


def run_freeqa_policies_reach_institution(query: str, parsed: Dict[str, Any]) -> Dict[str, Any]:
    institution = parsed.get("constraint_institution", "").strip()

    cypher = f"""
    MATCH (p:{label('Policy')})-[:supports]->(fp:{label('FinancialProduct')})<-[:providesProduct]-(fi:{label('FinancialInstitution')})
    WHERE {_match_inst_clause('fi')}
    RETURN DISTINCT p.name AS policy_name, fp.name AS product_name, fi.name AS institution_name
    ORDER BY policy_name, product_name
    """
    rows = run_cypher(cypher, {"constraint_institution": institution})
    if not rows:
        return make_result(query, parsed["question_type"], institution, "no_hit", "当前未从结构化链路中抽取到确定答案。", cypher)

    policy_to_products = {}
    for r in rows:
        p_name = (r.get("policy_name") or "").strip()
        fp_name = (r.get("product_name") or "").strip()
        if p_name and fp_name:
            policy_to_products.setdefault(p_name, []).append(fp_name)

    policies = dedup_sorted(list(policy_to_products.keys()))
    parts = []
    for policy in policies[:5]:
        products = dedup_sorted(policy_to_products.get(policy, []))
        if products:
            parts.append(f"{policy}可通过{join_cn(products[:3])}连到{institution}")

    answer = f"支持的产品最终能够连到{institution}的政策包括：{join_cn(policies[:8])}。"
    if parts:
        answer += " 例如：" + "；".join(parts) + "。"
    if len(policies) > 8:
        answer += f" 当前共检索到 {len(policies)} 项相关政策。"

    return make_result(query, parsed["question_type"], institution, "structured", answer, cypher)



def run_freeqa_featured_enterprise_products_by_institution(query: str, parsed: Dict[str, Any]) -> Dict[str, Any]:
    cypher = f"""
    MATCH (fi:{label('FinancialInstitution')})-[:providesProduct]->(fp:{label('FinancialProduct')})-[:servesEnterprise]->(e:{label('Enterprise')})-[:hasFeature]->(f:{label('QualificationCreditFeature')})
    WHERE f.name CONTAINS '科技型中小企业'
    RETURN DISTINCT fp.name AS product_name, fi.name AS institution_name, e.name AS enterprise_name
    ORDER BY product_name, institution_name, enterprise_name
    """
    rows = run_cypher(cypher, {})
    if not rows:
        return make_result(query, parsed["question_type"], "", "no_hit", "当前未从结构化链路中抽取到确定答案。", cypher)

    product_to_institutions = {}
    product_to_enterprises = {}
    for r in rows:
        product = (r.get("product_name") or "").strip()
        inst = (r.get("institution_name") or "").strip()
        ent = (r.get("enterprise_name") or "").strip()
        if not product:
            continue
        if inst:
            product_to_institutions.setdefault(product, []).append(inst)
        if ent:
            product_to_enterprises.setdefault(product, []).append(ent)

    ranked = []
    for product in set(list(product_to_institutions.keys()) + list(product_to_enterprises.keys())):
        insts = dedup_sorted(product_to_institutions.get(product, []))
        ents = dedup_sorted(product_to_enterprises.get(product, []))
        ranked.append((len(ents), len(insts), product, insts, ents))

    ranked.sort(key=lambda x: (-x[0], -x[1], x[2]))
    preview = ranked[:8]

    parts = []
    all_products = []
    for ent_cnt, inst_cnt, product, insts, ents in preview:
        all_products.append(product)
        if insts:
            parts.append(f"{product}由{join_cn(insts[:3])}提供")
        else:
            parts.append(product)

    answer = f"从当前图谱看，面向科技型中小企业的金融产品主要包括：{join_cn(all_products)}。"
    if parts:
        answer += " 其中可明确对应机构的包括：" + "；".join(parts) + "。"
    if len(ranked) > len(preview):
        answer += f" 当前共检索到 {len(ranked)} 类相关产品。"

    return make_result(query, parsed["question_type"], "", "structured", answer, cypher)


def run_freeqa_dual_feature_enterprise_product_match(query: str, parsed: Dict[str, Any]) -> Dict[str, Any]:
    cypher = f"""
    MATCH (e:{label('Enterprise')})-[:hasFeature]->(f1:{label('QualificationCreditFeature')})
    MATCH (e)-[:hasFeature]->(f2:{label('QualificationCreditFeature')})
    MATCH (fi:{label('FinancialInstitution')})-[:providesProduct]->(fp:{label('FinancialProduct')})-[:servesEnterprise]->(e)
    WHERE f1.name CONTAINS '科技型中小企业'
      AND f2.name CONTAINS '专精特新'
    RETURN DISTINCT fp.name AS product_name, fi.name AS institution_name, e.name AS enterprise_name
    ORDER BY product_name, institution_name, enterprise_name
    """
    rows = run_cypher(cypher, {})
    if not rows:
        return make_result(query, parsed["question_type"], "", "no_hit", "当前未从结构化链路中抽取到确定答案。", cypher)

    product_to_institutions = {}
    product_to_enterprises = {}
    for r in rows:
        product = (r.get("product_name") or "").strip()
        inst = (r.get("institution_name") or "").strip()
        ent = (r.get("enterprise_name") or "").strip()
        if not product:
            continue
        if inst:
            product_to_institutions.setdefault(product, []).append(inst)
        if ent:
            product_to_enterprises.setdefault(product, []).append(ent)

    ranked = []
    for product in set(list(product_to_institutions.keys()) + list(product_to_enterprises.keys())):
        insts = dedup_sorted(product_to_institutions.get(product, []))
        ents = dedup_sorted(product_to_enterprises.get(product, []))
        ranked.append((len(ents), len(insts), product, insts, ents))

    ranked.sort(key=lambda x: (-x[0], -x[1], x[2]))
    preview = ranked[:8]

    products = [x[2] for x in preview]
    parts = []
    for ent_cnt, inst_cnt, product, insts, ents in preview[:5]:
        frag = product
        if insts:
            frag += f"（对应机构如{join_cn(insts[:3])}）"
        parts.append(frag)

    answer = f"从当前图谱看，如果一家企业同时具备科技型中小企业和专精特新特征，通常更容易匹配到的产品包括：{join_cn(products)}。"
    if parts:
        answer += " 其中较典型的有：" + "；".join(parts) + "。"
    if ranked:
        answer += f" 这类判断是根据当前图谱中同时具备这两类特征企业的产品服务关联归纳得到的。"

    return make_result(query, parsed["question_type"], "", "structured", answer, cypher)


FREEQA_EXECUTORS = {
    "freeqa_institution_product_overview": run_freeqa_institution_product_overview,
    "freeqa_enterprise_profile": run_freeqa_enterprise_profile,
    "freeqa_policy_product_enterprise_overview": run_freeqa_policy_product_enterprise_overview,
    "freeqa_policy_landing_level": run_freeqa_policy_landing_level,
    "freeqa_policy_support_objects_overview": run_freeqa_policy_support_objects_overview,
    "freeqa_policies_cover_tech_enterprises": run_freeqa_policies_cover_tech_enterprises,
    "freeqa_policies_reach_institution": run_freeqa_policies_reach_institution,
    "freeqa_featured_enterprise_products_by_institution": run_freeqa_featured_enterprise_products_by_institution,
    "freeqa_dual_feature_enterprise_product_match": run_freeqa_dual_feature_enterprise_product_match,
}


PATH_EXECUTORS = {
    "path_policy_product_institution": run_path_policy_product_institution,
    "path_institution_product_policy": run_path_institution_product_policy,
    "path_policy_enterprise_feature": run_path_policy_enterprise_feature,
    "path_policy_enterprise_industry": run_path_policy_enterprise_industry,
    "path_institution_product_enterprise": run_path_institution_product_enterprise,
    "path_enterprise_institution_product": run_path_enterprise_institution_product,
}


# =========================
# 问句识别
# =========================
def parse_institution_serves_enterprises(query: str) -> Optional[Dict[str, Any]]:
    q = normalize_query_text(query)
    patterns = [
        (r"^(?P<subject>.+?)(?:支持|服务)了?哪些甘肃科技企业\??$", "甘肃", True, "forward"),
        (r"^(?P<subject>.+?)(?:支持|服务)哪些甘肃科技企业\??$", "甘肃", True, "forward"),
        (r"^(?P<subject>.+?)(?:支持|服务)了?哪些企业\??$", "", False, "forward"),
        (r"^(?P<subject>.+?)(?:支持|服务)哪些企业\??$", "", False, "forward"),
        (r"^哪些甘肃科技企业获得了(?P<subject>.+?)(?:的)?(?:支持|服务)\??$", "甘肃", True, "reverse"),
        (r"^哪些企业获得了(?P<subject>.+?)(?:的)?(?:支持|服务)\??$", "", False, "reverse"),
        (r"^被(?P<subject>.+?)(?:支持|服务)的甘肃科技企业有哪些\??$", "甘肃", True, "reverse"),
        (r"^被(?P<subject>.+?)(?:支持|服务)的企业有哪些\??$", "", False, "reverse"),
    ]

    for pat, region_hint, tech_hint, query_style in patterns:
        m = re.match(pat, q)
        if m:
            subject = m.group("subject").strip()
            if subject:
                return {
                    "mode": "relation_family",
                    "question_type": "institution_serves_enterprises",
                    "subject": subject,
                    "region_hint": region_hint,
                    "tech_hint": tech_hint,
                    "query_style": query_style,
                }
    return None


def detect_path_family(query: str) -> Optional[Dict[str, Any]]:
    q = normalize_query_text(query)
    for family, cfg in PATH_FAMILIES.items():
        for pattern_cfg in cfg["patterns"]:
            m = re.match(pattern_cfg["regex"], q)
            if not m:
                continue
            gd = m.groupdict()
            subject = gd.get("subject", "").strip()
            if not subject:
                continue
            payload = {
                "mode": "path_family",
                "question_type": family,
                "subject": subject,
                "return_mode": pattern_cfg.get("return_mode", ""),
            }
            if gd.get("constraint_institution"):
                payload["constraint_institution"] = gd["constraint_institution"].strip()
            return payload
    return None


def detect_relation_family(query: str) -> Optional[Dict[str, Any]]:
    q = normalize_query_text(query)
    for family, cfg in RELATION_FAMILIES.items():
        for pat in cfg["patterns"]:
            m = re.match(pat, q)
            if not m:
                continue
            gd = m.groupdict()
            subject = gd.get("subject", "").strip()
            if subject:
                return {
                    "mode": "relation_family",
                    "question_type": family,
                    "subject": subject,
                }
    return None


def detect_freeqa_family(query: str) -> Optional[Dict[str, Any]]:
    q = normalize_query_text(query)
    for family, cfg in FREEQA_FAMILIES.items():
        for pat in cfg["patterns"]:
            m = re.match(pat, q)
            if not m:
                continue
            gd = m.groupdict()
            subject = (gd.get("subject", "") or "").strip()
            constraint_institution = (gd.get("constraint_institution", "") or "").strip()

            payload = {
                "mode": "freeqa_family",
                "question_type": family,
                "subject": subject,
            }
            if constraint_institution:
                payload["constraint_institution"] = constraint_institution

            if subject or constraint_institution or not gd:
                return payload
    return None
def detect_question(query: str) -> Optional[Dict[str, Any]]:
    parsed = parse_institution_serves_enterprises(query)
    if parsed is not None:
        return parsed

    parsed = detect_path_family(query)
    if parsed is not None:
        return parsed

    parsed = detect_freeqa_family(query)
    if parsed is not None:
        return parsed

    parsed = detect_relation_family(query)
    if parsed is not None:
        return parsed

    return None

# =========================
# 文本兜底总入口
# =========================
def answer_from_local_retrieval(query: str, parsed: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    qtype = parsed.get("question_type", "")
    if qtype not in QUESTION_GUARDS:
        return None
    return guarded_retrieval_fallback(query, parsed)


# =========================
# 主流程
# =========================
def answer_hybrid(query: str) -> Dict[str, Any]:
    parsed = detect_question(query)

    if parsed is None:
        return make_result(
            query=query,
            question_type="unsupported",
            subject="",
            route="unsupported",
            answer="当前暂不支持该问句模板。",
            cypher="",
            extra={"is_refusal": False},
        )

    mode = parsed["mode"]
    qtype = parsed["question_type"]

    if mode == "relation_family":
        if qtype == "institution_serves_enterprises":
            structured_result = handle_institution_serves_enterprises(query, parsed)
        else:
            structured_result = run_relation_family(query, parsed)
    elif mode == "path_family":
        executor = PATH_EXECUTORS[qtype]
        structured_result = executor(query, parsed)
    elif mode == "freeqa_family":
        executor = FREEQA_EXECUTORS[qtype]
        structured_result = executor(query, parsed)
    else:
        structured_result = make_result(
            query=query,
            question_type=qtype,
            subject=parsed.get("subject", ""),
            route="unsupported",
            answer="当前暂不支持该问句模板。",
            cypher="",
            extra={"is_refusal": False},
        )

    if structured_result["route"] == "structured":
        return structured_result

    fallback_result = answer_from_local_retrieval(query, parsed)
    if fallback_result is not None:
        return fallback_result

    return make_refusal_result(
        query=query,
        parsed=parsed,
        cypher=structured_result.get("cypher", ""),
        reason="unsupported_relation_or_no_evidence",
    )



def build_display_cypher(question_type: str, actual_cypher: str = "") -> str:
    templates = {
        "institution_provides_what_product": f"""
MATCH (fi:{label('FinancialInstitution')})-[:providesProduct]->(fp:{label('FinancialProduct')})
WHERE /* normalized name match */ fi.name ~ $name
RETURN DISTINCT fp.name AS answer
ORDER BY answer
""".strip(),

        "policy_supports_what_product": f"""
MATCH (s)-[:supports]->(fp:{label('FinancialProduct')})
WHERE /* normalized name match */ s.name ~ $name
  AND /* label guard */ any(lbl IN labels(s) WHERE lbl IN $allowed_labels)
RETURN DISTINCT fp.name AS answer
ORDER BY answer
""".strip(),

        "enterprise_belongs_industry": f"""
MATCH (e:{label('Enterprise')})-[:belongsToIndustry]->(i:{label('IndustrySegment')})
WHERE /* normalized name match */ e.name ~ $name
RETURN DISTINCT i.name AS answer
ORDER BY answer
""".strip(),

        "enterprise_has_feature": f"""
MATCH (e:{label('Enterprise')})-[:hasFeature]->(f:{label('QualificationCreditFeature')})
WHERE /* normalized name match */ e.name ~ $name
RETURN DISTINCT f.name AS answer
ORDER BY answer
""".strip(),

        "enterprise_targeted_by_policies": f"""
MATCH (p:{label('Policy')})-[:targetsEnterprise]->(e:{label('Enterprise')})
WHERE /* normalized name match */ e.name ~ $name
RETURN DISTINCT p.name AS answer
ORDER BY answer
""".strip(),

        "product_provided_by_institution": f"""
MATCH (fi:{label('FinancialInstitution')})-[:providesProduct]->(fp:{label('FinancialProduct')})
WHERE /* normalized name match */ fp.name ~ $name
RETURN DISTINCT fi.name AS answer
ORDER BY answer
""".strip(),

        "product_supported_by_policies": f"""
MATCH (p:{label('Policy')})-[:supports]->(x)
WHERE /* normalized name match */ x.name ~ $name
RETURN DISTINCT p.name AS answer
ORDER BY answer
""".strip(),

        "path_policy_product_institution": f"""
MATCH (p:{label('Policy')})-[:supports]->(fp:{label('FinancialProduct')})<-[:providesProduct]-(fi:{label('FinancialInstitution')})
WHERE /* normalized policy match */ p.name ~ $subject
  AND /* optional normalized institution match */ fi.name ~ $constraint_institution
RETURN DISTINCT p.name AS policy_name, fp.name AS product_name, fi.name AS institution_name
ORDER BY product_name, institution_name
""".strip(),

        "path_institution_product_policy": f"""
MATCH (fi:{label('FinancialInstitution')})-[:providesProduct]->(fp:{label('FinancialProduct')})<-[:supports]-(p:{label('Policy')})
WHERE /* normalized institution match */ fi.name ~ $subject
RETURN DISTINCT fi.name AS institution_name, fp.name AS product_name, p.name AS policy_name
ORDER BY product_name, policy_name
""".strip(),

        "path_policy_enterprise_feature": f"""
MATCH (p:{label('Policy')})-[:targetsEnterprise]->(e:{label('Enterprise')})-[:hasFeature]->(f:{label('QualificationCreditFeature')})
WHERE /* normalized policy match */ p.name ~ $subject
RETURN DISTINCT p.name AS policy_name, e.name AS enterprise_name, f.name AS feature_name
ORDER BY enterprise_name, feature_name
""".strip(),

        "path_policy_enterprise_industry": f"""
MATCH (p:{label('Policy')})-[:targetsEnterprise]->(e:{label('Enterprise')})-[:belongsToIndustry]->(i:{label('IndustrySegment')})
WHERE /* normalized policy match */ p.name ~ $subject
RETURN DISTINCT p.name AS policy_name, e.name AS enterprise_name, i.name AS industry_name
ORDER BY industry_name
""".strip(),

        "path_institution_product_enterprise": f"""
MATCH (fi:{label('FinancialInstitution')})-[:providesProduct]->(fp:{label('FinancialProduct')})-[:servesEnterprise]->(e:{label('Enterprise')})
WHERE /* normalized institution match */ fi.name ~ $subject
RETURN DISTINCT fi.name AS institution_name, fp.name AS product_name, e.name AS enterprise_name
ORDER BY enterprise_name
""".strip(),

        "path_enterprise_institution_product": f"""
MATCH (fi:{label('FinancialInstitution')})-[:providesProduct]->(fp:{label('FinancialProduct')})-[:servesEnterprise]->(e:{label('Enterprise')})
WHERE /* normalized enterprise match */ e.name ~ $subject
RETURN DISTINCT fi.name AS institution_name, fp.name AS product_name, e.name AS enterprise_name
ORDER BY institution_name, product_name
""".strip(),

        "freeqa_institution_product_overview": f"""
MATCH (fi:{label('FinancialInstitution')})-[:providesProduct]->(fp:{label('FinancialProduct')})
WHERE /* normalized institution match */ fi.name ~ $subject
RETURN DISTINCT fi.name AS institution_name, fp.name AS product_name
ORDER BY product_name
""".strip(),

        "freeqa_enterprise_profile": f"""
-- region --
MATCH (e:{label('Enterprise')})-[:locatedIn]->(r:{label('Region')})
WHERE /* normalized enterprise match */ e.name ~ $subject
RETURN DISTINCT r.name AS answer
ORDER BY answer

-- industry --
MATCH (e:{label('Enterprise')})-[:belongsToIndustry]->(i:{label('IndustrySegment')})
WHERE /* normalized enterprise match */ e.name ~ $subject
RETURN DISTINCT i.name AS answer
ORDER BY answer

-- feature --
MATCH (e:{label('Enterprise')})-[:hasFeature]->(f:{label('QualificationCreditFeature')})
WHERE /* normalized enterprise match */ e.name ~ $subject
RETURN DISTINCT f.name AS answer
ORDER BY answer

-- policy --
MATCH (p:{label('Policy')})-[:targetsEnterprise]->(e:{label('Enterprise')})
WHERE /* normalized enterprise match */ e.name ~ $subject
RETURN DISTINCT p.name AS answer
ORDER BY answer

-- product --
MATCH (fi:{label('FinancialInstitution')})-[:providesProduct]->(fp:{label('FinancialProduct')})-[:servesEnterprise]->(e:{label('Enterprise')})
WHERE /* normalized enterprise match */ e.name ~ $subject
RETURN DISTINCT fp.name AS answer
ORDER BY answer
""".strip(),

        "freeqa_policy_product_enterprise_overview": f"""
-- products --
MATCH (p:{label('Policy')})-[:supports]->(fp:{label('FinancialProduct')})
WHERE /* normalized policy match */ p.name ~ $subject
RETURN DISTINCT fp.name AS answer
ORDER BY answer

-- enterprises --
MATCH (p:{label('Policy')})-[:supports]->(fp:{label('FinancialProduct')})-[:servesEnterprise]->(e:{label('Enterprise')})
WHERE /* normalized policy match */ p.name ~ $subject
RETURN DISTINCT e.name AS answer
ORDER BY answer
""".strip(),

        "freeqa_policy_landing_level": f"""
-- products --
MATCH (p:{label('Policy')})-[:supports]->(fp:{label('FinancialProduct')})
WHERE /* normalized policy match */ p.name ~ $subject
RETURN DISTINCT fp.name AS answer
ORDER BY answer

-- enterprises --
MATCH (p:{label('Policy')})-[:supports]->(fp:{label('FinancialProduct')})-[:servesEnterprise]->(e:{label('Enterprise')})
WHERE /* normalized policy match */ p.name ~ $subject
RETURN DISTINCT e.name AS answer
ORDER BY answer

-- direct_enterprises --
MATCH (p:{label('Policy')})-[:targetsEnterprise]->(e:{label('Enterprise')})
WHERE /* normalized policy match */ p.name ~ $subject
RETURN DISTINCT e.name AS answer
ORDER BY answer
""".strip(),

        "freeqa_policy_support_objects_overview": f"""
-- products --
MATCH (p:{label('Policy')})-[:supports]->(fp:{label('FinancialProduct')})
WHERE /* normalized policy match */ p.name ~ $subject
RETURN DISTINCT fp.name AS answer
ORDER BY answer

-- institutions --
MATCH (p:{label('Policy')})-[:supports]->(fp:{label('FinancialProduct')})<-[:providesProduct]-(fi:{label('FinancialInstitution')})
WHERE /* normalized policy match */ p.name ~ $subject
RETURN DISTINCT fi.name AS answer
ORDER BY answer

-- enterprises --
MATCH (p:{label('Policy')})-[:supports]->(fp:{label('FinancialProduct')})-[:servesEnterprise]->(e:{label('Enterprise')})
WHERE /* normalized policy match */ p.name ~ $subject
RETURN DISTINCT e.name AS answer
ORDER BY answer

-- direct_enterprises --
MATCH (p:{label('Policy')})-[:targetsEnterprise]->(e:{label('Enterprise')})
WHERE /* normalized policy match */ p.name ~ $subject
RETURN DISTINCT e.name AS answer
ORDER BY answer
""".strip(),

        "freeqa_policies_cover_tech_enterprises": f"""
MATCH (p:{label('Policy')})-[:supports]->(fp:{label('FinancialProduct')})-[:servesEnterprise]->(e:{label('Enterprise')})
WHERE EXISTS {{
    MATCH (e)-[:hasFeature]->(f:{label('QualificationCreditFeature')})
    WHERE f.name CONTAINS '科技'
}}
   OR e.name CONTAINS '科技'
RETURN DISTINCT p.name AS policy_name, fp.name AS product_name, e.name AS enterprise_name
ORDER BY policy_name, product_name, enterprise_name
""".strip(),

        "freeqa_policies_reach_institution": f"""
MATCH (p:{label('Policy')})-[:supports]->(fp:{label('FinancialProduct')})<-[:providesProduct]-(fi:{label('FinancialInstitution')})
WHERE /* normalized institution match */ fi.name ~ $constraint_institution
RETURN DISTINCT p.name AS policy_name, fp.name AS product_name, fi.name AS institution_name
ORDER BY policy_name, product_name
""".strip(),

        "freeqa_featured_enterprise_products_by_institution": f"""
MATCH (fi:{label('FinancialInstitution')})-[:providesProduct]->(fp:{label('FinancialProduct')})-[:servesEnterprise]->(e:{label('Enterprise')})-[:hasFeature]->(f:{label('QualificationCreditFeature')})
WHERE f.name CONTAINS '科技型中小企业'
RETURN DISTINCT fp.name AS product_name, fi.name AS institution_name, e.name AS enterprise_name
ORDER BY product_name, institution_name, enterprise_name
""".strip(),

        "freeqa_dual_feature_enterprise_product_match": f"""
MATCH (e:{label('Enterprise')})-[:hasFeature]->(f1:{label('QualificationCreditFeature')})
MATCH (e)-[:hasFeature]->(f2:{label('QualificationCreditFeature')})
MATCH (fi:{label('FinancialInstitution')})-[:providesProduct]->(fp:{label('FinancialProduct')})-[:servesEnterprise]->(e)
WHERE f1.name CONTAINS '科技型中小企业'
  AND f2.name CONTAINS '专精特新'
RETURN DISTINCT fp.name AS product_name, fi.name AS institution_name, e.name AS enterprise_name
ORDER BY product_name, institution_name, enterprise_name
""".strip(),
    }

    if question_type in templates:
        return templates[question_type]

    if actual_cypher and "replace(replace(" in actual_cypher:
        return "/* normalized-match cypher omitted in display; export SHOW_ACTUAL_CYPHER=1 to inspect the real execution cypher */"

    return actual_cypher

# =========================
# 输出
# =========================
def print_result(result: Dict[str, Any]) -> None:
    print(f"query = {result.get('query', '')}")
    print(f"question_type = {result.get('question_type', '')}")
    print(f"subject = {result.get('subject', '')}")
    print()
    print(f"route = {result.get('route', '')}")
    if result.get("is_refusal"):
        print("is_refusal = True")
    print()

    print("===== ANSWER =====")
    print(result.get("answer", ""))
    print()

    if result.get("evidence_paths"):
        print("===== EVIDENCE PATHS =====")
        for p in result["evidence_paths"]:
            print(p)
        print()

    if result.get("evidence_snippets"):
        print("===== EVIDENCE SNIPPETS =====")
        for s in result["evidence_snippets"]:
            print(s)
        print()

    if result.get("retrieval_scores"):
        print("===== RETRIEVAL SCORES =====")
        for s in result["retrieval_scores"]:
            print(s)
        print()

    print("===== CYPHER =====")
    display_cypher = build_display_cypher(
        result.get("question_type", ""),
        result.get("cypher", "")
    )
    print(display_cypher)

    if os.getenv("SHOW_ACTUAL_CYPHER", "0") == "1" and result.get("cypher", ""):
        print()
        print("===== ACTUAL CYPHER =====")
        print(result.get("cypher", ""))


def main():
    if len(sys.argv) < 2:
        print('Usage: python retrieval_only/scripts/answer_hybrid_v5_path_framework.py "你的问题"')
        sys.exit(1)

    query = sys.argv[1]
    try:
        result = answer_hybrid(query)
        print_result(result)
    finally:
        close_driver()


if __name__ == "__main__":
    main()
