# -*- coding: utf-8 -*-
import re
from pathlib import Path
import os
import subprocess
import json
import html
from typing import Dict, Any, List, Tuple

import streamlit as st
from neo4j import GraphDatabase


try:
    st.set_page_config(page_title="知识图谱可视化", page_icon="🕸️", layout="wide")
except Exception:
    pass


DEFAULT_NAMESPACE = "GansuTechFinanceDevV1Enhance"


NODE_STYLE = {
    "Policy": {"color": "#F94144", "label": "政策 Policy"},
    "GovernmentAgency": {"color": "#577590", "label": "政府部门 GovernmentAgency"},
    "FinancialInstitution": {"color": "#43AA8B", "label": "金融机构 FinancialInstitution"},
    "FinancialProduct": {"color": "#F8961E", "label": "金融产品 FinancialProduct"},
    "Enterprise": {"color": "#9B5DE5", "label": "企业 Enterprise"},
    "Region": {"color": "#277DA1", "label": "地区 Region"},
    "IndustrySegment": {"color": "#F9C74F", "label": "行业 IndustrySegment"},
    "QualificationCreditFeature": {"color": "#90BE6D", "label": "企业特征 QualificationCreditFeature"},
    "ServicePlatform": {"color": "#4D908E", "label": "服务平台 ServicePlatform"},
    "LoanEvent": {"color": "#F15BB5", "label": "贷款事件 LoanEvent"},
    "SubsidyEvent": {"color": "#00BBF9", "label": "补贴事件 SubsidyEvent"},
    "Unknown": {"color": "#ADB5BD", "label": "未知类型 Unknown"},
}


CREDIT_STYLE = {
    "A": {"color": "#2A9D8F", "width": 5, "label": "A：高可信 / 硬证据"},
    "B": {"color": "#E9C46A", "width": 4, "label": "B：中可信 / 半结构化证据"},
    "C": {"color": "#E76F51", "width": 3, "label": "C：弱证据 / 文本推断证据"},
    "NONE": {"color": "#868E96", "width": 2, "label": "无 creditLevel：普通关系"},
}



RULE_REL_TYPES = {
    "potentiallyMatchesPolicy",
    "potentiallyMatchesProduct",
    "policyCoversRegion",
    "policyCoversIndustry",
    "productFitsEnterpriseFeature",
    "fitsEnterpriseFeature",
    "ruleMatchesPolicy",
    "ruleMatchesProduct",
}

RULE_KEYWORDS = [
    "potentially",
    "rule",
    "reasoning",
    "inferred",
    "matches",
    "fit",
    "coverage",
]

# 关系类型中文展示名：仅用于前端展示，不改变 Neo4j 底层英文关系类型。
RELATION_CN = {
    "issues": "发布/印发政策",
    "supports": "支持产品",
    "providesProduct": "提供产品",
    "servesEnterprise": "服务企业",
    "locatedIn": "位于地区",
    "hasFeature": "具有企业特征",
    "belongsToIndustry": "所属行业",
    "targetsEnterprise": "面向企业",
    "connects": "连接服务平台",
    "issuesLoan": "发放贷款",
    "loanToEnterprise": "贷款流向企业",
    "grantsSubsidy": "发放补贴",
    "benefitsEnterprise": "补贴惠及企业",
    "matchesFinancing": "融资匹配",
    "potentiallyMatchesPolicy": "潜在匹配政策（规则推理）",
    "potentiallyMatchesProduct": "潜在匹配产品（规则推理）",
    "policyCoversRegion": "政策覆盖地区（规则推理）",
    "policyCoversIndustry": "政策覆盖行业（规则推理）",
    "productFitsEnterpriseFeature": "产品适配企业特征（规则推理）",
    "fitsEnterpriseFeature": "适配企业特征（规则推理）",
    "ruleMatchesPolicy": "规则匹配政策",
    "ruleMatchesProduct": "规则匹配产品",
}

def relation_cn(rel_type: str) -> str:
    """关系类型转中文展示名；未知关系保留英文，避免误翻译。"""
    if not rel_type:
        return "未知关系"
    return RELATION_CN.get(str(rel_type), str(rel_type))

def get_env_config() -> Dict[str, str]:
    return {
        "uri": os.getenv("GTF_NEO4J_URI", "bolt://127.0.0.1:7688"),
        "user": os.getenv("GTF_NEO4J_USER", "neo4j"),
        "password": os.getenv("GTF_NEO4J_PASSWORD", ""),
        "database": os.getenv("GTF_NEO4J_DATABASE", "neo4j"),
    }


