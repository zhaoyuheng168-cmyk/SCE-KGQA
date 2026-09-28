# MetaQA Predicted-Route End-to-End Protocol

## Purpose

This experiment removes the Oracle-qtype assumption from evaluation. The
system receives only the natural-language question and bracketed topic entity,
predicts one of the 49 MetaQA routes, and executes that route through the same
unified Core.

## Leakage Controls

- Test qtype is used only as an evaluation label.
- The classifier never receives test qtype as input.
- Topic entity text is replaced with `TOPIC_ENTITY` before classification.
- Training uses only the official MetaQA train split.
- Dev and test questions are not used to fit the classifier.
- Gold answers are never used for route prediction or answer filtering.

## Baseline Model

- Features: word 1-3 gram TF-IDF over masked questions.
- Classifier: linear support-vector classifier.
- Output: one of 49 typed route specifications.
- Execution: the existing MetaQA adapter and unified Core.

This is a supervised in-domain route-prediction baseline. It tests removal of
the Oracle-qtype assumption, but it is not a zero-shot cross-domain language
understanding experiment.

## Metrics

- Route classification accuracy.
- End-to-end answer Exact Match.
- End-to-end macro F1.
- Results by hop and gold qtype.
- Runtime for training, route prediction, graph loading, and answer execution.

## Stages

1. Bounded dev smoke: 20 train and 3 dev questions per qtype.
2. Template-overlap audit across official splits.
3. Template-held-out bounded preflight.
4. Five-fold full template-held-out evaluation.
5. Full-train, full-test official-split evaluation.

Official-split results measure removal of the Oracle-qtype input under
template-seen conditions. Template-held-out results measure route
generalization to unseen natural-language templates.

For five-fold evaluation, templates are assigned deterministically within each
qtype using `--fold-count 5 --fold-index 0..4`. The folds are disjoint and
their union covers every normalized training template.

The five-fold stability experiment uses `--train-unit template`: each unique
normalized training template contributes one classifier example, while every
question belonging to a held-out template remains in evaluation. This removes
template-frequency bias and avoids repeatedly fitting identical language
inputs.
