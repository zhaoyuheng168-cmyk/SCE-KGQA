# Architecture

## Runtime layers

1. **Question grounding** identifies domain entities, aliases, relation clues and the requested answer type.
2. **Schema validation** checks directed triples of the form `(source type, relation, target type)` before execution.
3. **Plan construction** selects a direct query, reverse relation, explicit multihop path, rule filter or evidence lookup.
4. **Execution** obtains candidate entities from graph paths and applies business conditions when required.
5. **Answer validation** checks Schema consistency, target type and available support.
6. **Boundary control** returns a refusal when the entity, path, answer type or support condition cannot be established.

## Lightweight showcase

The public engine in `src/sce_kgqa/engine.py` executes against
`data/samples/graph_sample.json`. It is deliberately dependency-free and uses
only a small curated graph. This makes entity grounding, path selection,
relation direction, rule filtering and refusal behavior inspectable without a
database service.

## Research-core snapshot

`src/sce_kgqa/research_core/` contains selected files copied from the V8
research runtime. The main V8 file was not reorganized or algorithmically
rewritten; only its original server root and loopback address were replaced by
an environment-based repository root and `localhost`. Full data, indexes,
model configuration and the original runtime environment are not included.

The snapshot is supplied for code review and method inspection. The supported
entry point for this repository remains the lightweight engine and Streamlit
application.

## Sample Schema

```text
FinancialInstitution -[providesProduct]-> FinancialProduct
FinancialProduct     -[servesEnterprise]-> Enterprise
Enterprise           -[hasFeature]-> QualificationCreditFeature
Enterprise           -[locatedIn]-> Region
Enterprise           -[belongsToIndustry]-> IndustrySegment
```

Relation direction is part of the contract. Reverse questions traverse an
existing relation in reverse during query execution; they do not create a new
inverse fact.