def short_label(label: str) -> str:
    if not label:
        return "Unknown"
    return label.split(".")[-1] if "." in label else label


def get_node_type(node) -> str:
    labels = list(node.labels)
    for label in labels:
        s = short_label(label)
        if s in NODE_STYLE:
            return s
    return short_label(labels[0]) if labels else "Unknown"


def get_node_name(props: Dict[str, Any]) -> str:
    for key in ["name", "title", "id", "code", "event_name"]:
        val = props.get(key)
        if val is not None and str(val).strip():
            return str(val)
    return "未命名节点"


def normalize_props(props: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    for k, v in props.items():
        if isinstance(v, (str, int, float, bool)) or v is None:
            out[k] = v
        else:
            out[k] = str(v)
    return out


def get_credit_level(props: Dict[str, Any]) -> str:
    for key in ["creditLevel", "credit_level", "evidenceLevel", "evidence_level", "confidenceLevel"]:
        val = props.get(key)
        if val is not None and str(val).strip():
            level = str(val).strip().upper()
            if level in {"A", "B", "C"}:
                return level
    return "NONE"


def is_rule_edge(rel_type: str, props: Dict[str, Any]) -> bool:
    if rel_type in RULE_REL_TYPES:
        return True

    lower_type = rel_type.lower()
    if any(k.lower() in lower_type for k in RULE_KEYWORDS):
        return True

    pool = " ".join([
        str(props.get("source_scope", "")),
        str(props.get("sourceScope", "")),
        str(props.get("relationLayer", "")),
        str(props.get("layer", "")),
        str(props.get("kind", "")),
        str(props.get("source", "")),
        str(props.get("notes", "")),
    ]).lower()

    return any(k.lower() in pool for k in RULE_KEYWORDS)


def make_label(namespace: str, entity_type: str) -> str:
    return f"`{namespace}.{entity_type}`"



# ============================================================
# V7 多跳链路族展示场景：T01-T10
# 只用于前端局部图谱展示，不改变后端 V8 / V7 问答逻辑。
# ============================================================

MULTIHOP_CHAIN_SCENES = {
    "多跳链路｜T01 政策→产品→企业→企业特征": """
        MATCH p=(s:`{ns}.Policy`)-[:supports]->(:`{ns}.FinancialProduct`)-[:servesEnterprise]->(:`{ns}.Enterprise`)-[:hasFeature]->(:`{ns}.QualificationCreditFeature`)
        RETURN p
        LIMIT $limit
    """,
    "多跳链路｜T02 政策→产品→企业→行业": """
        MATCH p=(s:`{ns}.Policy`)-[:supports]->(:`{ns}.FinancialProduct`)-[:servesEnterprise]->(:`{ns}.Enterprise`)-[:belongsToIndustry]->(:`{ns}.IndustrySegment`)
        RETURN p
        LIMIT $limit
    """,
    "多跳链路｜T03 政策→产品→企业→地区": """
        MATCH p=(s:`{ns}.Policy`)-[:supports]->(:`{ns}.FinancialProduct`)-[:servesEnterprise]->(:`{ns}.Enterprise`)-[:locatedIn]->(:`{ns}.Region`)
        RETURN p
        LIMIT $limit
    """,
    "多跳链路｜T04 机构→产品→企业→企业特征": """
        MATCH p=(s:`{ns}.FinancialInstitution`)-[:providesProduct]->(:`{ns}.FinancialProduct`)-[:servesEnterprise]->(:`{ns}.Enterprise`)-[:hasFeature]->(:`{ns}.QualificationCreditFeature`)
        RETURN p
        LIMIT $limit
    """,
    "多跳链路｜T05 机构→产品→企业→行业": """
        MATCH p=(s:`{ns}.FinancialInstitution`)-[:providesProduct]->(:`{ns}.FinancialProduct`)-[:servesEnterprise]->(:`{ns}.Enterprise`)-[:belongsToIndustry]->(:`{ns}.IndustrySegment`)
        RETURN p
        LIMIT $limit
    """,
    "多跳链路｜T06 政策→产品→企业→特征→地区": """
        MATCH p=(s:`{ns}.Policy`)-[:supports]->(:`{ns}.FinancialProduct`)-[:servesEnterprise]->(e:`{ns}.Enterprise`)-[:hasFeature]->(:`{ns}.QualificationCreditFeature`)
        MATCH p2=(e)-[:locatedIn]->(:`{ns}.Region`)
        RETURN p, p2
        LIMIT $limit
    """,
    "多跳链路｜T07 机构→产品→企业→特征→地区": """
        MATCH p=(s:`{ns}.FinancialInstitution`)-[:providesProduct]->(:`{ns}.FinancialProduct`)-[:servesEnterprise]->(e:`{ns}.Enterprise`)-[:hasFeature]->(:`{ns}.QualificationCreditFeature`)
        MATCH p2=(e)-[:locatedIn]->(:`{ns}.Region`)
        RETURN p, p2
        LIMIT $limit
    """,
    "多跳链路｜T08 政策→产品→企业→行业→地区": """
        MATCH p=(s:`{ns}.Policy`)-[:supports]->(:`{ns}.FinancialProduct`)-[:servesEnterprise]->(e:`{ns}.Enterprise`)-[:belongsToIndustry]->(:`{ns}.IndustrySegment`)
        MATCH p2=(e)-[:locatedIn]->(:`{ns}.Region`)
        RETURN p, p2
        LIMIT $limit
    """,
    "多跳链路｜T09 机构→产品→企业→行业→地区": """
        MATCH p=(s:`{ns}.FinancialInstitution`)-[:providesProduct]->(:`{ns}.FinancialProduct`)-[:servesEnterprise]->(e:`{ns}.Enterprise`)-[:belongsToIndustry]->(:`{ns}.IndustrySegment`)
        MATCH p2=(e)-[:locatedIn]->(:`{ns}.Region`)
        RETURN p, p2
        LIMIT $limit
    """,
    "多跳链路｜T10 政策→产品→企业→行业→地区概览": """
        MATCH p=(s:`{ns}.Policy`)-[:supports]->(:`{ns}.FinancialProduct`)-[:servesEnterprise]->(e:`{ns}.Enterprise`)-[:belongsToIndustry]->(:`{ns}.IndustrySegment`)
        MATCH p2=(e)-[:locatedIn]->(:`{ns}.Region`)
        RETURN p, p2
        LIMIT $limit
    """,
}


GENERIC_RELATION_SCENES = {
    "泛关系邻域｜企业多类型邻域": """
        MATCH p=(e:`{ns}.Enterprise`)-[r]-(o)
        WHERE type(r) IN [
            "locatedIn", "belongsToIndustry", "hasFeature",
            "potentiallyMatchesProduct", "potentiallyMatchesPolicy",
            "servesEnterprise", "loanToEnterprise", "benefitsEnterprise"
        ]
        RETURN p
        LIMIT $limit
    """,
    "泛关系邻域｜产品多类型邻域": """
        MATCH p=(fp:`{ns}.FinancialProduct`)-[r]-(o)
        WHERE type(r) IN [
            "providesProduct", "supports", "servesEnterprise",
            "fitsEnterpriseFeature", "productFitsEnterpriseFeature",
            "hasCoverageRegion", "hasCoverageIndustry"
        ]
        RETURN p
        LIMIT $limit
    """,
    "泛关系邻域｜机构宽邻域": """
        MATCH p=(fi:`{ns}.FinancialInstitution`)-[r]-(o)
        WHERE type(r) IN [
            "providesProduct", "issuesLoan", "connects",
            "supports", "servesEnterprise"
        ]
        RETURN p
        LIMIT $limit
    """,
    "泛关系邻域｜政策多类型邻域": """
        MATCH p=(po:`{ns}.Policy`)-[r]-(o)
        WHERE type(r) IN [
            "issues", "supports", "targetsEnterprise",
            "hasCoverageRegion", "hasCoverageIndustry",
            "policyCoversRegion", "policyCoversIndustry"
        ]
        RETURN p
        LIMIT $limit
    """,
}


def build_query(namespace: str, view_name: str, limit: int, subject: str, relation_type: str = None) -> Tuple[str, Dict[str, Any]]:
    label = lambda t: make_label(namespace, t)
    params = {"limit": int(limit), "subject": subject.strip()}

    # V7 多跳链路族：T01-T10，用于局部图谱展示
    if view_name in MULTIHOP_CHAIN_SCENES:
        return MULTIHOP_CHAIN_SCENES[view_name].format(ns=namespace), params

    # 泛关系邻域：展示一个主体类型可跨多类实体连接到的对象，用于对应 open_generic_relation 能力。
    if view_name in GENERIC_RELATION_SCENES:
        return GENERIC_RELATION_SCENES[view_name].format(ns=namespace), params

    # 按某一类关系直接展示局部链路。
    # 注意：关系类型仍使用 Neo4j 底层英文名，页面展示时再翻译成中文。
    if relation_type:
        safe_rel = str(relation_type).replace("`", "")
        return f"""
        MATCH p=(a)-[r:`{safe_rel}`]->(b)
        RETURN p
        LIMIT $limit
        """, params

    if view_name == "机构—产品—企业链路":
        return f"""
        MATCH p=(fi:{label("FinancialInstitution")})-[r1:providesProduct]->(fp:{label("FinancialProduct")})-[r2:servesEnterprise]->(e:{label("Enterprise")})
        RETURN p
        LIMIT $limit
        """, params

    if view_name == "政策—产品—企业链路":
        return f"""
        MATCH p=(po:{label("Policy")})-[r1:supports]->(fp:{label("FinancialProduct")})-[r2:servesEnterprise]->(e:{label("Enterprise")})
        RETURN p
        LIMIT $limit
        """, params

    if view_name == "企业—地区/行业/特征链路":
        return f"""
        MATCH p=(e:{label("Enterprise")})-[r]->(x)
        WHERE type(r) IN ["locatedIn", "belongsToIndustry", "hasFeature"]
        RETURN p
        LIMIT $limit
        """, params

    if view_name == "规则推理链路":
        return """
        MATCH p=(a)-[r]->(b)
        WHERE
            type(r) CONTAINS "potentially"
            OR type(r) CONTAINS "Matches"
            OR coalesce(r.relationLayer, "") CONTAINS "rule"
            OR coalesce(r.source_scope, "") CONTAINS "rule"
            OR coalesce(r.kind, "") CONTAINS "rule"
        RETURN p
        LIMIT $limit
        """, params

    if view_name == "非结构化贷款事件链路":
        return f"""
        MATCH p=(fi:{label("FinancialInstitution")})-[r1:issuesLoan]->(le:{label("LoanEvent")})-[r2:loanToEnterprise]->(e:{label("Enterprise")})
        RETURN p
        LIMIT $limit
        """, params

    if view_name == "信用等级 A/B/C 关系":
        return """
        MATCH p=(a)-[r]->(b)
        WHERE r.creditLevel IS NOT NULL
           OR r.credit_level IS NOT NULL
           OR r.evidenceLevel IS NOT NULL
           OR r.evidence_level IS NOT NULL
        RETURN p
        LIMIT $limit
        """, params

    if view_name == "按主体查询局部图谱":
        return """
        MATCH p=(a)-[r]-(b)
        WHERE
            coalesce(a.name, "") CONTAINS $subject
            OR coalesce(b.name, "") CONTAINS $subject
            OR $subject CONTAINS coalesce(a.name, "")
            OR $subject CONTAINS coalesce(b.name, "")
        RETURN p
        LIMIT $limit
        """, params

    return "MATCH p=(a)-[r]->(b) RETURN p LIMIT $limit", params


@st.cache_data(show_spinner=False, ttl=20)
def fetch_graph(uri: str, user: str, password: str, database: str, cypher: str, params_json: str):
    params = json.loads(params_json)
    driver = GraphDatabase.driver(uri, auth=(user, password))

    nodes = {}
    edges = {}

    with driver.session(database=database) as session:
        result = session.run(cypher, params)
        for record in result:
            for value in record.values():
                if not (hasattr(value, "nodes") and hasattr(value, "relationships")):
                    continue

                for n in value.nodes:
                    node_id = str(n.element_id)
                    props = normalize_props(dict(n))
                    ntype = get_node_type(n)
                    name = get_node_name(props)
                    style = NODE_STYLE.get(ntype, NODE_STYLE["Unknown"])

                    nodes[node_id] = {
                        "id": node_id,
                        "label": name[:26] + ("..." if len(name) > 26 else ""),
                        "full_name": name,
                        "type": ntype,
                        "labels": [short_label(x) for x in list(n.labels)],
                        "properties": props,
                        "color": style["color"],
                        "shape": "diamond" if ntype in {"LoanEvent", "SubsidyEvent"} else "dot",
                        "size": 24 if ntype in {"Policy", "Enterprise", "FinancialProduct"} else 18,
                        "title": f"{html.escape(ntype)}<br>{html.escape(name)}",
                    }

                for r in value.relationships:
                    rel_id = str(r.element_id)
                    props = normalize_props(dict(r))
                    rel_type = str(r.type)
                    credit = get_credit_level(props)
                    rule_edge = is_rule_edge(rel_type, props)
                    cstyle = CREDIT_STYLE.get(credit, CREDIT_STYLE["NONE"])

                    edge_color = cstyle["color"]
                    if rule_edge and credit == "NONE":
                        edge_color = "#6F42C1"

                    rel_cn = relation_cn(rel_type)

                    edges[rel_id] = {
                        "id": rel_id,
                        "from": str(r.start_node.element_id),
                        "to": str(r.end_node.element_id),
                        "label": rel_cn,
                        "label_cn": rel_cn,
                        "label_en": rel_type,
                        "type": rel_type,
                        "creditLevel": credit,
                        "isRuleEdge": rule_edge,
                        "properties": props,
                        "arrows": "to",
                        "color": {"color": edge_color, "highlight": "#000000"},
                        "width": cstyle["width"] + (1 if rule_edge else 0),
                        "dashes": [10, 7] if rule_edge else False,
                        "smooth": {"type": "dynamic"},
                        "title": f"{html.escape(rel_type)}<br>creditLevel={credit}<br>rule={rule_edge}",
                    }

    driver.close()
    return list(nodes.values()), list(edges.values())



@st.cache_data(show_spinner=False, ttl=60)
def fetch_relationship_types(uri: str, user: str, password: str, database: str) -> List[str]:
    """从 Neo4j 动态读取当前图谱中所有关系类型。"""
    driver = GraphDatabase.driver(uri, auth=(user, password))
    rels = []
    try:
        with driver.session(database=database) as session:
            try:
                result = session.run(
                    "CALL db.relationshipTypes() YIELD relationshipType "
                    "RETURN relationshipType ORDER BY relationshipType"
                )
                rels = [str(r["relationshipType"]) for r in result if r.get("relationshipType")]
            except Exception:
                result = session.run(
                    "MATCH ()-[r]->() "
                    "RETURN DISTINCT type(r) AS relationshipType "
                    "ORDER BY relationshipType"
                )
                rels = [str(r["relationshipType"]) for r in result if r.get("relationshipType")]
    finally:
        driver.close()

    return rels

def legend_html() -> str:
    node_rows = []
    for key, val in NODE_STYLE.items():
        if key == "Unknown":
            continue
        node_rows.append(
            f'<div class="legend-row"><span class="node-dot" style="background:{val["color"]}"></span>{html.escape(val["label"])}</div>'
        )

    edge_rows = []
    for key in ["A", "B", "C", "NONE"]:
        val = CREDIT_STYLE[key]
        edge_rows.append(
            f'<div class="legend-row"><span class="edge-line" style="background:{val["color"]};height:{val["width"]}px"></span>{html.escape(val["label"])}</div>'
        )

    return f"""
    <div class="legend-box">
      <h4>图例说明</h4>
      <b>节点颜色</b>
      {''.join(node_rows)}
      <hr>
      <b>边颜色 / 粗细</b>
      {''.join(edge_rows)}
      <div class="legend-row"><span class="dash-line"></span>虚线：规则推理边 / 推断边</div>
    </div>
    """


def build_graph_html(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> str:
    nodes_json = json.dumps(nodes, ensure_ascii=False)
    edges_json = json.dumps(edges, ensure_ascii=False)
    lgd = legend_html()

    return f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<script src="https://unpkg.com/vis-network@9.1.9/dist/vis-network.min.js"></script>
<style>
body {{
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", Arial, sans-serif;
}}
.layout {{
  display: grid;
  grid-template-columns: 1fr 360px;
  gap: 12px;
  height: 760px;
}}
#network {{
  height: 760px;
  border: 1px solid #E9ECEF;
  border-radius: 16px;
  background: #FAFAFA;
}}
.side {{
  height: 760px;
  overflow: auto;
  border: 1px solid #E9ECEF;
  border-radius: 16px;
  padding: 14px;
  background: #FFF;
  box-sizing: border-box;
}}
.legend-box {{
  padding: 12px;
  border-radius: 12px;
  background: #F8F9FA;
  border: 1px solid #E9ECEF;
  margin-bottom: 14px;
}}
.legend-row {{
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 7px 0;
  font-size: 13px;
}}
.node-dot {{
  width: 13px;
  height: 13px;
  border-radius: 50%;
  display: inline-block;
}}
.edge-line {{
  width: 36px;
  display: inline-block;
  border-radius: 3px;
}}
.dash-line {{
  width: 36px;
  border-top: 3px dashed #6F42C1;
  display: inline-block;
}}
.detail-box {{
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 13px;
  line-height: 1.45;
}}
.detail-title {{
  font-weight: 700;
  font-size: 16px;
  margin: 8px 0;
}}
.pill {{
  display: inline-block;
  padding: 2px 8px;
  margin: 2px 4px 2px 0;
  border-radius: 999px;
  background: #EDF2FF;
  color: #364FC7;
  font-size: 12px;
}}
code {{
  background: #F1F3F5;
  padding: 2px 5px;
  border-radius: 5px;
}}
</style>
</head>
<body>
<div class="layout">
  <div id="network"></div>
  <div class="side">
    {lgd}
    <div class="detail-title">属性面板</div>
    <div id="detail" class="detail-box">点击左侧节点或边，可查看详细属性。</div>
  </div>
