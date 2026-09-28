# -*- coding: utf-8 -*-
import os
import re
import subprocess
import sys
from pathlib import Path

import streamlit as st


try:
    st.set_page_config(page_title="智能问答", page_icon="💬", layout="wide")
except Exception:
    pass


ROOT = Path(__file__).resolve().parents[3]
V8_SCRIPT = ROOT / "scripts/run_qa.py"


EXAMPLE_GROUPS = {
    "单跳正向查询": {
        "说明": "从一个主体出发，查询它直接连接的对象，例如金融机构提供哪些产品、政策支持哪些产品。",
        "例题": [
            "甘肃银行提供什么科技金融产品？",
            "中国银行甘肃省分行提供什么科技金融产品？",
            "甘肃省科学技术厅发布了哪些政策？",
            "哪些政策支持惠知贷？",
        ],
    },
    "反向单跳查询": {
        "说明": "从产品、政策、企业等目标反查来源，例如某产品由谁提供、某产品被哪些政策支持。",
        "例题": [
            "惠知贷由哪家金融机构提供？",
            "科技贷被哪些政策支持？",
            "科创贷由哪些金融机构提供？",
            "专利转化贷由哪家金融机构提供？",
        ],
    },
    "规则推理问题": {
        "说明": "查询由规则推理生成的潜在匹配关系，例如企业潜在匹配政策、产品适配企业特征等。",
        "例题": [
            "根据规则推理，兰州建鑫消防科技有限公司潜在匹配哪些政策？",
            "根据规则推理，兰州威特焊材科技股份有限公司潜在匹配哪些政策？",
            "根据规则推理，兰州大唐园林科技有限公司潜在匹配哪些政策？",
            "根据规则推理，哪些政策覆盖生物医药产业？",
        ],
    },
    "泛关系问答": {
        "说明": "围绕一个主体查看图谱邻域对象。宽泛关系返回多类型对象；窄泛关系限定产品、政策、机构、企业、事件等目标类型。",
        "例题": [
            "围绕甘肃银行，图谱中能看到哪些相关对象？",
            "甘肃银行在当前图谱中关联了哪些产品、企业或贷款事件？",
            "围绕惠知贷，图谱里能看到哪些相关机构、政策或企业画像？",
            "科技贷在图谱里关联了哪些机构、政策或企业画像？",
            "甘肃渭水源健康产业科技有限公司在图谱中关联了哪些政策、产品、地区、行业或事件？",
            "想全面了解中国邮政储蓄银行甘肃省分行，图谱里有哪些关键信息？",
        ],
    },
    "多跳问答": {
        "说明": "跨越多个关系链路进行查询，例如机构—产品—企业—特征—地区、政策—产品—企业—行业/特征等链路。",
        "例题": [
            "从“机构→产品→企业→特征→地区”的组合链看，中国邮政储蓄银行甘肃省分行在兰州市主要服务了哪些专精特新中小企业？",
            "从政策支持产品再到企业所属行业看，甘肃省科技型企业成长金融护航计划实施方案落到了哪些行业？",
            "关于发布甘肃省2025年度第二批科技创新政策改革试点任务的通知，最终主要覆盖到哪些企业特征？",
            "甘肃省“十四五”科技创新规划顺着产品服务链最终主要触达到哪些行业的企业？",
        ],
    },
    "非结构化问答": {
        "说明": "查询由非结构化文本抽取补充的贷款事件、机构贷款支持、KAG evidence 证据增强等问题。",
        "例题": [
            "甘肃华羚乳品股份有限公司获得了哪家金融机构的贷款支持？",
            "甘肃临潭县青石山水电有限责任公司获得了哪家金融机构的贷款支持？",
            "杭州新再灵科技公司获得了哪家金融机构的贷款支持？",
            "惠知贷由哪家金融机构提供？",
        ],
    },
    "Level2 自由问法": {
        "说明": "自然语言改写后的自由问法，重点测试实体识别、意图识别和路由泛化能力。",
        "例题": [
            "我想了解中国银行甘肃省分行有哪些科技金融产品？",
            "请问甘肃银行目前推出了哪些科技金融产品？",
            "中国邮政储蓄银行甘肃省分行有哪些支持科技创新的金融产品？",
            "惠知贷目前是哪家金融机构在提供？",
        ],
    },
    "边界/拒答问题": {
        "说明": "测试系统是否能对知识库范围外、证据不足或主体不存在的问题进行拒答。",
        "例题": [
            "美国苹果公司获得了甘肃哪些科技金融政策支持？",
            "火星基地企业可以申请甘肃银行哪些科技金融产品？",
            "某不存在企业获得了哪家金融机构贷款支持？",
            "甘肃科技金融图谱中有没有关于新能源汽车出口退税的完整政策细则？",
        ],
    },
}


def extract_section(text: str, name: str) -> str:
    pattern = rf"===== {re.escape(name)} =====\n(.*?)(?=\n===== |\Z)"
    m = re.search(pattern, text, flags=re.S)
    return m.group(1).strip() if m else ""


def parse_meta(raw: str):
    meta = {}
    keys = [
        "query",
        "question_type",
        "subject",
        "route",
        "intent_source",
        "final_route",
        "answer_source",
        "kag_used",
        "graph_answers",
        "kag_answers",
    ]

    for key in keys:
        m = re.search(rf"^{key}\s*=\s*(.*)$", raw, flags=re.M)
        if m:
            meta[key] = m.group(1).strip()

    meta["answer"] = extract_section(raw, "ANSWER")
    meta["cypher"] = extract_section(raw, "CYPHER")
    meta["kag_evidence"] = (
        extract_section(raw, "KAG EVIDENCE")
        or extract_section(raw, "KAG EVIDENCE ANSWER")
        or meta.get("kag_answers", "")
    )
    return meta


