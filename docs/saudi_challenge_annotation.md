# Saudi Arabic challenge-set annotation

`data/evaluation/saudi_challenge_set.csv` is a small **synthetic demo challenge set**, not a real-world test set. It is used to review natural Saudi phrasing, extraction behavior, and ambiguity before collecting consented messages.

## Decision rules

- `new_task`: an actionable request is introduced and no earlier deadline is replaced.
- `reschedule`: an existing event/task is moved; the message must contain a change cue, an old/new contrast, or sufficient conversation context.
- `cancellation`: an existing task/event is withdrawn. Negated reminders such as `لا تنسين` remain new tasks.
- `info_only`: approval, completion, location, attendance, or schedule information that does not itself request or confirm a database change.
- `needs_context`: do not calculate correctness or use the row for training until the referenced task/event is supplied and reviewed.

## Review protocol

1. Show annotators the complete conversation, not only the final message.
2. Ask two reviewers to label independently and record disagreements.
3. Copy action and time evidence exactly; leave normalized time blank when the reference date is unavailable.
4. Group paraphrases and messages from the same conversation in one split to avoid leakage.
5. Keep this challenge set outside model training. A locked, human-verified real-message test set is still required.

The current `curated_reference` labels are engineering review references for the demo. They must not be renamed `human_verified` without actual independent human review.
