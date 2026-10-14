# FI'L AI Model Comparison

All evaluated models below use the exact same 24-row preserved synthetic holdout. These numbers do not measure real-world performance.

- **baseline_v1** — accuracy 0.500, macro-F1 0.494, weighted-F1 0.494
- **classical_v2** — accuracy 0.500, macro-F1 0.470, weighted-F1 0.470
- **fine-tuned CAMeLBERT-DA** — accuracy 0.958, macro-F1 0.958, weighted-F1 0.958

Model selection for classical_v2 used a separate validation subset of the original training portion. The preserved holdout was not used to select the feature/model family.

CAMeLBERT was fine-tuned in Google Colab and then evaluated locally on the same preserved repository holdout. The user-reported Colab result is 89.6% on a synthetic test split; the local 95.8% result is on this repository's 24-row synthetic holdout. Both are synthetic and neither establishes real-world accuracy. Row-level predictions and the exact integration result are under `results/camelbert/`.

## Unavailable controlled metrics

- Performance by Arabic writing style: **Not evaluated** — style is not annotated in the seed data.
- Extraction precision/recall/F1 and datetime exact match: **Not evaluated** — no reviewed extraction test set exists.
- Context matching precision/recall/F1: **Not evaluated** — no labeled message-pair test set exists.
