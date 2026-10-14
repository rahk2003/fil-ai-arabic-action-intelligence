"""Pydantic request and response contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Intent = Literal["new_task", "reschedule", "cancellation", "info_only"]
ModelChoice = Literal["baseline", "camelbert"]
Priority = Literal["low", "medium", "high", "urgent"]
TaskStatus = Literal["pending", "completed", "canceled"]


class AnalyzeRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10000)
    model: ModelChoice = "baseline"
    reference_time: datetime | None = None
    conversation_id: int | None = Field(default=None, ge=1)
    source: str = Field(default="api", max_length=80)


class AnalyzeResponse(BaseModel):
    message_id: int
    prediction_id: int
    suggestion_id: int | None = None
    analysis: dict[str, Any]


class CompareAnalyzeRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10000)
    reference_time: datetime | None = None
    conversation_id: int | None = Field(default=None, ge=1)
    source: str = Field(default="api_compare", max_length=80)


class CompareAnalyzeResponse(BaseModel):
    message_id: int
    results: dict[ModelChoice, AnalyzeResponse]
    same_message: bool = True


class ConversationAnalyzeRequest(BaseModel):
    messages: list[str] = Field(min_length=1, max_length=100)
    conversation_id: int | None = Field(default=None, ge=1)
    title: str | None = Field(default=None, max_length=250)
    reference_time: datetime | None = None
    model: ModelChoice = "baseline"

    @model_validator(mode="after")
    def validate_messages(self):
        cleaned = [message.strip() for message in self.messages if message.strip()]
        if not cleaned:
            raise ValueError("At least one non-empty message is required")
        self.messages = cleaned
        return self


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=2000)
    description: str | None = Field(default=None, max_length=5000)
    deadline: str | None = Field(default=None, max_length=100)
    priority: Priority = "medium"
    conversation_id: int | None = Field(default=None, ge=1)
    original_message: str | None = Field(default=None, max_length=10000)
    model_version: str = Field(default="manual", max_length=150)
    confirmed: bool


class TaskImportUpload(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_base64: str = Field(min_length=1)
    column_mapping: dict[str, str] | None = None


class TaskImportRow(BaseModel):
    row_number: int = Field(ge=2)
    title: str = Field(min_length=1, max_length=2000)
    description: str | None = Field(default=None, max_length=5000)
    deadline: str | None = Field(default=None, max_length=100)
    priority: Priority = "medium"
    status: Literal["pending", "in_progress", "completed", "canceled"] = "pending"
    notes: str | None = Field(default=None, max_length=5000)


class TaskImportCommit(BaseModel):
    rows: list[TaskImportRow] = Field(min_length=1, max_length=500)
    confirmed: bool


class TaskUpdate(BaseModel):
    event_type: Literal["started", "rescheduled", "canceled", "completed", "reopened", "edited"]
    title: str | None = Field(default=None, min_length=1, max_length=2000)
    description: str | None = Field(default=None, max_length=5000)
    deadline: str | None = Field(default=None, max_length=100)
    priority: Priority | None = None
    evidence: str | None = Field(default=None, max_length=10000)
    reason: str | None = Field(default=None, max_length=2000)
    confirmed: bool


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int | None
    title: str
    description: str | None
    status: TaskStatus
    workflow_status: Literal["pending", "in_progress", "completed", "rescheduled", "canceled"]
    priority: Priority
    deadline: str | None
    original_deadline: str | None
    original_message_id: int | None
    original_message: str | None = None
    source: str | None = None
    received_at: datetime | None = None
    last_change_summary: str | None = None
    overdue: bool = False
    model_version: str | None
    created_at: datetime
    updated_at: datetime


class TaskEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    event_type: str
    old_value: str | None
    new_value: str | None
    evidence: str | None
    summary: str | None
    related_message_id: int | None
    related_message: str | None = None
    model_prediction_id: int | None
    model_intent: str | None = None
    model_identifier: str | None = None
    confirmed: int
    created_at: datetime


class FeedbackCreate(BaseModel):
    prediction_id: int | None = Field(default=None, ge=1)
    message_id: int | None = Field(default=None, ge=1)
    corrected_intent: Intent | None = None
    corrected_payload: dict[str, Any] | None = None
    reviewer: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=5000)
    confirmed: bool

    @model_validator(mode="after")
    def require_reference(self):
        if self.prediction_id is None and self.message_id is None:
            raise ValueError("prediction_id or message_id is required")
        if self.corrected_intent is None and self.corrected_payload is None:
            raise ValueError("A corrected intent or corrected payload is required")
        return self


class FeedbackResponse(BaseModel):
    id: int
    review_status: str
    online_retraining: bool = False


class TaskSuggestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    message_id: int
    prediction_id: int
    task_id: int | None
    suggestion_type: Literal["new_task", "reschedule", "cancellation"]
    suggested_title: str | None
    description: str | None
    current_deadline: str | None
    proposed_deadline: str | None
    evidence: str
    reason: str | None
    review_status: Literal["pending", "confirmed", "rejected"]
    model_identifier: str | None = None
    predicted_intent: Intent | None = None
    uncalibrated_score: float | None = None
    created_at: datetime
    resolved_at: datetime | None


class SuggestionDecision(BaseModel):
    confirmed: bool
    task_id: int | None = Field(default=None, ge=1)
    title: str | None = Field(default=None, max_length=2000)
    description: str | None = Field(default=None, max_length=5000)
    deadline: str | None = Field(default=None, max_length=100)
    priority: Priority = "medium"
    reason: str | None = Field(default=None, max_length=2000)


class TaskDetailResponse(TaskResponse):
    history: list[TaskEventResponse]


class CalendarEventResponse(BaseModel):
    id: str
    task_id: int | None = None
    suggestion_id: int | None = None
    kind: Literal["current", "historical", "pending"]
    color: Literal["red", "green", "purple", "yellow", "gray"]
    label: str
    title: str
    starts_at: str
    recorded_at: datetime | None = None
    task_status: str
    is_current: bool
    source_message: str | None = None


class CalendarResponse(BaseModel):
    timezone: str = "Asia/Riyadh"
    range_start: datetime
    range_end: datetime
    events: list[CalendarEventResponse]
    unscheduled_tasks: list[TaskResponse]
    pending_unscheduled: list[TaskSuggestionResponse]


class ComparisonExample(BaseModel):
    message: str
    expected_label: Intent
    baseline_prediction: Intent
    baseline_score: float
    baseline_latency_ms: float
    baseline_correct: bool
    camelbert_prediction: Intent
    camelbert_score: float
    camelbert_latency_ms: float
    camelbert_correct: bool
    reference_status: str


class ModelComparisonEvidenceResponse(BaseModel):
    examples: list[ComparisonExample]
    metrics: dict[str, Any]
    confusion_matrices: dict[str, dict[str, dict[str, int]]]
    methodology: dict[str, Any]