</div>

<script>
const nodes = new vis.DataSet({nodes_json});
const edges = new vis.DataSet({edges_json});
const container = document.getElementById("network");
const data = {{nodes, edges}};

const options = {{
  interaction: {{
    hover: true,
    navigationButtons: true,
    keyboard: true,
    tooltipDelay: 180
  }},
  physics: {{
    enabled: true,
    stabilization: {{enabled: true, iterations: 180}},
    barnesHut: {{
      gravitationalConstant: -36000,
      centralGravity: 0.25,
      springLength: 170,
      springConstant: 0.035,
      damping: 0.18,
      avoidOverlap: 0.35
    }}
  }},
  nodes: {{
    borderWidth: 2,
    shadow: true,
    font: {{size: 13, face: "Microsoft YaHei"}}
  }},
  edges: {{
    font: {{size: 11, align: "middle", face: "Microsoft YaHei"}},
    arrows: {{to: {{enabled: true, scaleFactor: 0.65}}}}
  }}
}};

const network = new vis.Network(container, data, options);

function esc(str) {{
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}}

function renderProps(obj) {{
  if (!obj || Object.keys(obj).length === 0) return "无属性";
  return esc(Object.entries(obj).map(([k,v]) => `${{k}}: ${{v}}`).join("\\n"));
}}

