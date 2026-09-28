# LightRAG External Baseline

Official PyPI package: `lightrag-hku`. This adapter uses LightRAG core in an isolated virtual environment and does not start a server or Docker service.

LightRAG consumes the same frozen Text+KG source as the other comparison methods. Gold fields are never passed to the framework. The formal protocol uses the `compact` natural-language variant, which preserves all frozen knowledge records while removing repeated template metadata.

## Smoke

```bash
python experiments/external_baselines/common/build_external_corpus.py --mode smoke --variant compact --smoke-docs 200
python experiments/external_baselines/lightrag/prepare_workspace.py --mode smoke --variant compact
bash experiments/external_baselines/lightrag/run_index_smoke.sh
bash experiments/external_baselines/lightrag/run_query_smoke5.sh
```

## Formal 1300

Only proceed after smoke quality and cost are reviewed.

```bash
python experiments/external_baselines/common/build_external_corpus.py --mode full --variant compact
python experiments/external_baselines/common/audit_compact_corpus.py
python experiments/external_baselines/lightrag/prepare_workspace.py --mode full --variant compact
nohup bash experiments/external_baselines/lightrag/run_index_full.sh \
  > experiments/external_baselines/logs/lightrag_index_full_runner.log 2>&1 &

# Run after indexing succeeds:
nohup bash experiments/external_baselines/lightrag/run_query_formal1300.sh \
  > experiments/external_baselines/logs/lightrag_formal1300_runner.log 2>&1 &
```

The index is reusable. Do not rebuild it for each dataset or query run.
