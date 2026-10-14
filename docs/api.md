# FI'L AI REST API

FastAPI serves interactive OpenAPI documentation at `http://127.0.0.1:8000/docs` and the raw schema at `/openapi.json`. All examples below use the real locally loaded classifier. Predictions are persisted, but task changes require `confirmed: true`.

## Run

```bash
source .venv312/bin/activate
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

## Endpoints

### `GET /api/health`

Returns database type, default model, API version, and status for both local models. CAMeLBERT status includes `available`, `loaded`, device, and verified labels without forcing a weight load.

### `POST /api/analyze`

```bash
curl -s http://127.0.0.1:8000/api/analyze \
  -H 'Content-Type: application/json' \
  -d '{"message":"ارسلي التقرير بكرة الساعة ٩ الصباح","model":"camelbert","reference_time":"2026-10-14T12:00:00+03:00"}'
```

`model` is `baseline` (default) or `camelbert`. The response includes IDs, predicted label, uncalibrated score, exact model identifier, model-only inference latency, probabilities, extraction evidence, normalized time, warnings, context candidates, and `automatic_execution: false`.

### `POST /api/analyze/compare`

Accepts the same message/reference fields without a model. It runs both local models on the exact same string and returns `results.baseline` and `results.camelbert`. One message row and two linked prediction rows are persisted. If either requested model fails, the endpoint returns HTTP 503 rather than a partial or substituted comparison.

### `POST /api/conversations/analyze`

```json
{
  "title": "اجتماع الفريق",
  "reference_time": "2026-10-14T12:00:00+03:00",
  "messages": [
    "اجتماعنا يوم الأحد الساعة 10 الصباح",
    "خلاص خلوه الخميس الساعة 12 الظهر"
  ]
}
```

Returns each message analysis plus a review-only before/after suggestion when context can be linked. It never mutates tasks automatically.

Each analysis reports `context.matching_method` as `embeddings`, `lexical_fallback`, or `no_candidates`, plus the exact embedding status. Embedding cosine is combined with lexical/shared-term/recency evidence and never commits a change by itself.

### `GET /api/tasks`

Optional `status=pending|completed|canceled`. Returns confirmed tasks from the configured database with description, original/current deadlines, workflow status, original message/source, received time, latest change summary, and overdue flag.

### `GET /api/calendar`

Returns Gregorian `Asia/Riyadh` markers. Historical reschedule deadlines are red, the current updated deadline is green, normal active tasks are purple, pending suggestions are yellow, and canceled tasks are gray. Old/current markers retain one `task_id`.

### `POST /api/tasks/import/preview` and `/commit`

Accept base64 CSV/XLSX data up to 2 MB and 500 rows. Preview performs Arabic/English column detection, date/priority/status validation, and duplicate detection. Commit requires `confirmed: true` and rechecks duplicates. `GET /api/tasks/import/template?format=csv|xlsx` returns downloadable empty templates.

### `GET /api/tasks/{id}`

Returns one task plus its chronological history. Each history entry can include the affecting message, before/after values, Arabic summary, model intent/identifier, and source evidence.

### `GET /api/task-suggestions`

Returns persisted unconfirmed suggestions. Use `status=pending|confirmed|rejected`. Informational predictions do not create suggestions.

### `POST /api/task-suggestions/{id}/confirm`

Requires `confirmed: true`. A `new_task` suggestion creates a task. A `reschedule` or `cancellation` suggestion updates the selected existing task, preserves original values, and appends a message-linked history event. If a reschedule has no supported date/time, the API returns HTTP 409 until the reviewer enters a deadline; it never invents one.

### `POST /api/task-suggestions/{id}/reject`

Requires `confirmed: true` and marks the suggestion rejected without mutating tasks.

### `POST /api/tasks`

```json
{
  "title": "إرسال التقرير",
  "deadline": "2026-10-15T09:00:00+03:00",
  "priority": "high",
  "original_message": "ارسلي التقرير بكرة الساعة ٩",
  "model_version": "intent_baseline",
  "confirmed": true
}
```

Unconfirmed writes return HTTP 409. A successful write also creates a confirmed `task_events` history record.

### `PATCH /api/tasks/{id}`

`event_type` is one of `rescheduled`, `canceled`, `completed`, `reopened`, or `edited`. Send `confirmed: true`; evidence is retained in the event history.

### `GET /api/tasks/{id}/history`

Returns the append-only change history for one task.

### `POST /api/feedback`

Stores a correction linked to a message or prediction. Corrections are marked `reviewed_candidate`; they do not trigger online retraining.

```json
{
  "prediction_id": 1,
  "corrected_intent": "new_task",
  "reviewer": "capstone-reviewer",
  "notes": "Reviewed against annotation guide",
  "confirmed": true
}
```

### `GET /api/analytics`

Reads the committed evaluation and dataset artifacts plus live application counts. It does not recompute or invent model metrics.

## Error behavior

- HTTP 422: schema validation failed.
- HTTP 404: referenced conversation, message, prediction, or task does not exist.
- HTTP 409: a state-changing request was not explicitly confirmed.
- HTTP 503: an explicitly requested local model is missing, invalid, or cannot be loaded. No model substitution occurs.
- HTTP 500: unexpected local model, database, or artifact failure; inspect Uvicorn logs.
