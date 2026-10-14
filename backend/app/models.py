"""SQLAlchemy relational model for SQLite and PostgreSQL."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str | None] = mapped_column(String(250))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, server_default=func.now(), onupdate=utc_now, nullable=False)

    messages: Mapped[list["Message"]] = relationship(back_populates="conversation")
    tasks: Mapped[list["Task"]] = relationship(back_populates="conversation")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int | None] = mapped_column(ForeignKey("conversations.id", ondelete="SET NULL"), index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False, default="local", server_default="local")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, server_default=func.now(), onupdate=utc_now, nullable=False)

    conversation: Mapped[Conversation | None] = relationship(back_populates="messages")
    predictions: Mapped[list["ModelPrediction"]] = relationship(back_populates="message", cascade="all, delete-orphan")


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("status IN ('pending','completed','canceled')", name="ck_tasks_status"),
        CheckConstraint("priority IN ('low','medium','high','urgent')", name="ck_tasks_priority"),
        Index("ix_tasks_status_deadline", "status", "deadline"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int | None] = mapped_column(ForeignKey("conversations.id", ondelete="SET NULL"), index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="pending", server_default="pending", nullable=False)
    workflow_status: Mapped[str] = mapped_column(String(30), default="pending", server_default="pending", nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default="medium", server_default="medium", nullable=False)
    deadline: Mapped[str | None] = mapped_column(String(100))
    original_deadline: Mapped[str | None] = mapped_column(String(100))
    original_message_id: Mapped[int | None] = mapped_column(ForeignKey("messages.id", ondelete="SET NULL"), index=True)
    model_version: Mapped[str | None] = mapped_column(String(150))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, server_default=func.now(), onupdate=utc_now, nullable=False)

    conversation: Mapped[Conversation | None] = relationship(back_populates="tasks")
    events: Mapped[list["TaskEvent"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    original_message: Mapped["Message | None"] = relationship(foreign_keys=[original_message_id])
    suggestions: Mapped[list["TaskSuggestion"]] = relationship(back_populates="task")


class TaskEvent(Base):
    __tablename__ = "task_events"
    __table_args__ = (Index("ix_task_events_task_created", "task_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    evidence: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    related_message_id: Mapped[int | None] = mapped_column(ForeignKey("messages.id", ondelete="SET NULL"), index=True)
    model_prediction_id: Mapped[int | None] = mapped_column(ForeignKey("model_predictions.id", ondelete="SET NULL"), index=True)
    confirmed: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    task: Mapped[Task] = relationship(back_populates="events")
    related_message: Mapped["Message | None"] = relationship(foreign_keys=[related_message_id])
    model_prediction: Mapped["ModelPrediction | None"] = relationship(foreign_keys=[model_prediction_id])


class ModelPrediction(Base):
    __tablename__ = "model_predictions"
    __table_args__ = (Index("ix_predictions_model_intent", "model_version", "intent"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True)
    model_version: Mapped[str] = mapped_column(String(150), nullable=False)
    intent: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    confidence: Mapped[float | None] = mapped_column(Float)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    message: Mapped[Message] = relationship(back_populates="predictions")
    corrections: Mapped[list["UserCorrection"]] = relationship(back_populates="prediction")


class TaskSuggestion(Base):
    __tablename__ = "task_suggestions"
    __table_args__ = (
        CheckConstraint(
            "suggestion_type IN ('new_task','reschedule','cancellation')",
            name="ck_task_suggestions_type",
        ),
        CheckConstraint(
            "review_status IN ('pending','confirmed','rejected')",
            name="ck_task_suggestions_review_status",
        ),
        Index("ix_task_suggestions_status_created", "review_status", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True)
    prediction_id: Mapped[int] = mapped_column(ForeignKey("model_predictions.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"), index=True)
    suggestion_type: Mapped[str] = mapped_column(String(40), nullable=False)
    suggested_title: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    current_deadline: Mapped[str | None] = mapped_column(String(100))
    proposed_deadline: Mapped[str | None] = mapped_column(String(100))
    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    review_status: Mapped[str] = mapped_column(String(30), default="pending", server_default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    task: Mapped[Task | None] = relationship(back_populates="suggestions")
    message: Mapped[Message] = relationship(foreign_keys=[message_id])
    prediction: Mapped[ModelPrediction] = relationship(foreign_keys=[prediction_id])


class UserCorrection(Base):
    __tablename__ = "user_corrections"
    __table_args__ = (Index("ix_corrections_review_status", "review_status", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prediction_id: Mapped[int | None] = mapped_column(ForeignKey("model_predictions.id", ondelete="SET NULL"), index=True)
    message_id: Mapped[int | None] = mapped_column(ForeignKey("messages.id", ondelete="SET NULL"), index=True)
    corrected_intent: Mapped[str | None] = mapped_column(String(40))
    corrected_payload_json: Mapped[str | None] = mapped_column(Text)
    reviewer: Mapped[str | None] = mapped_column(String(120))
    review_status: Mapped[str] = mapped_column(String(40), nullable=False, default="reviewed_candidate", server_default="reviewed_candidate")
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    prediction: Mapped[ModelPrediction | None] = relationship(back_populates="corrections")
