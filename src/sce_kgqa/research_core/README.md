# Selected V8 research-core snapshot

This directory preserves selected files from the final V8 research system for
method inspection. It includes the main graph-first wrapper and helpers related
to multihop planning, type gates, validation, scope control and evidence
retrieval.

Only portability and publication-hygiene edits were made to the copied files:

1. The original server root was replaced by `SCE_KGQA_RESEARCH_ROOT` with a
   repository-relative default.
2. The script and embedding directories are resolved from `__file__`.
3. The local Neo4j default uses `localhost` rather than a numeric address.
4. The embedding helper resolves its repository root at the new directory depth.
5. One historical evaluation-set label in a code comment was generalized.

No routing rule, Schema registry, query template, metric or answer logic was
rewritten. The full data, indexes, model settings and original runtime are not
included, so this snapshot is not the supported demo entry point.
