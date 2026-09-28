# 部署环境

建议使用 Python 3.10，并单独创建虚拟环境。Neo4j Community 5.26.0 的独立实例已实际验证恢复。
可以使用 docker-compose.yml；本机未运行 Docker 验证。

```bash
python -m venv .venv
# Windows: .venv/Scripts/activate ; Linux: source .venv/bin/activate
python -m pip install -r requirements-baselines.lock
```

本次 Windows / Python 3.10 的完整已安装依赖记录为 requirements-tested-win-py310.lock。
它是重建并检查过的环境，不声称与旧服务器虚拟环境逐字节相同。
CPU PyTorch 可从其官方 CPU wheel 源安装；完整迁移候选生成可以按历史需求使用 CUDA。
requirements-frontend.txt 为前端依赖，外部 LightRAG 使用独立环境避免依赖冲突。

完整数据附件包含原服务器 BGE safetensors 与配置，不需要重新下载即可进行嵌入推理。
KoPL 权重通过固定官方版本下载，并核对历史文件 SHA256；其版本与 SHA256 在 models/MODEL_MANIFEST.json。
不需要保存 optimizer、scheduler、训练状态或整个服务器镜像来运行推理。

复制 .env.example 为 .env，填写自己的 Neo4j 密码与在线模型 API Key。
默认线上模型为 qwen3.5-plus，temperature=0、enable_thinking=false。
第三方 API 参数和服务可能变化，重跑预测与冻结输出可能不同。
不要把自己的 .env 或 app/kag_config.yaml 提交到公开仓库。
