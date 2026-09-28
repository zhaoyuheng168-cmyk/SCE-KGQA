from pathlib import Path
import pandas as pd
import streamlit as st

ROOT=Path(__file__).resolve().parents[3]
TABLES=ROOT/'release_package/09_20260614_最终增补/final_experiment_package_20260613/tables'
st.set_page_config(page_title='正式评测结果',layout='wide')
st.title('正式评测结果')
st.caption('1300 题正式比较、修正消融及补充实验')
tables=sorted(TABLES.glob('*.csv'))
selected=st.selectbox('结果表',tables,format_func=lambda p:p.name)
if selected: st.dataframe(pd.read_csv(selected),hide_index=True,use_container_width=True)
st.write('主比较 SCE-KGQA 88.23% 与消融 Full 88.31% 来自两份冻结预测；使用时保留对应口径。')
