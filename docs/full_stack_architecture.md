# Full-stack architecture

## Runtime flow

```text
React/Vite RTL client
        |
        | JSON over /api
        v
FastAPI + Pydantic validation
        |
        +--> existing ActionIntelligencePipeline
        |      +--> Arabic normalization/extraction
        |      +--> local TF-IDF + Logistic Regression checkpoint
        |      +--> conservative context suggestions
        |
        +--> SQLAlchemy unit of work
               +--> SQLite (default, preserves data/fil_ai.db)
               +--> PostgreSQL (Alembic-managed option)
```

No browser-side prediction logic or mock production data is used. The API reports the exact loaded checkpoint. CAMeLBERT is shown as unavailable unless `IntentModel` successfully opens a valid local fine-tuned directory.

## Relational model

```text
conversations 1---* messages 1---* model_predictions 1---* user_corrections
      |                 |                                      |
      |                 +--- optional source of task            +--- review queue only
      +---* tasks 1---* task_events
```

- `messages`: immutable message text, source, timestamps, optional conversation.
- `model_predictions`: model version, intent, confidence, complete JSON analysis.
- `tasks`: only human-confirmed work items, status, priority, deadline.
- `task_events`: append-only before/after evidence for confirmed changes.
- `user_corrections`: reviewed training candidates; never online training input.
- `conversations`: grouping for related message analysis and tasks.

Foreign keys, status/priority checks, time and lookup indexes, and cascade behavior are defined in both SQLAlchemy and the initial PostgreSQL migration.

## SQLite compatibility

On startup, FI'L AI creates a missing schema or performs a small additive compatibility upgrade to the existing SQLite file. It adds only missing tables, columns, and indexes. Existing rows are not deleted or rewritten, except filling a newly added `updated_at` value from the row's original `created_at`.

## PostgreSQL migration safety

1. Keep `data/fil_ai.db` as the source-of-record backup.
2. Run Alembic against an empty PostgreSQL database.
3. Run `backend/scripts/migrate_sqlite_to_postgres.py`.
4. The copier inserts in foreign-key order with `ON CONFLICT DO NOTHING` and never deletes or modifies SQLite.
5. Compare row counts before switching `FIL_AI_DATABASE_URL`.

The migration is optional. SQLite remains suitable for a single-user capstone demo.

## Security and privacy boundary

Credentials are environment variables and `.env` is ignored. The repository does not upload messages, download inference models, or call a paid API at runtime. CORS defaults to local Vite addresses. This is a capstone prototype, so authentication and role-based access remain production gaps.
