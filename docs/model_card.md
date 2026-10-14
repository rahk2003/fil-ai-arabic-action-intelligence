# FI'L AI Intent Model Card

## Preserved baseline

The active model is the preserved character TF-IDF + balanced Logistic Regression baseline. It was trained on 72 synthetic examples and evaluated on a 24-example synthetic holdout: accuracy 0.500, macro-F1 0.494. These are pipeline diagnostics, not real-world estimates.

## Classical v2 experiment

Word, character, combined word+character TF-IDF, Logistic Regression, and Linear SVM candidates were selected on an 18-row validation subset of the original training partition. The selected combined Logistic Regression model scored accuracy 0.500 and macro-F1 0.470 on the same preserved holdout, so it was **not promoted**.

## Known behavior

The active model predicts `reschedule` for `اكملي التسجيل قبل الساعة التاسعة مساء`, although the expected intent is `new_task`. The case is an expected-failure regression test. Weaknesses include negation scope, deadline-versus-reschedule semantics, implicit changes, and temporal information statements.

## Fine-tuned CAMeLBERT-DA

The local `models/FIL_AI_CAMeLBERT/` checkpoint is a fine-tuned `BertForSequenceClassification` model. Its configuration maps `0 cancellation`, `1 info_only`, `2 new_task`, and `3 reschedule`; inference refuses incompatible mappings.

On the repository's preserved 24 rows it scored accuracy 0.958 and macro-F1 0.958, compared with 0.500 / 0.494 for the baseline. Those 24 rows overlap the CAMeLBERT fine-tuning corpus, so the number is a contaminated integration diagnostic. The separately reported Colab comparison on one 125-row synthetic split is 89.6% / approximately 0.895 for CAMeLBERT versus 72.0% / approximately 0.719 for the classical baseline. Neither establishes real-world performance.

Known false positives include informational statements about tomorrow's online work being labeled `reschedule`, and final-report approval being labeled `cancellation`. They are retained as future reviewed-data candidates, not hard-coded rules.

The FastAPI process loads the checkpoint lazily, caches it after first use, uses batch size one and max length 128, and selects MPS when available (otherwise CPU). Scores are raw maximum softmax probabilities and are explicitly presented as uncalibrated.