function showNode(id) {{
  const n = nodes.get(id);
  const labels = (n.labels || []).map(x => `<span class="pill">${{esc(x)}}</span>`).join("");
  document.getElementById("detail").innerHTML = `
    <div class="detail-title">节点详情</div>
    <div><b>名称：</b>${{esc(n.full_name || n.label)}}</div>
    <div><b>类型：</b><code>${{esc(n.type || "")}}</code></div>
    <div><b>标签：</b>${{labels}}</div>
    <hr>
    <div><b>属性：</b></div>
    <pre>${{renderProps(n.properties)}}</pre>
  `;
}}

function showEdge(id) {{
  const e = edges.get(id);
  const fromNode = nodes.get(e.from);
  const toNode = nodes.get(e.to);
  document.getElementById("detail").innerHTML = `
    <div class="detail-title">关系详情</div>
    <div><b>关系类型：</b><code>${{esc(e.type || e.label || "")}}</code></div>
    <div><b>起点：</b>${{esc(fromNode ? fromNode.full_name : e.from)}}</div>
    <div><b>终点：</b>${{esc(toNode ? toNode.full_name : e.to)}}</div>
    <div><b>creditLevel：</b><code>${{esc(e.creditLevel || "NONE")}}</code></div>
    <div><b>是否规则推理边：</b><code>${{e.isRuleEdge ? "是，虚线显示" : "否"}}</code></div>
    <hr>
    <div><b>关系属性：</b></div>
    <pre>${{renderProps(e.properties)}}</pre>
  `;
}}

