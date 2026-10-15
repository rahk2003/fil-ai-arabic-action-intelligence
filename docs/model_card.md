# FI'L AI Intent Model Card

## Preserved baseline

The active model is the preserved character TF-IDF + balanced Logistic Regression baseline. It was trained on 72 synthetic examples and evaluated on a 24-example synthetic holdout: accuracy 0.500, macro-F1 0.494. These are pipeline diagnostics, not real-world estimates.

## Classical v2 experiment

Word, character, combined word+character TF-IDF, Logistic Regression, and Linear SVM candidates were selected on an 18-row validation subset of the original training partition. The selected combined Logistic Regression model scored accuracy 0.500 and macro-F1 0.470 on the same preserved holdout, so it was **not promoted**.

## Known behavior

The active model predicts `reschedule` for `اكملي التسجيل قبل الساعة التاسعة مساء`, although the expected intent is `new_task`. The case is an expected-failure regression test. Weaknesses include negation scope, deadline-versus-reschedule semantics, implicit changes, and temporal information statements.

## Fine-tuned CAMeLBERT-DA

The local `models/FIL_AI_CAMeLBERT/` checkpoint is a fine-tuned `BertForSequenceClassification` model. Its configuration maps `0 cancellation`, `1 info_only`, `2 new_task`, and `3 reschedule`; inference refuses incompatible mappings.

The primary comparison is the reported Colab experiment on the same 125-message synthetic test split: the classical baseline recorded 72.0% accuracy / approximately 0.719 Macro-F1, and CAMeLBERT recorded 89.6% / approximately 0.895. That is a +17.6 percentage-point accuracy improvement on the same reported split. The aggregate values are preserved in `results/camelbert/colab_reported_metrics.json`; row-level predictions and exact split membership are absent, so this is a reported experiment result rather than a freshly reproduced metric. It does not establish real-world performance.

## Data Leakage warning — repository diagnostic

On the repository's preserved 24 rows CAMeLBERT scored accuracy 0.958 and Macro-F1 0.958, compared with 0.500 / 0.494 for the baseline. Those 24 rows overlap the CAMeLBERT fine-tuning corpus. The 95.8% value is therefore retained only as a contaminated integration diagnostic and must not be presented as the primary model accuracy.

The exact 500-row Colab dataset and split membership are not present in this repository. Exact duplicates and paraphrase-family leakage therefore cannot be independently audited; paraphrase-family independence remains unverified.

Known false positives include informational statements about tomorrow's online work being labeled `reschedule`, and final-report approval being labeled `cancellation`. They are retained as future reviewed-data candidates, not hard-coded rules.

The FastAPI process loads the checkpoint lazily, caches it after first use, uses batch size one and max length 128, and selects MPS when available (otherwise CPU). Scores are raw maximum softmax probabilities and are explicitly presented as uncalibrated.
