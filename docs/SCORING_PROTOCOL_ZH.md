# 冻结评分协议

正式主比较使用 1300 题 expanded Gold。原始 Gold 同时保留，不修改预测或标注。
六月原始 Task-aware 评分器已从历史服务器归档找回，默认复算直接调用原实现。
此前为缺失源码而设置的兼容重建已撤销；较晚评分器另存为 available_20260909 版本供核对。

默认原协议：Strict 88.230769%，Task-aware 92.230769%。
12 个方法、15600 条逐题输出均与历史评分一致，见根目录 SCORING_VALIDATION.json。
消融 Full System 88.31% 属于另一份冻结输出，不覆盖主比较 88.23%。
Official LightRAG 原报告只包含严格指标，不补写不存在的 Task-aware 数字。

命令：python scripts/recompute_metrics.py --method sce_kgqa_full
完整方法列表见 SCORING_VALIDATION.json。
