# MASSIVE ar-SA Suitability for FI'L AI

## Decision

Amazon MASSIVE is **not directly compatible** with FI'L AI's four workplace-action intents. It contains localized, single-shot virtual-assistant commands with 60 original intents across 18 scenarios—not real workplace conversations. No MASSIVE row is admitted to FI'L AI supervised training until a human verifies the target label.

## Verified local data

- Official dataset/config: `AmazonScience/massive`, `ar-SA`
- License: CC BY 4.0; attribution is required.
- Train: 11,514; validation/dev: 2,033; test: 2,974; total: 16,521.
- Original schema includes `id`, `locale`, `partition`, `scenario`, `intent`, `utt`, `annot_utt`, `worker_id`, `slot_method`, and `judgments`.
- 60 intents, 18 scenarios, no missing values in the downloaded schema.
- 3,180 utterances contain explicit `[date : ...]` or `[time : ...]` annotations.
- Normalized text audit: 537 duplicate groups involving 1,545 rows. Official splits are preserved for MASSIVE-specific work; duplicates must be grouped if constructing a derived in-domain split.

## What is useful

### Directly useful without FI'L AI relabeling

- Saudi Arabic utterance text for language/normalization inspection.
- `annot_utt` spans for date/time and other slot-extraction research.
- Original quality judgments and localization metadata.
- MASSIVE-specific intent/slot experiments using the official objective and official splits.

### Indirectly useful candidates

The local review queue contains 5,672 rows selected from calendar, alarm, datetime, lists, and email-related scenarios/intents. Examples such as `calendar_set`, `calendar_remove`, `alarm_set`, and `email_sendemail` may express creation or cancellation, but their virtual-assistant semantics do not automatically establish a workplace task. `calendar_query` and `datetime_query` are especially poor candidates for `info_only` because they are user questions, not informational statements.

### Not defensible as automatic mappings

- `alarm_set` → `new_task`: an alarm command is not necessarily a workplace task.
- `calendar_remove` → `cancellation`: superficially plausible, but the target taxonomy depends on task history and communicative context.
- `calendar_query` → `info_only`: a query is an action request.
- Any bulk mapping by intent-name string alone.

## Review artifacts

- `data/processed/massive_relevant_candidates.csv` preserves the original utterance, scenario, intent, and split. Every row is `manual_review_required` / `unreviewed`.
- `data/annotation/annotation_template.csv` contains the required FI'L AI fields, but target labels are blank.
- `data/annotation/review_queue.csv` prioritizes 500 candidates for human review; it remains entirely unverified.
- `data/annotation/labeling_guidelines.md` defines human review and ambiguity handling.

## Recommended use

Use MASSIVE now for temporal-span analysis and to seed a human review queue. Build the primary four-class dataset from consented, de-identified task-management messages plus reviewed candidates. Keep source provenance and human-verification state as first-class columns. The current lack of verified in-domain labels blocks a scientifically reliable Transformer fine-tuning experiment.
