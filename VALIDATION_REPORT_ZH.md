# 实际验证记录

本次完成文件整理与恢复验证，不重跑历史整套实验。

| 检查 | 实际结果 | 证据 |
|---|---|---|
| 正式数据、图谱、语料 | 保留历史全量资产；核心 7 份数据按原文件哈希核对 | 最终交付目录 FINAL_VERIFICATION.json |
| 历史六月评分器 | 原代码从归档找回，未经兼容重写 | docs/RECOVERED_SERVER_ASSETS.json |
| 冻结正式比较评分 | 12 个方法 × 1300 条，汇总与逐题均一致 | SCORING_VALIDATION.json |
| 新建 Python 环境 | Python 3.10；依赖安装与 pip check 通过 | requirements-tested-win-py310.lock |
| BGE 与索引 | 历史模型加载成功；实体 1675、证据 11873、关系 17 条索引可检索 | docs/MODEL_VALIDATION.json |
| KoPL 推理权重 | 模型加载和前向检查通过；没有新增迁移实验 | docs/MODEL_VALIDATION.json |
| 实际 Neo4j 恢复 | 独立 Community 5.26.0 数据库恢复 1707 节点、31018 关系 | docs/BACKEND_VALIDATION.json |
| 真实问答，无在线路由 | 银行产品与科技 e 贷多跳问题返回预期图谱答案 | docs/BACKEND_VALIDATION.json |
| 嵌入开启的问答抽样 | 银行产品问题正常；多跳抽样进程非正常退出，未通过该项验收 | docs/BACKEND_EMBEDDING_VALIDATION.json |
| 在线 API 完整推理 | 本次没有重新运行 | 使用历史正式预测与结果，不能称作本轮全部验证 |
| Docker 容器启动 | 本机无 Docker，未执行；实际数据库恢复使用独立 Java 服务 | 不把原生验证写成 Docker 验证 |

“兰州市有哪些企业？”在未启用在线路由的有限配置中拒答，记录为能力观察，
不计作功能正确。嵌入多跳抽样退出没有获得错误输出，原因未定位；历史结果和代码原样保留。

Official LightRAG 的适配器、协议、逐题结果与严格评分保留；历史紧凑语料构建器和索引未找回，
该方法目前能复算冻结结果，不能宣称从历史索引逐字节重建已验证。详情见 docs/REPRODUCTION_SCOPE_ZH.md。

最终 ZIP 逐文件 SHA256、CRC、敏感信息模式检查见交付目录的 FINAL_VERIFICATION.json 与 FINAL_SAFETY_REPORT.json。
这些检查不能证明不存在任何敏感内容，也不能替代第三方来源授权。
