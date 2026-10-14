"""FastAPI entrypoint integrating the real local FI'L AI pipeline."""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from fil_ai.inference import ModelUnavailableError  # noqa: E402
from fil_ai.pipeline import ActionIntelligencePipeline  # noqa: E402
from fil_ai.semantic import get_semantic_matcher  # noqa: E402

from .database import Database
from .models import Conversation, Task, TaskEvent
from .schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    CalendarResponse,
    CompareAnalyzeRequest,
    CompareAnalyzeResponse,
    ConversationAnalyzeRequest,
    FeedbackCreate,
    FeedbackResponse,
    ModelComparisonEvidenceResponse,
    SuggestionDecision,
    TaskCreate,
    TaskDetailResponse,
    TaskEventResponse,
    TaskImportCommit,
    TaskImportUpload,
    TaskResponse,
    TaskSuggestionResponse,
    TaskUpdate,
)
from .services import (
    analytics_payload,
    calendar_payload,
    commit_task_import,
    create_confirmed_task,
    create_feedback,
    create_task_suggestion,
    dataset_sample_payload,
    error_analysis_payload,
    confirm_task_suggestion,
    get_task_detail,
    get_or_create_conversation,
    list_tasks,
    list_task_suggestions,
    list_task_summaries,
    model_comparison_evidence_payload,
    persist_analysis,
    persist_prediction,
    preview_task_import,
    reject_task_suggestion,
    task_event_payload,
    task_import_template,
    task_suggestion_payload,
    task_summary,
    update_confirmed_task,
)
from .settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    database = Database(app_settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        database.initialize()
        app.state.database = database
        app.state.pipeline = ActionIntelligencePipeline(
            app_settings.resolved_model_path,
            app_settings.resolved_camelbert_model_path,
            transformer_device=app_settings.transformer_device,
            semantic_matcher=get_semantic_matcher(
                app_settings.embedding_model_name,
                str(app_settings.resolved_embedding_cache_dir),
                app_settings.embedding_local_files_only,
                app_settings.embedding_enabled,
            ),
            semantic_threshold=app_settings.semantic_threshold,
        )
        yield
        database.engine.dispose()

    app = FastAPI(
        title=app_settings.app_name,
        version=app_settings.app_version,
        description=(
            "Local Arabic action-intelligence API. Predictions come from a real local "
            "checkpoint; task mutations and corrections require explicit confirmation."
        ),
        lifespan=lifespan,
    )
    app.state.settings = app_settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def get_session(request: Request):
        with request.app.state.database.session() as session:
            yield session

    prefix = app_settings.api_prefix

    @app.get(f"{prefix}/health", tags=["system"])
    def health(request: Request):
        pipeline = request.app.state.pipeline
        models = pipeline.models.statuses()
        return {
            "status": "ok" if request.app.state.database.ping() else "degraded",
            "database": "sqlite" if app_settings.is_sqlite else "postgresql",
            "model": pipeline.intent_model.name,
            "model_warning": pipeline.intent_model.warning,
            "models": models,
            "embeddings": pipeline.semantic_matcher.status() if pipeline.semantic_matcher else None,
            "version": app_settings.app_version,
        }

    @app.post(f"{prefix}/analyze", response_model=AnalyzeResponse, tags=["ai"])
    def analyze(payload: AnalyzeRequest, request: Request, session: Session = Depends(get_session)):
        if payload.conversation_id is not None and session.get(Conversation, payload.conversation_id) is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        task_context = [
            {"id": task.id, "title": task.title, "original_message": task.title}
            for task in list_tasks(session, "pending")
        ]
        try:
            analysis_result = request.app.state.pipeline.analyze(
                payload.message,
                model=payload.model,
                reference_time=payload.reference_time,
                previous_tasks=task_context,
            )
        except ModelUnavailableError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        message, prediction = persist_analysis(
            session,
            payload.message,
            analysis_result,
            conversation_id=payload.conversation_id,
            source=payload.source,
        )
        suggestion = create_task_suggestion(
            session, message, prediction, analysis_result
        )
        return AnalyzeResponse(
            message_id=message.id,
            prediction_id=prediction.id,
            suggestion_id=suggestion.id if suggestion else None,
            analysis=analysis_result,
        )

    @app.post(
        f"{prefix}/analyze/compare",
        response_model=CompareAnalyzeResponse,
        tags=["ai"],
    )
    def compare_models(
        payload: CompareAnalyzeRequest,
        request: Request,
        session: Session = Depends(get_session),
    ):
        if payload.conversation_id is not None and session.get(Conversation, payload.conversation_id) is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        task_context = [
            {"id": task.id, "title": task.title, "original_message": task.title}
            for task in list_tasks(session, "pending")
        ]
        try:
            analyses = {
                model: request.app.state.pipeline.analyze(
                    payload.message,
                    model=model,
                    reference_time=payload.reference_time,
                    previous_tasks=task_context,
                )
                for model in ("baseline", "camelbert")
            }
        except ModelUnavailableError as error:
            # The request explicitly asked for both models. Returning a partial
            # comparison would be a silent substitution/omission, so fail closed.
            raise HTTPException(status_code=503, detail=str(error)) from error

        message, baseline_prediction = persist_analysis(
            session,
            payload.message,
            analyses["baseline"],
            conversation_id=payload.conversation_id,
            source=payload.source,
        )
        camelbert_prediction = persist_prediction(
            session,
            message.id,
            analyses["camelbert"],
        )
        return CompareAnalyzeResponse(
            message_id=message.id,
            results={
                "baseline": AnalyzeResponse(
                    message_id=message.id,
                    prediction_id=baseline_prediction.id,
                    analysis=analyses["baseline"],
                ),
                "camelbert": AnalyzeResponse(
                    message_id=message.id,
                    prediction_id=camelbert_prediction.id,
                    analysis=analyses["camelbert"],
                ),
            },
        )

    @app.post(f"{prefix}/conversations/analyze", tags=["ai", "conversations"])
    def analyze_conversation(
        payload: ConversationAnalyzeRequest,
        request: Request,
        session: Session = Depends(get_session),
    ):
        conversation = get_or_create_conversation(session, payload.conversation_id, payload.title)
        try:
            # Validate/load once before persisting any message in the batch.
            request.app.state.pipeline.models.get(payload.model).ensure_loaded()
        except ModelUnavailableError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        previous_tasks = [
            {"id": task.id, "title": task.title, "original_message": task.title}
            for task in list_tasks(session, "pending")
        ]
        analyses = []
        immediately_previous_message: str | None = None
        for sequence, message_text in enumerate(payload.messages, start=1):
            for candidate in previous_tasks:
                candidate["is_recent"] = False
            if previous_tasks and immediately_previous_message:
                previous_tasks[-1]["is_recent"] = True
            result = request.app.state.pipeline.analyze(
                message_text,
                model=payload.model,
                reference_time=payload.reference_time,
                previous_tasks=previous_tasks,
            )
            message, prediction = persist_analysis(
                session,
                message_text,
                result,
                conversation_id=conversation.id,
                source="conversation_api",
            )
            suggestion = create_task_suggestion(session, message, prediction, result)
            interpretation = result.get("interpretation") or {}
            top_candidate = (result.get("context", {}).get("candidates") or [None])[0]
            # Short Arabic follow-ups often omit the task noun entirely (for example,
            # "خلاص خلوه الخميس").  Keep this as an explicit, unexecuted suggestion
            # instead of silently mutating a task or pretending the classifier resolved it.
            if (
                top_candidate is None
                and immediately_previous_message
                and interpretation.get("action_type") in {
                    "update_task_scope", "update_task_requirement", "update_task_priority",
                    "reschedule_task", "cancel_task", "mark_complete", "needs_clarification",
                }
            ):
                top_candidate = {
                    "task_text": immediately_previous_message,
                    "score": None,
                    "basis": "immediate_preceding_message",
                }
            change = None
            if top_candidate and interpretation.get("action_type") not in {"create_task", "no_action"}:
                change = {
                    "before": top_candidate["task_text"],
                    "after": interpretation.get("proposed_change") or message_text,
                    "change_type": interpretation.get("action_type"),
                    "related_task_id": top_candidate.get("task_id"),
                    "missing_details": interpretation.get("missing_details") or [],
                    "suggestion": result["context"]["suggestion"],
                    "requires_confirmation": interpretation.get("requires_confirmation", False),
                }
            analyses.append(
                {
                    "sequence": sequence,
                    "message_id": message.id,
                    "prediction_id": prediction.id,
                    "suggestion_id": suggestion.id if suggestion else None,
                    "analysis": result,
                    "before_after": change,
                }
            )
            if interpretation.get("action_type") == "create_task":
                previous_tasks.append(
                    {
                        "id": f"conversation-{sequence}",
                        "title": interpretation.get("proposed_change") or message_text,
                        "original_message": message_text,
                        "is_recent": True,
                    }
                )
            immediately_previous_message = message_text
        return {
            "conversation_id": conversation.id,
            "analyses": analyses,
            "automatic_task_mutations": False,
        }

    @app.get(f"{prefix}/tasks", response_model=list[TaskResponse], tags=["tasks"])
    def get_tasks(
        task_status: str | None = Query(default=None, alias="status", pattern="^(pending|completed|canceled)$"),
        session: Session = Depends(get_session),
    ):
        return list_task_summaries(session, task_status)

    @app.get(
        f"{prefix}/calendar",
        response_model=CalendarResponse,
        tags=["tasks", "calendar"],
    )
    def get_calendar(
        start: datetime = Query(..., description="Inclusive calendar range start"),
        end: datetime = Query(..., description="Exclusive calendar range end"),
        include_history: bool = Query(default=True),
        session: Session = Depends(get_session),
    ):
        return calendar_payload(
            session,
            start,
            end,
            include_history=include_history,
        )

    @app.post(f"{prefix}/tasks", response_model=TaskResponse, status_code=201, tags=["tasks"])
    def post_task(payload: TaskCreate, session: Session = Depends(get_session)):
        return task_summary(session, create_confirmed_task(session, payload))

    @app.post(f"{prefix}/tasks/import/preview", tags=["tasks", "import"])
    def preview_tasks_import(payload: TaskImportUpload, session: Session = Depends(get_session)):
        return preview_task_import(session, payload)

    @app.post(f"{prefix}/tasks/import/commit", tags=["tasks", "import"])
    def commit_tasks_import(payload: TaskImportCommit, session: Session = Depends(get_session)):
        return commit_task_import(session, payload)

    @app.get(f"{prefix}/tasks/import/template", tags=["tasks", "import"])
    def get_tasks_import_template(file_format: str = Query(default="csv", alias="format", pattern="^(csv|xlsx)$")):
        return task_import_template(file_format)

    @app.patch(f"{prefix}/tasks/{{task_id}}", response_model=TaskResponse, tags=["tasks"])
    def patch_task(task_id: int, payload: TaskUpdate, session: Session = Depends(get_session)):
        return task_summary(session, update_confirmed_task(session, task_id, payload))

    @app.get(f"{prefix}/tasks/{{task_id}}", response_model=TaskDetailResponse, tags=["tasks"])
    def get_task(task_id: int, session: Session = Depends(get_session)):
        return get_task_detail(session, task_id)

    @app.get(
        f"{prefix}/tasks/{{task_id}}/history",
        response_model=list[TaskEventResponse],
        tags=["tasks"],
    )
    def get_task_history(task_id: int, session: Session = Depends(get_session)):
        if session.get(Task, task_id) is None:
            raise HTTPException(status_code=404, detail="Task not found")
        events = list(
            session.scalars(
                select(TaskEvent)
                .where(TaskEvent.task_id == task_id)
                .order_by(TaskEvent.created_at, TaskEvent.id)
            )
        )
        return [task_event_payload(session, event) for event in events]

    @app.get(
        f"{prefix}/task-suggestions",
        response_model=list[TaskSuggestionResponse],
        tags=["tasks", "ai"],
    )
    def get_task_suggestions(
        review_status: str = Query(default="pending", alias="status", pattern="^(pending|confirmed|rejected)$"),
        session: Session = Depends(get_session),
    ):
        return list_task_suggestions(session, review_status)

    @app.post(
        f"{prefix}/task-suggestions/{{suggestion_id}}/confirm",
        response_model=TaskResponse,
        tags=["tasks", "ai"],
    )
    def confirm_suggestion(
        suggestion_id: int,
        payload: SuggestionDecision,
        session: Session = Depends(get_session),
    ):
        task = confirm_task_suggestion(session, suggestion_id, payload)
        return task_summary(session, task)

    @app.post(
        f"{prefix}/task-suggestions/{{suggestion_id}}/reject",
        response_model=TaskSuggestionResponse,
        tags=["tasks", "ai"],
    )
    def reject_suggestion(
        suggestion_id: int,
        payload: SuggestionDecision,
        session: Session = Depends(get_session),
    ):
        suggestion = reject_task_suggestion(session, suggestion_id, payload)
        return task_suggestion_payload(session, suggestion)

    @app.post(f"{prefix}/feedback", response_model=FeedbackResponse, status_code=201, tags=["feedback"])
    def post_feedback(payload: FeedbackCreate, session: Session = Depends(get_session)):
        correction = create_feedback(session, payload)
        return FeedbackResponse(id=correction.id, review_status=correction.review_status)

    @app.get(f"{prefix}/analytics", tags=["analytics"])
    def analytics(request: Request, session: Session = Depends(get_session)):
        return analytics_payload(request.app.state.pipeline.models.statuses(), session)

    @app.get(f"{prefix}/datasets/samples", tags=["analytics", "datasets"])
    def dataset_samples(
        dataset: str = Query(..., pattern="^(baseline_96|massive_ar_sa|saudi_challenge)$"),
        query: str = Query(default="", max_length=200),
        limit: int = Query(default=25, ge=1, le=100),
    ):
        return dataset_sample_payload(dataset, query, limit)

    @app.get(
        f"{prefix}/evaluation/model-comparison",
        response_model=ModelComparisonEvidenceResponse,
        tags=["analytics", "ai"],
    )
    def model_comparison_evidence(
        limit: int = Query(default=10, ge=1, le=10),
    ):
        return model_comparison_evidence_payload(limit)

    @app.get(f"{prefix}/evaluation/errors", tags=["analytics", "ai"])
    def evaluation_errors():
        return error_analysis_payload()

    return app


app = create_app()
