from __future__ import annotations

import os
import tempfile
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from neo4j import GraphDatabase
from pyvis.network import Network


st.set_page_config(
    page_title="规则推理展示 - 甘肃科技金融知识图谱",
    page_icon="🧩",
    layout="wide",
)

st.title("规则推理展示")
st.caption("展示基于区域、产业、资质特征等关系生成的规则推理边。")

st.info(
    "本页面用于展示规则推理增强结果。"
    "系统不仅支持已有结构化事实查询，还可以通过规则边发现企业潜在政策、潜在产品、政策覆盖产业、政策覆盖区域和产品适配特征。"
)


DEFAULT_URI = os.getenv("GTF_NEO4J_URI", "bolt://127.0.0.1:7688")
DEFAULT_USER = os.getenv("GTF_NEO4J_USER", "neo4j")
DEFAULT_PASSWORD = os.getenv("GTF_NEO4J_PASSWORD", "")
DEFAULT_DATABASE = os.getenv("GTF_NEO4J_DATABASE", "neo4j")


RULE_TYPES = {
    "企业潜在政策推荐": {
        "rel": "potentiallyMatchesPolicy",
        "desc": "根据企业区域、产业、资质特征等信息，推理企业可能适配的政策。",
        "source": "企业",
        "target": "政策",
        "example": "关键词可输入企业名称，也可以留空展示部分推理边。",
    },
    "企业潜在产品推荐": {
        "rel": "potentiallyMatchesProduct",
        "desc": "根据企业特征与金融产品服务对象，推理企业可能适配的科技金融产品。",
        "source": "企业",
        "target": "金融产品",
        "example": "关键词可输入企业名称或产品名称。",
    },
    "政策覆盖产业识别": {
        "rel": "hasCoverageIndustry",
        "desc": "根据政策内容和目标对象，推理政策覆盖的产业方向。",
        "source": "政策",
        "target": "产业",
        "example": "关键词可输入政策名称或产业名称，例如“生物医药”。",
    },
    "政策覆盖区域识别": {
        "rel": "hasCoverageRegion",
        "desc": "根据政策适用范围，推理政策覆盖的区域。",
        "source": "政策",
        "target": "区域",
        "example": "关键词可输入政策名称或区域名称，例如“兰州”。",
    },
    "产品适配企业特征": {
        "rel": "fitsEnterpriseFeature",
        "desc": "根据产品服务对象和准入条件，推理金融产品适配的企业资质或信用特征。",
        "source": "金融产品",
        "target": "企业特征",
        "example": "关键词可输入产品名称或特征名称，例如“科技型中小企业”。",
    },
    "产品服务重点产业": {
        "rel": "hasServiceFocusIndustry",
        "desc": "根据产品定位和服务方向，推理金融产品或平台重点服务的产业方向。",
        "source": "产品/平台",
        "target": "产业",
        "example": "关键词可输入产品名称或产业名称。",
    },
}


with st.sidebar:
    st.header("Neo4j 连接")

    uri = st.text_input("Bolt URI", value=DEFAULT_URI)
    user = st.text_input("用户名", value=DEFAULT_USER)
    password = st.text_input("密码", value=DEFAULT_PASSWORD, type="password")
    database = st.text_input("数据库", value=DEFAULT_DATABASE)

    st.divider()

    rule_name = st.selectbox("选择规则推理类型", list(RULE_TYPES.keys()))
    keyword = st.text_input("关键词", value="")
    limit = st.slider("最多展示关系数", 10, 300, 50, step=10)


def label_short(label: str) -> str:
    if not label:
        return ""
    return str(label).split(".")[-1]


def run_query(cypher: str, params: dict):
    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        with driver.session(database=database) as session:
            return list(session.run(cypher, params))
    finally:
        driver.close()


def rule_query(rel_type: str) -> str:
    return f"""
    MATCH (a)-[r:{rel_type}]->(b)
    WHERE $keyword = ''
       OR coalesce(a.name, '') CONTAINS $keyword
       OR coalesce(b.name, '') CONTAINS $keyword
    RETURN
       coalesce(a.name, elementId(a)) AS source,
       labels(a)[0] AS source_label,
       type(r) AS relation,
       coalesce(b.name, elementId(b)) AS target,
       labels(b)[0] AS target_label,
       properties(r) AS rel_props
    ORDER BY source, target
    LIMIT $limit
    """


def render_graph(rows):
    net = Network(
        height="680px",
        width="100%",
        directed=True,
        notebook=False,
        cdn_resources="in_line",
    )

    net.barnes_hut(
        gravity=-5000,
        central_gravity=0.35,
        spring_length=180,
        spring_strength=0.04,
        damping=0.09,
    )

    added = set()

    for row in rows:
        source = row["source"] or "未知起点"
        target = row["target"] or "未知终点"
        relation = row["relation"] or "REL"
        source_label = label_short(row["source_label"])
        target_label = label_short(row["target_label"])

        if source not in added:
            net.add_node(source, label=source, title=f"{source_label}: {source}")
            added.add(source)

        if target not in added:
            net.add_node(target, label=target, title=f"{target_label}: {target}")
            added.add(target)

        net.add_edge(source, target, label=relation, title=relation, arrows="to")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp:
        html = net.generate_html()
        Path(tmp.name).write_text(html, encoding="utf-8")
        html = Path(tmp.name).read_text(encoding="utf-8")

    components.html(html, height=700, scrolling=True)


