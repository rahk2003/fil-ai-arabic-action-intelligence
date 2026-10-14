# FI'L AI | فِعل — Engineering Report

## Executive summary

FI'L AI is a local Arabic action-intelligence prototype. It classifies one primary intent, extracts multiple action candidates and temporal evidence, ranks possible historical-task links, and stores only user-confirmed tasks in SQLite. No paid API is used.

## Evidence and experiments

The preserved synthetic baseline scores 0.500 accuracy and 0.494 macro-F1 on 24 examples. `info_only` recall is 0.333; the largest routes are `info_only → reschedule` and `reschedule → cancellation`. A controlled classical-v2 selection experiment did not improve the held-out macro-F1 (0.470), so the original remains active.

Amazon MASSIVE ar-SA was downloaded from the official Amazon 1.1 archive and parsed with Hugging Face Datasets after the repository loading script failed. Counts are 11,514/2,033/2,974. MASSIVE supplies Saudi-localized virtual-assistant utterances and date/time spans, but not FI'L AI workplace labels. All 5,672 selected candidates remain unreviewed.

## System boundaries

Temporal extraction is rule-based and uncertainty-aware. Context matching is conservative lexical matching, not proof of identity. A fine-tuned CAMeLBERT-DA checkpoint is now integrated with explicit selection, lazy loading, and same-message comparison. It scored 0.958 macro-F1 on the preserved 24-row synthetic holdout; the separately reported 89.6% Colab accuracy is also synthetic. Extraction and context metrics remain Not evaluated where reviewed labeled data is absent.

## Most important next step

Calibrate the annotation guide on consented, de-identified natural task messages, double-label them, group by conversation/source, and lock a real test set. Only then retrain classical and CAMeLBERT candidates and compare them on the same test set.
