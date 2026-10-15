# FI'L AI Model Comparison

## Primary comparison — reported Colab experiment

Both models below were evaluated on the same reported 125-message synthetic test split.

| Model | Accuracy | Macro-F1 | Difference in accuracy |
|---|---:|---:|---:|
| Classical baseline | 72.0% | ≈0.719 | — |
| Fine-tuned CAMeLBERT-DA | 89.6% | ≈0.895 | +17.6 percentage points |

Source of truth: `results/camelbert/colab_reported_metrics.json`.

These are synthetic-data experiment results, not real-world accuracy. The repository preserves aggregate metrics and the reported 300/75/125 split sizes, but it does not contain the exact 500 rows, split membership, row-level test predictions, or confusion matrix. The values therefore cannot be freshly reproduced from repository files alone. Exact duplicates and paraphrase-family leakage cannot be audited; independence at the paraphrase-family level is unverified.

## Data Leakage warning — 24-row diagnostic only

The following results remain tied to the preserved 24-row repository holdout and are not the primary model comparison:

- **baseline_v1** — accuracy 0.500, Macro-F1 0.494, weighted-F1 0.494
- **classical_v2** — accuracy 0.500, Macro-F1 0.470, weighted-F1 0.470
- **fine-tuned CAMeLBERT-DA** — accuracy 0.958, Macro-F1 0.958, weighted-F1 0.958

The 24 rows overlap the CAMeLBERT fine-tuning corpus. CAMeLBERT's 95.8% is therefore a contaminated integration diagnostic, not an independent estimate of generalization. Raw predictions and metrics under `results/camelbert/` are preserved unchanged for traceability.

## Unavailable controlled metrics

- Precision, recall, confusion matrix, and row-level errors for the 125-message Colab test: **not saved**.
- Performance by Arabic writing style: **not evaluated** — style is not annotated in the seed data.
- Extraction precision/recall/F1 and datetime exact match: **not evaluated** — no reviewed extraction test set exists.
- Real-world in-domain accuracy: **not evaluated** — the current verified human-reviewed count is zero.
