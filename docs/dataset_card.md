# FI'L AI Dataset Card

## Sources

1. **Synthetic seed:** 96 manually written prototype messages, exactly 24 per target class. No real-world performance claim is valid.
2. **Expanded synthetic fine-tuning set:** 500 messages used in the Colab CAMeLBERT experiment, reported as 300 train / 75 validation / 125 test. The row-level file is not present in this repository, so exact duplicates and paraphrase-family leakage cannot be re-audited locally.
3. **Amazon MASSIVE ar-SA:** 16,521 CC BY 4.0 localized virtual-assistant utterances. Original labels/splits are preserved. It is not workplace data and contributes zero supervised FI'L AI rows.
4. **Human-reviewed in-domain:** workflow prepared; zero rows currently available.

## Target labels

See `data/annotation/labeling_guidelines.md`. Primary labels are `new_task`, `reschedule`, `cancellation`, and `info_only`; multi-action details belong in extraction fields.

## Splits and leakage

The historical baseline uses 72 synthetic training and 24 stratified synthetic holdout rows. There are no exact or normalized duplicates in the seed set, but shared author/template style remains a leakage/generalization risk. The repository's 24-row CAMeLBERT diagnostic overlaps the fine-tuning corpus and is explicitly contaminated. MASSIVE's official splits are preserved. Future in-domain data must be grouped by conversation/source/paraphrase family before splitting.

## Privacy and limitations

Never ingest private conversations without consent and de-identification. The synthetic data is clean and narrow. MASSIVE is task-oriented assistant language and cannot substitute for natural task-management messages.

## Attribution

MASSIVE 1.1, AmazonScience, licensed under Creative Commons Attribution 4.0: https://huggingface.co/datasets/AmazonScience/massive
