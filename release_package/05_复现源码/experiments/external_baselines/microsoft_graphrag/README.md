# Microsoft GraphRAG External Baseline

Official package/CLI: `graphrag`, with `graphrag init`, `graphrag index`, and `graphrag query`.

This adapter is isolated under `experiments/external_baselines/` and does not call SCE modules.

Important blocker: GraphRAG configuration changes across releases. After installation, run `graphrag init --root <workspace>` and manually configure the generated `settings.yaml` for the DashScope OpenAI-compatible endpoint. Compatibility must be verified by smoke indexing.
