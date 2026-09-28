# MetaQA Final Transfer Experiment Summary

## Experimental Settings

| Setting | Route input or training condition | Purpose |
|---|---|---|
| Oracle-qtype execution | Official qtype supplied to the Core | Measure transferred typed-path execution |
| Official Test predicted-route | Predict qtype from natural language; all Test templates appear in Train | Measure removal of qtype input under seen-template conditions |
| Five-fold template holdout | Predict qtype on templates absent from training | Measure unseen-language-template generalization |

All settings execute answers through the same MetaQA adapter and unified Core.

## Main Results

| Setting | Questions | Route Accuracy | End-to-End Exact Match | Macro F1 |
|---|---:|---:|---:|---:|
| Oracle-qtype Test | 39,093 | 100% by definition | **98.619%** | **99.511%** |
| Official Test predicted-route, seen templates | 39,093 | **100.000%** | **98.619%** | **99.511%** |
| Five-fold unseen-template, fold mean | 329,282 across folds | **79.765% ± 6.473%** | **79.180% ± 6.357%** | **81.117% ± 6.075%** |
| Five-fold unseen-template, question weighted | 329,282 | **79.670%** | **79.081%** | **81.028%** |

## Official Test Predicted-Route Result

- Training unit: one representative per normalized template.
- Training templates: **521**.
- Test questions: **39,093**.
- Test templates seen in Train: **100%**.
- Route Accuracy: **39,093/39,093**.
- Answer Exact Match: **38,553/39,093**.
- Total runtime: **4.741 seconds**.

The official predicted-route result exactly matches Oracle-qtype execution,
showing that qtype input can be removed without loss when the language template
has already been observed.

## Interpretation

The experiments separate three capabilities:

1. The transferred unified Core executes known typed routes reliably.
2. Seen natural-language templates can be mapped to routes without an Oracle
   qtype input.
3. Unseen-template route prediction remains substantially harder, especially
   for 3-hop questions.

The official Test result must not be presented as unseen-language
generalization because every normalized Test template occurs in Train. The
five-fold template-held-out result is the appropriate evidence for language
template generalization.

## Transfer Claim Supported by Current Evidence

The current evidence supports:

> A domain-independent KGQA Core extracted from the Gansu system design can be
> configured through a MetaQA adapter, formally evaluated on 49 route types,
> and combined with natural-language route prediction for end-to-end QA.

It does not yet support:

> The production Gansu V8 backend and MetaQA runtime already execute through
> the exact same deployed Core implementation.
