from pathlib import Path
import json
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT/'release_package/04_数据与知识资源'
REPORT = ROOT/'release_package/02_实验协议与报告/formal1300_protocol_v2/sce_kgqa_full'
st.set_page_config(page_title='甘肃省科技金融知识图谱问答系统',page_icon='🏦',layout='wide')
st.title('甘肃省科技金融知识图谱问答系统')
st.caption('SCE-KGQA · 完整研究资产 · 2026.09.28')
strict=json.loads((REPORT/'strict_metrics.json').read_text(encoding='utf-8'))
task=json.loads((REPORT/'task_aware_metrics/paper_corrected_metrics_summary.json').read_text(encoding='utf-8'))
meta=json.loads((DATA/'runtime_data/neo4j_export/metadata.json').read_text(encoding='utf-8'))
cols=st.columns(4)
for col,(label,value) in zip(cols,[('正式问题',strict['total']),('严格准确率',f"{strict['accuracy']:.2%}"),('任务感知成功率',f"{task['paper_corrected_accuracy']:.2%}"),('图谱',f"{meta['node_count']} 节点 / {meta['relationship_count']} 关系")]):
    col.metric(label,value)
st.write('系统使用领域 Schema 约束、图路径执行、规则推理、实体归一、证据和范围判定完成问答。')
st.write('侧栏提供真实问答、正式结果、图谱可视化、规则和证据浏览。')
st.dataframe(pd.read_csv(DATA/'benchmark/gtf_kgqa_1300_formal.csv')[['question_id','category','question']].head(20),hide_index=True,use_container_width=True)
st.info('首页指标来自冻结预测文件，以 expanded Gold 评分。实际问答结果随本地配置和模型服务变化。')
