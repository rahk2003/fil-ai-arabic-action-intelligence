# CAMeLBERT Integration Verification

Generated from actual local inference on 2026-10-14. No model was retrained by this evaluation.

## Checkpoint and mapping

- Local checkpoint: `models/FIL_AI_CAMeLBERT/`
- Runtime model identifier: `camelbert-da:FIL_AI_CAMeLBERT`
- Architecture: `BertForSequenceClassification`
- Verified mapping: `0=cancellation`, `1=info_only`, `2=new_task`, `3=reschedule`
- Runtime device in this verification: CPU
- Loading behavior: lazy first use, then one cached model per FastAPI process
- Failure behavior: explicit CAMeLBERT requests fail with HTTP 503; no silent baseline substitution

## Same-holdout comparison

Both models were run on the exact 24 messages and labels in `results/test_predictions.csv`.

| Model | Accuracy | Macro precision | Macro recall | Macro F1 | Weighted F1 | Mean inference latency |
|---|---:|---:|---:|---:|---:|---:|
| TF-IDF + Logistic Regression | 0.500 | 0.524 | 0.500 | 0.494 | 0.494 | 1.23 ms |
| Fine-tuned CAMeLBERT-DA | 0.958 | 0.964 | 0.958 | 0.958 | 0.958 | 115.47 ms |

Latency is an observed CPU measurement and excludes one-time lazy checkpoint loading. It is not a benchmark for every Mac.

The holdout is synthetic. These values compare the implementations under one controlled repository test but cannot establish Saudi workplace or real-world accuracy. The separately reported 89.6% Colab test accuracy is also synthetic and is not assumed to use this exact 24-row split.

## Observed failures

The single CAMeLBERT error on the preserved holdout was:

- `ما يحتاج ترفعين النموذج بعد القرار الجديد.` — expected `cancellation`, predicted `new_task`, uncalibrated score 0.670. Category: negated obligation/cancellation scope.

The user-provided failure cases were reproduced locally:

- `بكرة الدوام أون لاين` — expected `info_only`, predicted `reschedule`, uncalibrated score 0.756. The model appears to over-associate future-time wording with a schedule change despite the absence of an explicit task-change action.
- `تم اعتماد التقرير النهائي` — expected `info_only`, predicted `cancellation`, uncalibrated score 0.526. The completion/approval construction is confused with terminating or canceling an action.

These cases are recorded in `known_failure_cases.csv`. They are not sentence-specific correction rules and are not used for online retraining.

## Generated artifacts

- `same_holdout_predictions.csv` — row-level predictions, scores, latency, and correctness for both models.
- `same_holdout_metrics.csv` — directly computed comparison metrics.
- `known_failure_cases.csv` — reproduced known failures with both model outputs.
- `integration_summary.json` — checkpoint, label map, runtime, provenance, and metrics.
