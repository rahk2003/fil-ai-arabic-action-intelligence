# FI'L AI | فِعل — Engineering Report

## Executive summary

FI'L AI is a local Arabic action-intelligence prototype. It classifies one primary intent, extracts multiple action candidates and temporal evidence, ranks possible historical-task links, and stores only user-confirmed tasks in SQLite. No paid API is used.

## Evidence and experiments

The preserved synthetic baseline scores 0.500 accuracy and 0.494 macro-F1 on 24 examples. `info_only` recall is 0.333; the largest routes are `info_only → reschedule` and `reschedule → cancellation`. A controlled classical-v2 selection experiment did not improve the held-out macro-F1 (0.470), so the original remains active.

The primary model comparison is the reported Colab experiment on the same 125-message synthetic test split: classical baseline 72.0% accuracy / approximately 0.719 Macro-F1 and fine-tuned CAMeLBERT 89.6% / approximately 0.895, an accuracy improvement of +17.6 percentage points. Aggregate metrics are preserved, but row-level predictions and split membership are not; these are reported experiment results, not a fresh reproduction or a real-world estimate.

Amazon MASSIVE ar-SA was downloaded from the official Amazon 1.1 archive and parsed with Hugging Face Datasets after the repository loading script failed. Counts are 11,514/2,033/2,974. MASSIVE supplies Saudi-localized virtual-assistant utterances and date/time spans, but not FI'L AI workplace labels. All 5,672 selected candidates remain unreviewed.

## System boundaries

Temporal extraction is rule-based and uncertainty-aware. Context matching is conservative lexical matching, not proof of identity. A fine-tuned CAMeLBERT-DA checkpoint is integrated with explicit selection, lazy loading, and same-message comparison. Its separate 95.8% repository result is retained only as a contaminated 24-row integration diagnostic because those rows overlap fine-tuning data. The exact 500-row Colab dataset is unavailable, so duplicate and paraphrase-family leakage cannot be independently audited. Extraction and context metrics remain Not evaluated where reviewed labeled data is absent.

## Most important next step

Calibrate the annotation guide on consented, de-identified natural task messages, double-label them, group by conversation/source, and lock a real test set. Only then retrain classical and CAMeLBERT candidates and compare them on the same test set.
