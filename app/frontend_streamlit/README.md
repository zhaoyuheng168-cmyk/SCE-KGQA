# 公开研究前端

前端读取本仓库正式 1300 题和冻结结果；实际问答调用 scripts/run_qa.py。
先按根目录 README.md 恢复 Neo4j 图谱并组装 runtime，再执行：

```bash
pip install -r requirements-frontend.txt
streamlit run app/frontend_streamlit/app.py
```

图谱可视化和规则页面读取用户本地 Neo4j。用户自己的凭据只放本地 .env 或环境变量。