def get_rule_stats():
    rel_names = [v["rel"] for v in RULE_TYPES.values()]
    cypher = """
    MATCH ()-[r]->()
    WHERE type(r) IN $rel_names
    RETURN type(r) AS rel_type, count(r) AS cnt
    ORDER BY cnt DESC
    """
    return run_query(cypher, {"rel_names": rel_names})


def get_sample_subjects(rel_type: str):
    cypher = f"""
    MATCH (a)-[r:{rel_type}]->(b)
    RETURN
      coalesce(a.name, elementId(a)) AS source,
      labels(a)[0] AS source_label,
      count(b) AS target_count
    ORDER BY target_count DESC
    LIMIT 20
    """
    return run_query(cypher, {})


tab1, tab2, tab3 = st.tabs(["规则推理查询", "规则统计", "规则说明"])

with tab1:
    info = RULE_TYPES[rule_name]
    rel_type = info["rel"]

    st.subheader(rule_name)
    st.markdown(f"**关系类型：** `{rel_type}`")
    st.markdown(f"**推理含义：** {info['desc']}")
    st.markdown(f"**起点对象：** {info['source']}　→　**终点对象：** {info['target']}")
    st.caption(info["example"])

    cypher = rule_query(rel_type)

    with st.expander("查看 Cypher", expanded=False):
        st.code(cypher, language="cypher")

    if st.button("查询规则推理结果", type="primary"):
        try:
            rows = run_query(cypher, {"keyword": keyword.strip(), "limit": int(limit)})
        except Exception as e:
            st.error(f"Neo4j 查询失败：{e}")
            st.stop()

        st.write(f"返回规则边数量：**{len(rows)}**")

        if not rows:
            st.warning("没有查询到结果。可以换关键词，或将关键词留空后降低/提高展示数量。")
            st.stop()

        table = []
        for row in rows:
            props = row["rel_props"] or {}
            table.append(
                {
                    "起点": row["source"],
                    "起点类型": label_short(row["source_label"]),
                    "规则关系": row["relation"],
                    "终点": row["target"],
                    "终点类型": label_short(row["target_label"]),
                    "规则属性": str(props) if props else "",
                }
            )

        st.markdown("### 表格结果")
        st.dataframe(table, use_container_width=True)

        st.markdown("### 规则推理局部图")
        render_graph(rows)

with tab2:
    st.subheader("规则推理边统计")

    if st.button("读取规则统计"):
        try:
            stats = get_rule_stats()
        except Exception as e:
            st.error(f"读取规则统计失败：{e}")
            st.stop()

        if not stats:
            st.warning("当前库中没有查询到规则推理边。")
            st.stop()

        stat_table = []
        name_by_rel = {v["rel"]: k for k, v in RULE_TYPES.items()}

        for row in stats:
            rel_type = row["rel_type"]
            stat_table.append(
                {
                    "规则类型": name_by_rel.get(rel_type, rel_type),
                    "关系名": rel_type,
                    "数量": row["cnt"],
                }
            )

        st.dataframe(stat_table, use_container_width=True)

        total = sum(x["数量"] for x in stat_table)
        st.metric("规则推理边总数", total)

        st.markdown("### 当前规则类型 Top 主体样例")

        selected_rule_for_sample = st.selectbox(
            "选择规则类型查看 Top 主体",
            list(RULE_TYPES.keys()),
            key="sample_rule_select",
        )

        sample_rel = RULE_TYPES[selected_rule_for_sample]["rel"]

        try:
            samples = get_sample_subjects(sample_rel)
        except Exception as e:
            st.error(f"读取样例失败：{e}")
            st.stop()

        sample_table = [
            {
                "起点": r["source"],
                "起点类型": label_short(r["source_label"]),
                "关联目标数量": r["target_count"],
            }
            for r in samples
        ]

        st.dataframe(sample_table, use_container_width=True)

with tab3:
    st.subheader("规则推理机制说明")

    st.markdown(
        """
本页面展示的是规则推理增强层的结果。规则推理不是直接由大模型自由生成，
而是在结构化图谱已有事实基础上，根据企业区域、产业、资质特征、政策覆盖范围、
产品服务对象等条件，生成新的潜在匹配关系。

### 当前规则推理类型

| 规则类型 | 关系名 | 说明 |
|---|---|---|
| 企业潜在政策推荐 | `potentiallyMatchesPolicy` | 企业与可能适配政策之间的推理关系 |
| 企业潜在产品推荐 | `potentiallyMatchesProduct` | 企业与可能适配金融产品之间的推理关系 |
| 政策覆盖产业识别 | `hasCoverageIndustry` | 政策与覆盖产业之间的推理关系 |
| 政策覆盖区域识别 | `hasCoverageRegion` | 政策与覆盖区域之间的推理关系 |
| 产品适配企业特征 | `fitsEnterpriseFeature` | 金融产品与适配企业特征之间的推理关系 |
| 产品服务重点产业 | `hasServiceFocusIndustry` | 产品或服务平台与重点服务产业之间的关系 |

### 汇报时可以这样讲

规则推理层用于弥补原始结构化事实中“显式边不足”的问题。
例如，企业本身可能没有直接连接到某项政策，但如果企业所在区域、所属产业、
资质特征与政策目标范围匹配，系统可以生成“企业潜在政策推荐”关系，
从而支持政策推荐和科技金融服务匹配。
"""
    )

