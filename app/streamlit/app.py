"""Streamlit interface for the lightweight public showcase."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from sce_kgqa import load_default_engine  # noqa: E402


SAMPLE_QUESTIONS = [
    "交行提供哪些产品？",
    "科创快贷由哪家金融机构提供？",
    "交通银行通过科创快贷主要服务到了哪些企业特征？",
    "科创快贷服务的专精特新企业有哪些？",
    "示例制药A位于哪里？",
    "科创快贷的公开依据是什么？",
    "火星科技公司适合哪些产品？",
]


st.set_page_config(page_title="SCE-KGQA Showcase", layout="wide")
st.title("SCE-KGQA 轻量问答演示")
st.caption("公开样例模式：展示实体归一、Schema 路径、规则筛选、证据说明与边界拒答。")

metric_columns = st.columns(4)
metric_columns[0].metric("正式测试题", "1300")
metric_columns[1].metric("严格准确率", "88.23%")
metric_columns[2].metric("任务感知成功率", "92.23%")
metric_columns[3].metric("关系类型", "20")

with st.sidebar:
    st.subheader("样例问题")
    selected = st.radio("选择一个样例", SAMPLE_QUESTIONS, label_visibility="collapsed")
    st.divider()
    st.caption("当前页面不连接完整科研图谱，也不包含正式测试集 Gold。")

question = st.text_area("输入问题", value=selected, height=90)
run = st.button("执行查询", type="primary", use_container_width=False)

if run:
    result = load_default_engine().answer(question)
    if result.refused:
        st.error(f"边界化拒答：{result.refusal_reason}")
    else:
        st.success("；".join(result.answers))

    left, right = st.columns([1, 1])
    with left:
        st.subheader("执行信息")
        st.write(f"**路由：** `{result.route}`")
        st.write(f"**目标类型：** `{result.answer_type or 'N/A'}`")
        st.write("**实体归一：**")
        st.dataframe(result.normalized_entities, use_container_width=True, hide_index=True)
        st.write("**一致性检查：**")
        st.json(result.checks)
    with right:
        st.subheader("路径与证据")
        if result.paths:
            for path in result.paths:
                st.code(path, language=None)
        else:
            st.caption("本次路由没有生成图路径。")
        if result.evidence:
            for item in result.evidence:
                st.write(f"- {item}")
        else:
            st.caption("公开样例中没有可显示的支持片段。")

    with st.expander("查看结构化结果"):
        st.code(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), language="json")

st.divider()
st.caption(
    "说明：页面指标来自冻结的 1300 题正式评测；当前交互仅运行小型公开样例，"
    "不用于复算论文指标。论文已投稿，尚未录用。"
)
