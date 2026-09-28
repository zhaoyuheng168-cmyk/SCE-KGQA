from pathlib import Path
import json
import streamlit as st

ROOT=Path(__file__).resolve().parents[3]
CORPUS=ROOT/'release_package/04_数据与知识资源/corpus/evidence_corpus.jsonl'
st.set_page_config(page_title='证据库',layout='wide')
st.title('加工证据库')
st.caption('完整冻结证据语料，保留证据 ID 和来源记录')
query=st.text_input('检索关键词')
rows=[]
with CORPUS.open(encoding='utf-8') as f:
    for line in f:
        row=json.loads(line)
        if not query or query in row.get('text',''):
            rows.append(row)
        if len(rows)>=50: break
for row in rows:
    with st.expander(row.get('doc_id','证据')):
        st.text(row.get('text',''))
        st.json(row.get('metadata',{}))
st.write('单次最多展示 50 条。来源文字按原来源条款使用。')
