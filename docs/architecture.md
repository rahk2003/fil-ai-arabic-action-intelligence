# FI'L AI Architecture

```text
React RTL client or preserved Gradio demo
            |
            v
FastAPI + Pydantic REST boundary
            |
            v
Arabic message + creation time
            |
            v
  Arabic normalization -------- provenance / original text
            |
            +--> intent model (active: preserved TF-IDF baseline)
            |
            +--> rule-based action + temporal extraction
            |
            +--> cached MiniLM embeddings + lexical/entity/recency ranking
            |
            v
 structured analysis + evidence + uncertainty
            |
      explicit user confirmation
            |
            v
 SQLAlchemy persistence + immutable task-event history
            |
            +--> existing SQLite (default)
            +--> PostgreSQL via Alembic (optional)
```

Both the TF-IDF baseline and a locally fine-tuned CAMeLBERT-DA classifier are available through an explicit model registry. CAMeLBERT is lazy-loaded and cached; an explicit request is never silently replaced. Date/action extraction is transparent rule logic, not NER. Context matching uses cached `paraphrase-multilingual-MiniLM-L12-v2` embeddings together with normalized lexical overlap, shared terms, and immediate-message recency. A failed embedding load activates a named lexical fallback. Similarity is never treated as proof and every mutation still requires confirmation. SQLite and confirmation checks are application logic.

`src/fil_ai/` separates normalization, inference, extraction, matching, orchestration, and storage. `backend/` exposes the same real pipeline through FastAPI and maps confirmed state to SQLAlchemy. `frontend/` is an Arabic-first React/TypeScript client with no browser-side model or mock production data. `scripts/` contains reproducible data/evaluation/training commands. `app.py` remains the local Gradio backup. See `full_stack_architecture.md` for database relationships and migration safety.
