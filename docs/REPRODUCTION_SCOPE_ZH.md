# 复现范围与入口

交付包保留整个研究系统及全量冻结知识资产。用户先恢复数据库、准备运行目录，再运行实际推理。

```bash
python scripts/prepare_runtime.py
python scripts/run_qa.py --check
python scripts/run_qa.py "甘肃银行提供哪些金融产品？"
```

原实验入口已改为读取当前 Python 解释器、所配置的 Neo4j 地址及可选择的数据集。
生成阶段只向模型传问题 ID 与问题文本；Gold 只用于评分。
以下命令先输出运行计划，添加 --execute 才实际启动。没有在本次交付收尾中执行这些整套实验。

```bash
python scripts/run_experiments.py --suite main
python scripts/run_experiments.py --suite ablation
python scripts/run_experiments.py --suite natural
python scripts/run_experiments.py --suite stress
python scripts/run_experiments.py --suite kqapro-frozen
```

main 包含原 12 个正式方法的实际生成与原协议评分。
ablation 使用正式 1300 题与 expanded Gold，保留各模块开关。
natural 仅做列名适配，保持原 100 题问题与答案，使用原问答和评分程序。
stress 保留历史脚本，BM25 使用修正后的 naive_bm25_rag；失效旧 BM25 分支不运行。
kqapro-frozen 对原 11697 题 holdout 的 9 个冻结变体评分，不新增迁移范围。
迁移生成与执行脚本、MetaQA 既有实验材料均保留，详细参数见原协议。

## 尚未具备完整重建证据的部分

Official LightRAG 历史 compact 语料构建器和持久化索引未从归档找回。
已保留官方适配器、构建/查询参数和全部冻结输出；可以核对及复算严格指标。
这不等于已有完整的历史索引重建链路，不能用新构造语料冒充原 compact 语料。
KoPL 新候选执行依赖官方 KQAPro_Baselines 执行器，按照迁移目录 README 获取上游代码。

本轮有一个启用嵌入的多跳抽样进程非正常退出，尚未定位。无嵌入配置的同一问题已通过。
因此交付材料已整理齐全，但不能声称每一个完整推理分支均已在新环境验收通过。
