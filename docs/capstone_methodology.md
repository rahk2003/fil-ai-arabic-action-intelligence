# Capstone Methodology

## Problem and users

Arabic workplace messages often encode tasks, deadline changes, cancellations, and status information in MSA or Saudi conversational language. FI'L AI supports students, teams, and coordinators by producing reviewable structured actions while preserving the original evidence.

## Method

1. Establish a reproducible TF-IDF baseline and error analysis.
2. Preserve provenance and assess published data without changing its objective.
3. Define annotation rules and collect consented, de-identified in-domain messages.
4. Compare models only on one locked in-domain test set.
5. Evaluate intent classification, extraction, and context matching separately.

## Current implementation

Machine learning performs four-class intent prediction. Rules extract multiple actions and common Arabic temporal expressions. A separate contextual action layer represents scope, requirement, priority, schedule, cancellation, completion, and clarification operations. Cached multilingual MiniLM sentence embeddings are combined with lexical, entity, and recency evidence to rank possible prior tasks; cosine similarity never mutates or merges a task. SQLAlchemy stores only confirmed tasks and event history in the preserved SQLite database or optional PostgreSQL. FastAPI exposes validated REST endpoints; the Arabic-first React application covers analysis, task management, conversation suggestions, evaluation, dataset provenance, reviewed corrections, and a Gregorian calendar. Gradio remains available as a backup demo.

## Evaluation

Intent metrics are accuracy, macro/weighted F1, and class precision/recall. Extraction should later use span/entity precision, recall, and F1 plus normalized-datetime exact match. Context matching requires a human-labeled pair dataset before precision/recall/F1 are reportable.

The primary model comparison is the reported Colab experiment on one shared 125-message synthetic test split: classical baseline 72.0% accuracy / approximately 0.719 Macro-F1 versus fine-tuned CAMeLBERT 89.6% / approximately 0.895, a +17.6 percentage-point accuracy difference. The aggregate metrics are saved, but the exact 500 rows, split membership, test predictions, and confusion matrix are not in the repository. The results are therefore reported—not freshly reproduced—and cannot establish real-world accuracy.

## Limitations

The preserved baseline is trained on 96 synthetic messages, and the integrated fine-tuned CAMeLBERT checkpoint was also trained/evaluated using synthetic task-specific data. The separate repository diagnostic gives CAMeLBERT 0.958 Macro-F1 on 24 rows, but those rows overlap its fine-tuning data; this 95.8% result is data-contaminated and is not the primary comparison. Because the exact 500-message dataset is unavailable, exact-duplicate and paraphrase-family leakage cannot be audited. Embedding matching was compared with lexical matching on the same tiny eight-pair synthetic test partition: F1 0.500 versus 0.400, with two embedding false matches versus zero lexical false matches. This is insufficient for a stable threshold or real-world claim. Temporal rules cover a bounded phrase set, and a consented, human-verified real-world evaluation set remains outstanding.