network.on("click", function(params) {{
  if (params.nodes && params.nodes.length > 0) showNode(params.nodes[0]);
  else if (params.edges && params.edges.length > 0) showEdge(params.edges[0]);
}});

network.once("stabilizationIterationsDone", function() {{
  network.setOptions({{physics: false}});
}});
</script>
</body>
</html>
"""



# ============================================================
# 自由问答辅助：图谱页内调用 V8 / V7
# ============================================================

try:
    ROOT
except NameError:
    ROOT = Path(__file__).resolve().parents[3]

V8_SCRIPT = ROOT / "app/retrieval_only/scripts/answer_hybrid_v8_graph_kag_fallback.py"
V7_SCRIPT = ROOT / "app/retrieval_only/scripts/answer_hybrid_v7_kag_reasoner.py"


def kg_extract_section(raw: str, name: str) -> str:
    m = re.search(rf"===== {re.escape(name)} =====\n(.*?)(?=\n===== |\Z)", raw or "", flags=re.S)
    return m.group(1).strip() if m else ""


def kg_parse_answer_meta(raw: str) -> dict:
    meta = {}
    for key in [
        "query",
        "question_type",
        "subject",
        "constraint_institution",
        "route",
        "final_route",
        "answer_source",
        "intent_source",
        "kag_used",
        "graph_answers",
        "kag_answers",
    ]:
        m = re.search(rf"^{key}\s*=\s*(.*)$", raw or "", flags=re.M)
        if m:
            meta[key] = m.group(1).strip()

    meta["answer"] = kg_extract_section(raw, "ANSWER")
    meta["cypher"] = kg_extract_section(raw, "CYPHER")
    meta["actual_cypher"] = kg_extract_section(raw, "ACTUAL CYPHER")
    meta["graph_trace_cypher"] = kg_extract_section(raw, "GRAPH TRACE CYPHER")
    meta["kag_evidence"] = (
        kg_extract_section(raw, "KAG EVIDENCE")
        or kg_extract_section(raw, "KAG EVIDENCE ANSWER")
        or meta.get("kag_answers", "")
    )
    return meta


def kg_run_freeqa(question: str, engine: str = "V8", timeout: int = 180) -> tuple[str, dict]:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("GTF_NEO4J_URI", "bolt://127.0.0.1:7688")
    env.setdefault("GTF_NEO4J_USER", "neo4j")
    env.setdefault("GTF_NEO4J_PASSWORD", os.getenv("GTF_NEO4J_PASSWORD", ""))
    env.setdefault("GTF_NEO4J_DATABASE", "neo4j")
    env.setdefault("GTF_LEVEL2_SUBJECT_SOURCE", "graph")
    env.setdefault("GTF_ENABLE_KAG_FALLBACK", "1")
    env.setdefault("GTF_ENABLE_V7_FALLBACK", "1")
    env.setdefault("GTF_ENABLE_V8_KAG_MULTIHOP_PLANNER", "1")

    if engine == "V7 多跳链路族":
        script = V7_SCRIPT
        env.setdefault("SHOW_ACTUAL_CYPHER", "1")
    else:
        script = V8_SCRIPT

    proc = subprocess.run(
        ["python", str(script), question],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=env,
    )

    raw = proc.stdout or ""
    return raw, kg_parse_answer_meta(raw)


st.title("🕸️ 知识图谱可视化")
st.caption("局部展示知识图谱：关系边显示中文名；节点颜色区分实体类型；虚线表示规则推理边；边颜色/粗细表示 creditLevel A/B/C；展示场景支持按全部关系类型与 V7 多跳链路族筛选；页面内支持自然语言问答定位。")

cfg = get_env_config()


with st.expander("自然语言问答 / 链路定位窗口", expanded=False):
    st.caption("在图谱可视化页内直接输入自然语言问题。默认调用 V8；多跳链路调试时可切换为 V7 多跳链路族。")

    qa_engine = st.radio(
        "调用脚本",
        ["V8 主问答", "V7 多跳链路族"],
        horizontal=True,
        key="kg_graph_qa_engine",
    )

    qa_question = st.text_area(
        "请输入自然语言问题",
        value="从“机构→产品→企业→特征→地区”的组合链看，中国邮政储蓄银行甘肃省分行在兰州市主要服务了哪些专精特新中小企业？",
        height=95,
        key="kg_graph_qa_question",
    )

    qa_timeout = st.slider(
        "问答超时时间/秒",
        min_value=60,
        max_value=300,
        value=180,
        step=30,
        key="kg_graph_qa_timeout",
    )

    if st.button("查询问答结果", type="primary", key="kg_graph_qa_btn"):
        if not qa_question.strip():
            st.warning("请输入问题。")
        else:
            try:
                with st.spinner("正在调用问答脚本..."):
                    raw, meta = kg_run_freeqa(
                        qa_question.strip(),
                        engine=qa_engine,
                        timeout=int(qa_timeout),
                    )

                if meta.get("answer"):
                    st.success(meta["answer"])
                else:
                    st.warning("未解析到 ANSWER 段，请查看原始输出。")

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("question_type", meta.get("question_type", ""))
                c2.metric("subject", meta.get("subject", ""))
                c3.metric("route", meta.get("route", ""))
                c4.metric("answer_source", meta.get("answer_source", ""))

                with st.expander("查看 Cypher / Graph Trace", expanded=False):
                    cypher_to_show = (
                        meta.get("graph_trace_cypher")
                        or meta.get("actual_cypher")
                        or meta.get("cypher")
                        or ""
                    )
                    st.code(cypher_to_show or "无 Cypher", language="cypher")

                with st.expander("查看 graph_answers / kag_answers", expanded=False):
                    st.markdown("**graph_answers**")
                    st.code(meta.get("graph_answers", "") or "无", language="text")
                    st.markdown("**kag_answers**")
                    if meta.get("kag_answers") or meta.get("kag_evidence"):
                        st.code(meta.get("kag_answers") or meta.get("kag_evidence"), language="text")
                    else:
                        st.code("无 KAG Evidence", language="text")

                with st.expander("查看原始输出", expanded=False):
                    st.code(raw, language="text")

            except subprocess.TimeoutExpired:
                st.error("问答脚本调用超时，请调大超时时间。")
            except Exception as e:
                st.error("问答脚本调用失败，请检查环境变量、Neo4j 服务和 V7/V8 脚本。")
                st.exception(e)


with st.sidebar:
    st.header("图谱展示配置")

    namespace = st.text_input("Schema 命名空间", value=DEFAULT_NAMESPACE)

    base_views = [
        "机构—产品—企业链路",
        "政策—产品—企业链路",
        "企业—地区/行业/特征链路",
        "规则推理链路",
        "泛关系邻域｜企业多类型邻域",
        "泛关系邻域｜产品多类型邻域",
        "泛关系邻域｜机构宽邻域",
        "泛关系邻域｜政策多类型邻域",
        "非结构化贷款事件链路",
        "信用等级 A/B/C 关系",
        "按主体查询局部图谱",
    ]

    try:
        relation_types = fetch_relationship_types(
            cfg["uri"],
            cfg["user"],
            cfg["password"],
            cfg["database"],
        )
    except Exception:
        relation_types = sorted(RELATION_CN.keys())
        st.warning("未能动态读取 Neo4j 关系类型，已使用内置关系类型列表。")

    relation_display_to_type = {
        f"单关系链路｜{relation_cn(rt)}（{rt}）": rt
        for rt in relation_types
    }

    view_name = st.selectbox(
        "选择展示场景",
        base_views + list(MULTIHOP_CHAIN_SCENES.keys()) + list(relation_display_to_type.keys()),
        index=0,
    )

    selected_relation_type = relation_display_to_type.get(view_name)

    subject = ""
    if view_name == "按主体查询局部图谱":
        subject = st.text_input("输入主体名称", value="甘肃银行")

    limit = st.slider("最大路径数量", min_value=10, max_value=300, value=80, step=10)

    st.divider()
    st.subheader("Neo4j 连接")
    st.code(
        f"GTF_NEO4J_URI={cfg['uri']}\n"
        f"GTF_NEO4J_USER={cfg['user']}\n"
        f"GTF_NEO4J_DATABASE={cfg['database']}\n"
        f"GTF_NEO4J_PASSWORD={'已设置' if cfg['password'] else '未设置'}",
        language="bash",
    )

cypher, params = build_query(namespace, view_name, limit, subject, selected_relation_type)
params_json = json.dumps(params, ensure_ascii=False)

with st.expander("查看当前 Cypher 查询", expanded=False):
    st.code(cypher.strip(), language="cypher")
    st.json(params)

try:
    with st.spinner("正在从 Neo4j 读取图谱数据..."):
        nodes, edges = fetch_graph(
            cfg["uri"],
            cfg["user"],
            cfg["password"],
            cfg["database"],
            cypher,
            params_json,
        )

    c1, c2, c3 = st.columns(3)
    c1.metric("节点数", len(nodes))
    c2.metric("关系数", len(edges))
    c3.metric("展示场景", view_name)

    if not nodes or not edges:
        st.warning("当前查询没有返回图谱数据。可以换一个展示场景，或调大路径数量。")
    else:
        st.components.v1.html(build_graph_html(nodes, edges), height=790, scrolling=False)

except Exception as e:
    st.error("图谱读取失败，请检查 Neo4j 环境变量、端口和密码。")
    st.exception(e)
    st.info(
        "建议先执行：\n\n"
        "```bash\n"
        "cd <交付包解压目录>/paper_submission_system_20260522_114215\n"
        "source scripts/加载运行环境变量.sh\n"
        "python app/retrieval_only/scripts/answer_hybrid_v8_graph_kag_fallback.py \"甘肃银行提供什么科技金融产品？\"\n"
        "```"
    )

