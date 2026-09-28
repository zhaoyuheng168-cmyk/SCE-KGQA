from pathlib import Path
import streamlit as st
ROOT=Path(__file__).resolve().parents[3]
st.set_page_config(page_title='系统说明',layout='wide')
st.markdown((ROOT/'docs/ARCHITECTURE_ZH.md').read_text(encoding='utf-8'))
