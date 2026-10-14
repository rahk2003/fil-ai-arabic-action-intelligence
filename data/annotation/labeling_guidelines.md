# FI'L AI Annotation Guidelines

## Unit and prerequisite

Label one complete message with enough preceding context to resolve references. Remove personal information before annotation. If context is missing, mark the row `needs_context` rather than guessing. `label_status=human_verified` is required for supervised training; automatic candidates remain `unreviewed` or `suggested`.

## Primary-intent labels

- `new_task`: asks someone to perform a new action. A deadline alone does not make it a reschedule. Example criterion: no earlier task/time is being replaced.
- `reschedule`: changes the date/time of an existing task, event, or deadline. Evidence should include the referenced item plus an old/change cue or conversational antecedent.
- `cancellation`: withdraws or stops an existing task/event. Negated new requests such as “لا تنسى” are not cancellations.
- `info_only`: communicates a fact/status without requesting, changing, or canceling an action.

## Difficult decisions

1. **Task plus deadline:** `مطلوب التسليم الأربعاء` → `new_task`, unless context shows Wednesday replaces an older deadline.
2. **Time in a fact:** `الدورات تبدأ بعد الخامسة` → `info_only`.
3. **Negation scope:** `ما يحتاج ترفعينه` → `cancellation`; `لا تنسين ترفعينه` → `new_task`.
4. **Multiple actions:** choose the dominant change as primary intent, but annotate every action in structured fields/notes. Never discard the second action.
5. **Ambiguous reference:** leave target intent blank, use `label_status=needs_context`, and explain in `notes`.
6. **MASSIVE:** preserve its `scenario`, `intent`, and split in notes/provenance. Do not copy an original virtual-assistant label into a FI'L AI label without reading the utterance and applying these rules.

## Extraction fields

- `action_text` and `datetime_text` must be exact evidence spans copied from the message.
- `normalized_datetime` must include timezone (`Asia/Riyadh`) and must be blank if message creation time or necessary context is unavailable.
- `reviewer` identifies the human reviewer; do not put personal message-owner information here.

## Review workflow

Two people independently label an initial calibration set. Resolve disagreements, revise the guide, then measure agreement. Deduplicate before splitting and group paraphrase families/conversations in one split. A reviewed, locked real-message test set must never be used for model selection.