def run_v8(question: str, timeout: int = 180) -> str:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")

    # 默认使用当前 Release Runtime 的 structured Neo4j。
    env.setdefault("GTF_NEO4J_URI", "bolt://127.0.0.1:7688")
    env.setdefault("GTF_NEO4J_USER", "neo4j")
    env.setdefault("GTF_NEO4J_PASSWORD", os.getenv("GTF_NEO4J_PASSWORD", ""))
    env.setdefault("GTF_NEO4J_DATABASE", "neo4j")

    env.setdefault("GTF_LEVEL2_SUBJECT_SOURCE", "graph")
    env.setdefault("GTF_ENABLE_KAG_FALLBACK", "1")
    env.setdefault("GTF_ENABLE_V7_FALLBACK", "0")
    env.setdefault("GTF_ENABLE_V8_KAG_MULTIHOP_PLANNER", "1")

    proc = subprocess.run(
        [sys.executable, str(V8_SCRIPT), question],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=env,
    )
    return proc.stdout or ""


st.title("💬 智能问答")
st.caption(
    "统一调用 V8 主问答入口，支持单跳查询、反向查询、规则推理、多跳问答、"
    "宽/窄泛关系查询、非结构化证据增强、Level2 自由问法和边界拒答。"
)

st.info(
    "左侧先选择问题类型，再选择该类型下的示例问题。示例题会自动填入文本框，"
    "点击查询后可查看最终答案、路由、Cypher 查询语句和 KAG evidence。"
)

with st.sidebar:
    st.header("示例问题")

    group_name = st.selectbox(
        "选择问题类型",
        list(EXAMPLE_GROUPS.keys()),
        index=0,
    )

    group = EXAMPLE_GROUPS[group_name]
    st.info(group["说明"])

    example_question = st.selectbox(
        "选择该类型示例问题",
        group["例题"],
        index=0,
    )

    timeout = st.slider(
        "V8 超时时间/秒",
        min_value=60,
        max_value=300,
        value=180,
        step=30,
    )

    st.divider()
    st.markdown("### 当前环境")
    st.code(
        "GTF_NEO4J_URI=bolt://127.0.0.1:7688\n"
        "GTF_LEVEL2_SUBJECT_SOURCE=graph\n"
        "GTF_ENABLE_KAG_FALLBACK=1\n"
        "GTF_ENABLE_V7_FALLBACK=1\n"
        "GTF_ENABLE_V8_KAG_MULTIHOP_PLANNER=1",
        language="bash",
    )


question = st.text_area(
    "请输入问题",
    value=example_question,
    height=120,
)

run_btn = st.button("查询", type="primary")

if run_btn:
    if not question.strip():
        st.warning("请输入问题。")
    else:
        with st.spinner("正在调用 V8 问答链路..."):
            try:
                raw = run_v8(question.strip(), timeout=timeout)
                meta = parse_meta(raw)

                st.subheader("最终答案")

                if meta.get("answer"):
                    st.success(meta["answer"])
                else:
                    st.warning("未解析到 ANSWER 段，请展开查看 V8 原始输出。")

                st.divider()
                st.subheader("问答链路解释")

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("question_type", meta.get("question_type", ""))
                c2.metric("subject", meta.get("subject", ""))
                c3.metric("route", meta.get("route", ""))
                c4.metric("answer_source", meta.get("answer_source", ""))

                c5, c6, c7 = st.columns(3)
                c5.metric("final_route", meta.get("final_route", ""))
                c6.metric("intent_source", meta.get("intent_source", ""))
                c7.metric("kag_used", meta.get("kag_used", "False"))

                st.markdown("### 图谱答案与 KAG 答案")

                left, right = st.columns(2)
                with left:
                    st.markdown("#### graph_answers")
                    st.code(meta.get("graph_answers", "") or "无", language="text")

                with right:
                    st.markdown("#### kag_answers")
                    st.code(meta.get("kag_answers", "") or "无", language="text")

                with st.expander("查看 Cypher 查询语句", expanded=False):
                    st.code(meta.get("cypher", "") or "无 Cypher", language="cypher")

                with st.expander("查看 KAG Evidence", expanded=False):
                    if meta.get("kag_evidence"):
                        st.code(meta["kag_evidence"], language="text")
                    else:
                        st.code("无 KAG Evidence", language="text")

                with st.expander("查看 V8 原始输出", expanded=False):
                    st.code(raw, language="text")

            except subprocess.TimeoutExpired:
                st.error("V8 调用超时，可以调大左侧超时时间。")
            except Exception as e:
                st.error("V8 调用失败，请检查环境变量、Neo4j 服务和端口。")
                st.exception(e)
else:
    st.subheader("页面说明")
    st.markdown(
        """
本页面用于展示系统的统一问答能力。当前 Release Runtime 以 **V8** 作为主问答入口，
能够根据问题类型自动路由到结构化图谱查询、规则推理、非结构化证据增强或多跳查询链路。

建议演示顺序：

1. 先选择 **单跳正向查询**，展示普通结构化图谱问答；
2. 再选择 **反向单跳查询**，展示产品反查机构/政策；
3. 再选择 **规则推理问题**，展示规则边参与问答；
4. 再选择 **泛关系问答**，分别展示宽泛关系和窄泛关系；
5. 再选择 **非结构化问答**，展示 KAG evidence 辅助支撑；
6. 最后选择 **多跳问答** 或 **Level2 自由问法**，展示自然语言泛化和多跳链路能力。
"""
    )

