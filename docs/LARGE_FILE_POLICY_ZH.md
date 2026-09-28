# GitHub 与完整数据附件布局

代码、配置、文档、完整 Gold、关键结果表放入 repository/。
全量冻结图谱、加工证据、逐题预测与构建记录放入完整 ZIP 附件，下载后解压到仓库根目录。
两边的相对路径保持一致。附件生成全量清单及 SHA256，支持脱离 Git 审计。

普通 Git 单个对象有 100 MB 限制：
https://docs.github.com/en/repositories/creating-and-managing-repositories/repository-limits

附件可上传 GitHub Release 或合适的数据托管平台，最终公开 URL 必须在成功上传后填写。
本地准备阶段不伪造 DOI、数据链接或成功上传状态。
