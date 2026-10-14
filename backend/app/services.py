"""Persistence and analytics services used by the API."""

from __future__ import annotations

import base64
import binascii
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    Conversation,
    Message,
    ModelPrediction,
    Task,
    TaskEvent,
    TaskSuggestion,
    UserCorrection,
)
from .schemas import (
    FeedbackCreate,
    SuggestionDecision,
    TaskCreate,
    TaskImportCommit,
    TaskImportUpload,
    TaskUpdate,
)
from .settings import PROJECT_ROOT


RIYADH_TZ = ZoneInfo("Asia/Riyadh")
IMPORT_MAX_BYTES = 2 * 1024 * 1024
IMPORT_COLUMNS = {
    "title": {"title", "task", "task name", "اسم المهمة", "المهمة", "العنوان"},
    "description": {"description", "details", "الوصف", "التفاصيل"},
    "date": {"date", "deadline date", "التاريخ", "تاريخ الموعد", "تاريخ الاستحقاق"},
    "time": {"time", "deadline time", "الوقت", "وقت الموعد"},
    "deadline": {"deadline", "due date", "الموعد", "الموعد النهائي"},
    "priority": {"priority", "الأولوية"},
    "status": {"status", "الحالة"},
    "notes": {"notes", "ملاحظات", "الملاحظات"},
}
PRIORITY_VALUES = {
    "low": "low", "منخفضة": "low", "منخفض": "low",
    "medium": "medium", "متوسطة": "medium", "متوسط": "medium",
    "high": "high", "عالية": "high", "عال": "high",
    "urgent": "urgent", "عاجلة": "urgent", "عاجل": "urgent",
}
STATUS_VALUES = {
    "pending": "pending", "قيد الانتظار": "pending",
    "in progress": "in_progress", "in_progress": "in_progress", "قيد التنفيذ": "in_progress",
    "completed": "completed", "مكتملة": "completed", "مكتمل": "completed",
    "canceled": "canceled", "cancelled": "canceled", "ملغاة": "canceled", "ملغي": "canceled",
}


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def create_conversation(session: Session, title: str | None = None) -> Conversation:
    conversation = Conversation(title=title)
    session.add(conversation)
    session.flush()
    return conversation


def get_or_create_conversation(
    session: Session, conversation_id: int | None, title: str | None = None
) -> Conversation:
    if conversation_id is not None:
        conversation = session.get(Conversation, conversation_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return conversation
    return create_conversation(session, title)


def persist_analysis(
    session: Session,
    message_text: str,
    analysis: dict[str, Any],
    *,
    conversation_id: int | None,
    source: str,
) -> tuple[Message, ModelPrediction]:
    message = Message(text=message_text, conversation_id=conversation_id, source=source)
    session.add(message)
    session.flush()
    prediction = persist_prediction(session, message.id, analysis)
    return message, prediction


def persist_prediction(
    session: Session,
    message_id: int,
    analysis: dict[str, Any],
) -> ModelPrediction:
    """Persist another model result against an existing message row."""
    prediction_data = analysis["prediction"]
    prediction = ModelPrediction(
        message_id=message_id,
        model_version=prediction_data["model_name"],
        intent=prediction_data["label"],
        confidence=prediction_data["confidence"],
        payload_json=json_text(analysis),
    )
    session.add(prediction)
    session.flush()
    return prediction


def _parse_deadline(deadline: str | None) -> datetime | None:
    if not deadline:
        return None
    try:
        parsed = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=RIYADH_TZ)
        return parsed
    except ValueError:
        return None


def normalize_deadline(deadline: str | None) -> str | None:
    parsed = _parse_deadline(deadline)
    return parsed.isoformat() if parsed else deadline


def _clean_cell(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def _resolve_import_columns(columns: list[str], custom: dict[str, str] | None) -> dict[str, str]:
    normalized = {str(column).strip().casefold(): str(column) for column in columns}
    resolved: dict[str, str] = {}
    for field, aliases in IMPORT_COLUMNS.items():
        requested = (custom or {}).get(field)
        if requested and requested in columns:
            resolved[field] = requested
            continue
        for alias in aliases:
            if alias.casefold() in normalized:
                resolved[field] = normalized[alias.casefold()]
                break
    return resolved


def _decode_import_file(payload: TaskImportUpload) -> pd.DataFrame:
    try:
        raw = base64.b64decode(payload.content_base64, validate=True)
    except (binascii.Error, ValueError) as error:
        raise HTTPException(status_code=422, detail="محتوى الملف غير صالح.") from error
    if len(raw) > IMPORT_MAX_BYTES:
        raise HTTPException(status_code=413, detail="الحد الأقصى لحجم ملف الاستيراد هو 2 MB.")
    suffix = Path(payload.filename).suffix.lower()
    try:
        if suffix == ".csv":
            try:
                return pd.read_csv(io.BytesIO(raw), encoding="utf-8-sig", dtype=str)
            except UnicodeDecodeError:
                return pd.read_csv(io.BytesIO(raw), encoding="cp1256", dtype=str)
        if suffix == ".xlsx":
            return pd.read_excel(io.BytesIO(raw), dtype=str, engine="openpyxl")
    except ImportError as error:
        raise HTTPException(status_code=503, detail="دعم XLSX غير مثبت محليًا. ثبّت متطلبات الخادم ثم أعد المحاولة.") from error
    except Exception as error:
        raise HTTPException(status_code=422, detail=f"تعذر قراءة الملف: {error}") from error
    raise HTTPException(status_code=415, detail="نوع الملف غير مدعوم. استخدم CSV أو XLSX فقط.")


def preview_task_import(session: Session, payload: TaskImportUpload) -> dict[str, Any]:
    frame = _decode_import_file(payload)
    if len(frame) > 500:
        raise HTTPException(status_code=422, detail="الحد الأقصى هو 500 صف لكل عملية استيراد.")
    columns = [str(column) for column in frame.columns]
    mapping = _resolve_import_columns(columns, payload.column_mapping)
    if "title" not in mapping:
        raise HTTPException(status_code=422, detail="تعذر تحديد عمود اسم المهمة. استخدم «اسم المهمة» أو title.")
    existing = {
        (re.sub(r"\s+", " ", task.title.strip()).casefold(), normalize_deadline(task.deadline))
        for task in list_tasks(session)
    }
    seen: set[tuple[str, str | None]] = set()
    rows: list[dict[str, Any]] = []
    for index, record in frame.fillna("").iterrows():
        title = _clean_cell(record.get(mapping["title"]))
        description = _clean_cell(record.get(mapping.get("description"))) or None
        raw_deadline = _clean_cell(record.get(mapping.get("deadline")))
        if not raw_deadline and mapping.get("date"):
            raw_deadline = _clean_cell(record.get(mapping["date"]))
            time_value = _clean_cell(record.get(mapping.get("time")))
            if raw_deadline and time_value:
                raw_deadline = f"{raw_deadline}T{time_value}"
        deadline = normalize_deadline(raw_deadline or None)
        priority_raw = _clean_cell(record.get(mapping.get("priority"))).casefold()
        status_raw = _clean_cell(record.get(mapping.get("status"))).casefold()
        priority = PRIORITY_VALUES.get(priority_raw, "medium")
        workflow_status = STATUS_VALUES.get(status_raw, "pending")
        notes = _clean_cell(record.get(mapping.get("notes"))) or None
        errors: list[str] = []
        if not title:
            errors.append("اسم المهمة مطلوب")
        if raw_deadline and _parse_deadline(raw_deadline) is None:
            errors.append("تنسيق التاريخ أو الوقت غير صالح")
        if priority_raw and priority_raw not in PRIORITY_VALUES:
            errors.append("قيمة الأولوية غير معروفة")
        if status_raw and status_raw not in STATUS_VALUES:
            errors.append("قيمة الحالة غير معروفة")
        key = (re.sub(r"\s+", " ", title).casefold(), deadline)
        duplicate = bool(title and (key in existing or key in seen))
        if duplicate:
            errors.append("مهمة مكررة بالاسم والموعد")
        seen.add(key)
        rows.append({
            "row_number": int(index) + 2,
            "title": title,
            "description": description,
            "deadline": deadline,
            "priority": priority,
            "status": workflow_status,
            "notes": notes,
            "valid": not errors,
            "duplicate": duplicate,
            "errors": errors,
        })
    return {
        "filename": payload.filename,
        "columns": columns,
        "mapping": mapping,
        "rows": rows,
        "summary": {
            "total": len(rows),
            "valid": sum(1 for row in rows if row["valid"]),
            "duplicates": sum(1 for row in rows if row["duplicate"]),
            "invalid": sum(1 for row in rows if not row["valid"] and not row["duplicate"]),
        },
    }


def commit_task_import(session: Session, payload: TaskImportCommit) -> dict[str, Any]:
    if not payload.confirmed:
        raise HTTPException(status_code=409, detail="يلزم تأكيد الاستيراد بعد مراجعة المعاينة.")
    existing = {
        (re.sub(r"\s+", " ", task.title.strip()).casefold(), normalize_deadline(task.deadline))
        for task in list_tasks(session)
    }
    imported: list[int] = []
    skipped: list[dict[str, Any]] = []
    for row in payload.rows:
        deadline = normalize_deadline(row.deadline)
        if row.deadline and _parse_deadline(row.deadline) is None:
            skipped.append({"row_number": row.row_number, "reason": "تاريخ غير صالح"})
            continue
        key = (re.sub(r"\s+", " ", row.title.strip()).casefold(), deadline)
        if key in existing:
            skipped.append({"row_number": row.row_number, "reason": "مهمة مكررة"})
            continue
        task = create_confirmed_task(session, TaskCreate(
            title=row.title,
            description=row.description,
            deadline=deadline,
            priority=row.priority,
            original_message=row.notes,
            model_version="file-import",
            confirmed=True,
        ))
        if row.status != "pending":
            event_type = {"in_progress": "started", "completed": "completed", "canceled": "canceled"}[row.status]
            update_confirmed_task(session, task.id, TaskUpdate(event_type=event_type, evidence="استيراد ملف مؤكد", confirmed=True))
        imported.append(task.id)
        existing.add(key)
    return {"imported": len(imported), "skipped": len(skipped), "failed": 0, "task_ids": imported, "skipped_rows": skipped}


def task_import_template(file_format: str) -> dict[str, str]:
    headers = ["اسم المهمة", "الوصف", "التاريخ", "الوقت", "الأولوية", "الحالة", "ملاحظات"]
    if file_format == "csv":
        raw = (",".join(headers) + "\n").encode("utf-8-sig")
        return {"filename": "fil_ai_tasks_template.csv", "content_base64": base64.b64encode(raw).decode()}
    if file_format == "xlsx":
        try:
            from openpyxl import Workbook
        except ImportError as error:
            raise HTTPException(status_code=503, detail="دعم XLSX غير مثبت محليًا.") from error
        workbook = Workbook(); sheet = workbook.active; sheet.title = "المهام"; sheet.append(headers)
        stream = io.BytesIO(); workbook.save(stream)
        return {"filename": "fil_ai_tasks_template.xlsx", "content_base64": base64.b64encode(stream.getvalue()).decode()}
    raise HTTPException(status_code=422, detail="صيغة القالب يجب أن تكون csv أو xlsx.")


def _deadline_is_overdue(deadline: str | None, workflow_status: str) -> bool:
    if workflow_status in {"completed", "canceled"}:
        return False
    parsed = _parse_deadline(deadline)
    return bool(parsed and parsed.astimezone(timezone.utc) < datetime.now(timezone.utc))


def _event_summary(event_type: str, old_value: dict[str, Any], new_value: dict[str, Any]) -> str:
    if event_type == "created":
        return "تم إنشاء المهمة بعد تأكيد المستخدم."
    if event_type == "rescheduled":
        before = old_value.get("deadline") or "موعد غير محدد"
        after = new_value.get("deadline") or "موعد غير محدد"
        return f"تم تغيير الموعد من {before} إلى {after}."
    if event_type == "started":
        return "تم نقل المهمة إلى قيد التنفيذ."
    if event_type == "completed":
        return "تم إكمال المهمة."
    if event_type == "canceled":
        return "تم إلغاء المهمة."
    if event_type == "reopened":
        return "تمت إعادة فتح المهمة."
    return "تم تعديل بيانات المهمة."


def task_summary(session: Session, task: Task) -> dict[str, Any]:
    message = session.get(Message, task.original_message_id) if task.original_message_id else None
    latest_event = session.scalar(
        select(TaskEvent)
        .where(TaskEvent.task_id == task.id)
        .order_by(TaskEvent.created_at.desc(), TaskEvent.id.desc())
        .limit(1)
    )
    return {
        "id": task.id,
        "conversation_id": task.conversation_id,
        "title": task.title,
        "description": task.description,
        "status": task.status,
        "workflow_status": task.workflow_status,
        "priority": task.priority,
        "deadline": task.deadline,
        "original_deadline": task.original_deadline,
        "original_message_id": task.original_message_id,
        "original_message": message.text if message else None,
        "source": message.source if message else "manual",
        "received_at": message.created_at if message else task.created_at,
        "last_change_summary": latest_event.summary if latest_event else None,
        "overdue": _deadline_is_overdue(task.deadline, task.workflow_status),
        "model_version": task.model_version,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }


def task_event_payload(session: Session, event: TaskEvent) -> dict[str, Any]:
    message = session.get(Message, event.related_message_id) if event.related_message_id else None
    prediction = (
        session.get(ModelPrediction, event.model_prediction_id)
        if event.model_prediction_id
        else None
    )
    return {
        "id": event.id,
        "task_id": event.task_id,
        "event_type": event.event_type,
        "old_value": event.old_value,
        "new_value": event.new_value,
        "evidence": event.evidence,
        "summary": event.summary,
        "related_message_id": event.related_message_id,
        "related_message": message.text if message else None,
        "model_prediction_id": event.model_prediction_id,
        "model_intent": prediction.intent if prediction else None,
        "model_identifier": prediction.model_version if prediction else None,
        "confirmed": event.confirmed,
        "created_at": event.created_at,
    }


def list_tasks(session: Session, task_status: str | None = None) -> list[Task]:
    query = select(Task)
    if task_status:
        query = query.where(Task.status == task_status)
    query = query.order_by(Task.status, Task.deadline.is_(None), Task.deadline, Task.id.desc())
    return list(session.scalars(query))


def list_task_summaries(session: Session, task_status: str | None = None) -> list[dict[str, Any]]:
    return [task_summary(session, task) for task in list_tasks(session, task_status)]


def get_task_detail(session: Session, task_id: int) -> dict[str, Any]:
    task = session.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    events = list(
        session.scalars(
            select(TaskEvent)
            .where(TaskEvent.task_id == task_id)
            .order_by(TaskEvent.created_at, TaskEvent.id)
        )
    )
    return {**task_summary(session, task), "history": [task_event_payload(session, event) for event in events]}


def create_confirmed_task(session: Session, payload: TaskCreate) -> Task:
    if not payload.confirmed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Explicit confirmation is required before creating a task",
        )
    if payload.conversation_id is not None and session.get(Conversation, payload.conversation_id) is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    message_id = None
    if payload.original_message:
        message = Message(
            text=payload.original_message,
            conversation_id=payload.conversation_id,
            source="confirmed_task",
        )
        session.add(message)
        session.flush()
        message_id = message.id
    task = Task(
        title=payload.title.strip(),
        description=payload.description.strip() if payload.description else None,
        deadline=normalize_deadline(payload.deadline),
        original_deadline=normalize_deadline(payload.deadline),
        priority=payload.priority,
        conversation_id=payload.conversation_id,
        original_message_id=message_id,
        model_version=payload.model_version,
    )
    session.add(task)
    session.flush()
    created_value = {
        "title": task.title,
        "description": task.description,
        "deadline": task.deadline,
        "priority": task.priority,
        "workflow_status": task.workflow_status,
    }
    session.add(TaskEvent(
        task_id=task.id,
        event_type="created",
        new_value=json_text(created_value),
        evidence=payload.original_message,
        summary=_event_summary("created", {}, created_value),
        confirmed=1,
    ))
    session.flush()
    return task


def update_confirmed_task(session: Session, task_id: int, payload: TaskUpdate) -> Task:
    if not payload.confirmed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Explicit confirmation is required before updating a task",
        )
    task = session.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    old_value = {
        "title": task.title,
        "description": task.description,
        "status": task.status,
        "workflow_status": task.workflow_status,
        "deadline": task.deadline,
        "priority": task.priority,
    }
    if payload.title is not None:
        task.title = payload.title.strip()
    if payload.description is not None:
        task.description = payload.description.strip() or None
    if payload.priority is not None:
        task.priority = payload.priority
    if payload.event_type == "started":
        task.workflow_status = "in_progress"
    elif payload.event_type == "rescheduled":
        task.deadline = normalize_deadline(payload.deadline)
        task.workflow_status = "rescheduled"
    elif payload.event_type == "canceled":
        task.status = "canceled"
        task.workflow_status = "canceled"
    elif payload.event_type == "completed":
        task.status = "completed"
        task.workflow_status = "completed"
    elif payload.event_type == "reopened":
        task.status = "pending"
        task.workflow_status = "pending"
    elif payload.event_type == "edited" and payload.deadline is not None:
        task.deadline = normalize_deadline(payload.deadline)
    session.flush()
    new_value = {
        "title": task.title,
        "description": task.description,
        "status": task.status,
        "workflow_status": task.workflow_status,
        "deadline": task.deadline,
        "priority": task.priority,
    }
    session.add(
        TaskEvent(
            task_id=task.id,
            event_type=payload.event_type,
            old_value=json_text(old_value),
            new_value=json_text(new_value),
            evidence=payload.evidence,
            summary=payload.reason or _event_summary(payload.event_type, old_value, new_value),
            confirmed=1,
        )
    )
    session.flush()
    return task


def create_task_suggestion(
    session: Session,
    message: Message,
    prediction: ModelPrediction,
    analysis: dict[str, Any],
) -> TaskSuggestion | None:
    interpretation = analysis.get("interpretation") or {}
    operation_to_intent = {
        "create_task": "new_task",
        "reschedule_task": "reschedule",
        "cancel_task": "cancellation",
    }
    intent = operation_to_intent.get(interpretation.get("action_type"))
    if intent is None:
        return None

    actions = analysis.get("actions") or []
    action = actions[0] if actions else {}
    task: Task | None = None
    candidates = (analysis.get("context") or {}).get("candidates") or []
    if intent in {"reschedule", "cancellation"} and candidates:
        candidate_id = candidates[0].get("task_id")
        if isinstance(candidate_id, int):
            task = session.get(Task, candidate_id)

    if intent == "new_task":
        reason = "تم استخراج طلب جديد من النص؛ يلزم التأكيد قبل إنشاء المهمة."
    elif task is not None:
        reason = "ربط النظام الرسالة بمهمة موجودة اعتمادًا على سياق الرسالة؛ يلزم التأكيد."
    else:
        reason = "اكتشف النظام تغييرًا محتملًا، لكنه لم يحدد مهمة مرتبطة بثقة كافية."

    suggestion = TaskSuggestion(
        message_id=message.id,
        prediction_id=prediction.id,
        task_id=task.id if task else None,
        suggestion_type=intent,
        suggested_title=(action.get("action_text") or message.text) if task is None else task.title,
        description=message.text if intent == "new_task" else task.description if task else None,
        current_deadline=task.deadline if task else None,
        proposed_deadline=normalize_deadline(action.get("normalized_datetime")),
        evidence=message.text,
        reason=reason,
    )
    session.add(suggestion)
    session.flush()
    return suggestion


def task_suggestion_payload(session: Session, suggestion: TaskSuggestion) -> dict[str, Any]:
    prediction = session.get(ModelPrediction, suggestion.prediction_id)
    return {
        "id": suggestion.id,
        "message_id": suggestion.message_id,
        "prediction_id": suggestion.prediction_id,
        "task_id": suggestion.task_id,
        "suggestion_type": suggestion.suggestion_type,
        "suggested_title": suggestion.suggested_title,
        "description": suggestion.description,
        "current_deadline": suggestion.current_deadline,
        "proposed_deadline": suggestion.proposed_deadline,
        "evidence": suggestion.evidence,
        "reason": suggestion.reason,
        "review_status": suggestion.review_status,
        "model_identifier": prediction.model_version if prediction else None,
        "predicted_intent": prediction.intent if prediction else None,
        "uncalibrated_score": prediction.confidence if prediction else None,
        "created_at": suggestion.created_at,
        "resolved_at": suggestion.resolved_at,
    }


def list_task_suggestions(session: Session, review_status: str = "pending") -> list[dict[str, Any]]:
    suggestions = list(
        session.scalars(
            select(TaskSuggestion)
            .where(TaskSuggestion.review_status == review_status)
            .order_by(TaskSuggestion.created_at.desc(), TaskSuggestion.id.desc())
        )
    )
    return [task_suggestion_payload(session, suggestion) for suggestion in suggestions]


def _range_datetime(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=RIYADH_TZ)


def _event_in_range(value: datetime | None, start: datetime, end: datetime) -> bool:
    if value is None:
        return False
    utc_value = value.astimezone(timezone.utc)
    return start.astimezone(timezone.utc) <= utc_value < end.astimezone(timezone.utc)


def _event_json(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def calendar_payload(
    session: Session,
    range_start: datetime,
    range_end: datetime,
    *,
    include_history: bool = True,
) -> dict[str, Any]:
    """Build calendar markers from the task audit trail without duplicating tasks."""
    start = _range_datetime(range_start)
    end = _range_datetime(range_end)
    if end <= start:
        raise HTTPException(status_code=422, detail="Calendar range_end must be after range_start")

    events: list[dict[str, Any]] = []
    unscheduled_tasks: list[dict[str, Any]] = []
    for task in list_tasks(session):
        summary = task_summary(session, task)
        history = list(
            session.scalars(
                select(TaskEvent)
                .where(TaskEvent.task_id == task.id)
                .order_by(TaskEvent.created_at, TaskEvent.id)
            )
        )
        reschedules = [event for event in history if event.event_type == "rescheduled"]
        current_deadline = _parse_deadline(task.deadline)
        if current_deadline is None:
            unscheduled_tasks.append(summary)
        elif _event_in_range(current_deadline, start, end):
            if task.workflow_status == "canceled":
                color, label = "gray", "ملغاة"
            elif reschedules:
                color, label = "green", "الموعد المحدّث"
            else:
                color, label = "purple", "مهمة"
            events.append(
                {
                    "id": f"task-{task.id}-current",
                    "task_id": task.id,
                    "suggestion_id": None,
                    "kind": "current",
                    "color": color,
                    "label": label,
                    "title": task.title,
                    "starts_at": current_deadline.isoformat(),
                    "recorded_at": task.updated_at,
                    "task_status": task.workflow_status,
                    "is_current": True,
                    "source_message": summary["original_message"],
                }
            )

        if include_history:
            for event in reschedules:
                previous_deadline = _parse_deadline(_event_json(event.old_value).get("deadline"))
                if not _event_in_range(previous_deadline, start, end):
                    continue
                events.append(
                    {
                        "id": f"task-{task.id}-history-{event.id}",
                        "task_id": task.id,
                        "suggestion_id": None,
                        "kind": "historical",
                        "color": "red",
                        "label": "الموعد القديم",
                        "title": f"{task.title} — الموعد القديم",
                        "starts_at": previous_deadline.isoformat(),
                        "recorded_at": event.created_at,
                        "task_status": task.workflow_status,
                        "is_current": False,
                        "source_message": event.related_message.text if event.related_message else event.evidence,
                    }
                )

    pending_unscheduled: list[dict[str, Any]] = []
    pending = list(
        session.scalars(
            select(TaskSuggestion)
            .where(TaskSuggestion.review_status == "pending")
            .order_by(TaskSuggestion.created_at.desc(), TaskSuggestion.id.desc())
        )
    )
    for suggestion in pending:
        payload = task_suggestion_payload(session, suggestion)
        proposed = _parse_deadline(suggestion.proposed_deadline)
        if proposed is None:
            pending_unscheduled.append(payload)
        elif _event_in_range(proposed, start, end):
            events.append(
                {
                    "id": f"suggestion-{suggestion.id}",
                    "task_id": suggestion.task_id,
                    "suggestion_id": suggestion.id,
                    "kind": "pending",
                    "color": "yellow",
                    "label": "بانتظار التأكيد",
                    "title": suggestion.suggested_title or suggestion.evidence,
                    "starts_at": proposed.isoformat(),
                    "recorded_at": suggestion.created_at,
                    "task_status": "pending_review",
                    "is_current": False,
                    "source_message": suggestion.evidence,
                }
            )

    events.sort(key=lambda item: (item["starts_at"], item["task_id"] or 0, item["id"]))
    return {
        "timezone": "Asia/Riyadh",
        "range_start": start,
        "range_end": end,
        "events": events,
        "unscheduled_tasks": unscheduled_tasks,
        "pending_unscheduled": pending_unscheduled,
    }


def confirm_task_suggestion(
    session: Session,
    suggestion_id: int,
    payload: SuggestionDecision,
) -> Task:
    if not payload.confirmed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Explicit confirmation is required before applying a suggestion",
        )
    suggestion = session.get(TaskSuggestion, suggestion_id)
    if suggestion is None:
        raise HTTPException(status_code=404, detail="Task suggestion not found")
    if suggestion.review_status != "pending":
        raise HTTPException(status_code=409, detail="Task suggestion was already reviewed")
    prediction = session.get(ModelPrediction, suggestion.prediction_id)

    if suggestion.suggestion_type == "new_task":
        deadline = normalize_deadline(
            payload.deadline if payload.deadline is not None else suggestion.proposed_deadline
        )
        task = Task(
            title=(payload.title or suggestion.suggested_title or suggestion.evidence).strip(),
            description=(payload.description or suggestion.description),
            deadline=deadline,
            original_deadline=deadline,
            priority=payload.priority,
            original_message_id=suggestion.message_id,
            model_version=prediction.model_version if prediction else None,
        )
        session.add(task)
        session.flush()
        new_value = {
            "title": task.title,
            "description": task.description,
            "deadline": task.deadline,
            "priority": task.priority,
            "workflow_status": task.workflow_status,
        }
        event_type = "created"
        old_value: dict[str, Any] = {}
    else:
        selected_task_id = payload.task_id or suggestion.task_id
        if selected_task_id is None:
            raise HTTPException(
                status_code=409,
                detail="Select a related task before confirming this suggested change",
            )
        task = session.get(Task, selected_task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Related task not found")
        old_value = {
            "title": task.title,
            "description": task.description,
            "status": task.status,
            "workflow_status": task.workflow_status,
            "deadline": task.deadline,
            "priority": task.priority,
        }
        if suggestion.suggestion_type == "reschedule":
            deadline = normalize_deadline(
                payload.deadline if payload.deadline is not None else suggestion.proposed_deadline
            )
            if deadline is None:
                raise HTTPException(
                    status_code=409,
                    detail="No supported date/time was found; enter a deadline before confirmation",
                )
            task.deadline = deadline
            task.workflow_status = "rescheduled"
            event_type = "rescheduled"
        else:
            task.status = "canceled"
            task.workflow_status = "canceled"
            event_type = "canceled"
        new_value = {
            "title": task.title,
            "description": task.description,
            "status": task.status,
            "workflow_status": task.workflow_status,
            "deadline": task.deadline,
            "priority": task.priority,
        }

    session.add(
        TaskEvent(
            task_id=task.id,
            event_type=event_type,
            old_value=json_text(old_value) if old_value else None,
            new_value=json_text(new_value),
            evidence=suggestion.evidence,
            summary=payload.reason or suggestion.reason or _event_summary(event_type, old_value, new_value),
            related_message_id=suggestion.message_id,
            model_prediction_id=suggestion.prediction_id,
            confirmed=1,
        )
    )
    suggestion.task_id = task.id
    suggestion.review_status = "confirmed"
    suggestion.resolved_at = datetime.now(timezone.utc)
    session.flush()
    return task


def reject_task_suggestion(
    session: Session,
    suggestion_id: int,
    payload: SuggestionDecision,
) -> TaskSuggestion:
    if not payload.confirmed:
        raise HTTPException(status_code=409, detail="Explicit confirmation is required")
    suggestion = session.get(TaskSuggestion, suggestion_id)
    if suggestion is None:
        raise HTTPException(status_code=404, detail="Task suggestion not found")
    if suggestion.review_status != "pending":
        raise HTTPException(status_code=409, detail="Task suggestion was already reviewed")
    suggestion.review_status = "rejected"
    suggestion.reason = payload.reason or suggestion.reason
    suggestion.resolved_at = datetime.now(timezone.utc)
    session.flush()
    return suggestion


def create_feedback(session: Session, payload: FeedbackCreate) -> UserCorrection:
    if not payload.confirmed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Explicit confirmation is required before saving feedback",
        )
    if payload.prediction_id is not None and session.get(ModelPrediction, payload.prediction_id) is None:
        raise HTTPException(status_code=404, detail="Prediction not found")
    if payload.message_id is not None and session.get(Message, payload.message_id) is None:
        raise HTTPException(status_code=404, detail="Message not found")
    correction = UserCorrection(
        prediction_id=payload.prediction_id,
        message_id=payload.message_id,
        corrected_intent=payload.corrected_intent,
        corrected_payload_json=json_text(payload.corrected_payload) if payload.corrected_payload else None,
        reviewer=payload.reviewer,
        review_status="reviewed_candidate",
        notes=payload.notes,
    )
    session.add(correction)
    session.flush()
    return correction


def read_json(path: Path, default: Any) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def read_csv_records(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    frame = pd.read_csv(path)
    return json.loads(frame.to_json(orient="records", force_ascii=False))


def dataset_sample_payload(dataset_key: str, query: str, limit: int) -> dict[str, Any]:
    sources = {
        "baseline_96": (PROJECT_ROOT / "data/seed_messages.csv", "message"),
        "massive_ar_sa": (PROJECT_ROOT / "data/processed/massive_relevant_candidates.csv", "utt"),
        "saudi_challenge": (PROJECT_ROOT / "data/evaluation/saudi_challenge_set.csv", "message"),
    }
    if dataset_key not in sources:
        raise HTTPException(status_code=404, detail="لا يوجد ملف محلي قابل للاستعراض لهذه المجموعة.")
    path, text_column = sources[dataset_key]
    frame = pd.read_csv(path)
    if query.strip():
        frame = frame[frame[text_column].fillna("").astype(str).str.contains(query.strip(), case=False, regex=False)]
    rows = json.loads(frame.head(limit).to_json(orient="records", force_ascii=False))
    return {"dataset": dataset_key, "source_file": str(path.relative_to(PROJECT_ROOT)), "rows": rows, "returned": len(rows)}


def _csv_bool(value: Any) -> bool:
    return value is True or str(value).strip().lower() == "true"


def model_comparison_evidence_payload(limit: int = 10) -> dict[str, Any]:
    """Return only saved, reproducible comparisons; never synthesize model wins."""
    predictions_path = PROJECT_ROOT / "results/camelbert/same_holdout_predictions.csv"
    metrics_path = PROJECT_ROOT / "results/camelbert/same_holdout_metrics.csv"
    rows = read_csv_records(predictions_path)
    metrics_rows = read_csv_records(metrics_path)
    labels = ["new_task", "reschedule", "cancellation", "info_only"]
    confusion = {
        model: {truth: {prediction: 0 for prediction in labels} for truth in labels}
        for model in ("baseline", "camelbert")
    }


def _failure_category(message: str, truth: str | None = None) -> str:
    normalized = str(message)
    if re.search(r"(?:ما في داعي|لا |لن |محد|لاحد)", normalized): return "negation"
    if re.search(r"(?:قبل الساعة|قبل نهاية|موعد|تأجل|خلوه)", normalized): return "deadline_or_rescheduling"
    if truth == "info_only" or re.search(r"(?:نشكر|تم اعتماد|أون لاين|نفيدكم)", normalized): return "informational"
    if truth == "cancellation" or re.search(r"(?:إلغاء|الغاء|انلغ)", normalized): return "cancellation"
    if re.search(r"(?:خلاص|ابغى|أبغى|بكرة)", normalized): return "dialect"
    if re.search(r"(?:و|،).*(?:و|،)", normalized): return "multiple_actions"
    return "other"


def error_analysis_payload() -> dict[str, Any]:
    baseline_rows = read_csv_records(PROJECT_ROOT / "results/baseline/misclassified_examples.csv")
    overlap_rows = read_csv_records(PROJECT_ROOT / "results/camelbert/same_holdout_predictions.csv")
    challenge_rows = read_csv_records(PROJECT_ROOT / "results/camelbert/saudi_challenge_predictions.csv")
    failures: list[dict[str, Any]] = []
    for row in baseline_rows:
        failures.append({
            "message": row["message"], "expected_label": row["true_intent"],
            "baseline_prediction": row["predicted_intent"], "camelbert_prediction": None,
            "category": _failure_category(row["message"], row["true_intent"]),
            "explanation": row.get("possible_reason"), "source": "original_baseline_24",
            "validity": "valid_for_original_baseline_only", "synthetic": True,
        })
    for row in overlap_rows:
        if _csv_bool(row.get("baseline_correct")) and _csv_bool(row.get("camelbert_correct")):
            continue
        failures.append({
            "message": row["message"], "expected_label": row["true_intent"],
            "baseline_prediction": row["baseline_prediction"], "camelbert_prediction": row["camelbert_prediction"],
            "category": _failure_category(row["message"], row["true_intent"]),
            "explanation": "نتيجة تشغيل محفوظة؛ لم يثبت سبب الخطأ تجريبيًا.", "source": "overlapping_repository_24",
            "validity": "contaminated_diagnostic", "synthetic": True,
        })
    for row in challenge_rows:
        label = row.get("reference_intent")
        if label and _csv_bool(row.get("baseline_correct")) and _csv_bool(row.get("camelbert_correct")):
            continue
        failures.append({
            "message": row["message"], "expected_label": label or None,
            "baseline_prediction": row.get("baseline_prediction"), "camelbert_prediction": row.get("camelbert_prediction"),
            "category": row.get("category") or _failure_category(row["message"], label),
            "explanation": row.get("notes"), "source": "manual_saudi_challenge",
            "validity": "curated_synthetic_demo_not_human_verified" if label else "needs_context_not_scored",
            "synthetic": True,
        })
    return {
        "failures": failures,
        "sections": {
            "original_baseline": {"saved_errors": len(baseline_rows), "independent_for_baseline": True, "note": "اختبار اصطناعي محفوظ من 24 رسالة؛ صالح لتحليل النموذج الأساسي فقط."},
            "colab_125": {"reported_errors": 13, "prediction_rows_available": False, "note": "حُفظت المقاييس الإجمالية فقط؛ لا يمكن عرض رسائل الخطأ أو مصفوفة الالتباس دون ملف تنبؤات Colab."},
            "overlapping_24": {"rows": len(overlap_rows), "independent_comparison": False, "note": "متداخل مع بيانات ضبط CAMeLBERT؛ تشخيص تكامل فقط."},
            "saudi_challenge": {"rows": len(challenge_rows), "human_verified": False, "note": "أمثلة تحدٍ اصطناعية منسقة، وليست مجموعة اختبار واقعية مستقلة."},
        },
    }
    improvements: list[dict[str, Any]] = []
    errors: dict[str, list[dict[str, Any]]] = {"baseline": [], "camelbert": []}

    for row in rows:
        truth = str(row["true_intent"])
        baseline_prediction = str(row["baseline_prediction"])
        camelbert_prediction = str(row["camelbert_prediction"])
        if truth in labels and baseline_prediction in labels:
            confusion["baseline"][truth][baseline_prediction] += 1
        if truth in labels and camelbert_prediction in labels:
            confusion["camelbert"][truth][camelbert_prediction] += 1
        example = {
            "message": str(row["message"]),
            "expected_label": truth,
            "baseline_prediction": baseline_prediction,
            "baseline_score": float(row["baseline_uncalibrated_score"]),
            "baseline_latency_ms": float(row["baseline_latency_ms"]),
            "baseline_correct": _csv_bool(row["baseline_correct"]),
            "camelbert_prediction": camelbert_prediction,
            "camelbert_score": float(row["camelbert_uncalibrated_score"]),
            "camelbert_latency_ms": float(row["camelbert_latency_ms"]),
            "camelbert_correct": _csv_bool(row["camelbert_correct"]),
            "reference_status": "saved_synthetic_reference_label",
        }
        if not example["baseline_correct"]:
            errors["baseline"].append(example)
        if not example["camelbert_correct"]:
            errors["camelbert"].append(example)
        if not example["baseline_correct"] and example["camelbert_correct"]:
            improvements.append(example)

    metrics = {
        row["model"]: {
            "model_identifier": row["model_identifier"],
            "accuracy": row["accuracy"],
            "macro_f1": row["macro_f1"],
            "rows": row["rows"],
            "mean_inference_latency_ms": row["mean_inference_latency_ms"],
            "provenance": row["data_provenance"],
        }
        for row in metrics_rows
    }
    metrics["reported_colab_125"] = {
        "rows": 125,
        "provenance": "user_reported_synthetic_colab_evaluation",
        "baseline_accuracy": 0.72,
        "baseline_macro_f1": 0.719,
        "camelbert_accuracy": 0.896,
        "camelbert_macro_f1": 0.895,
    }
    return {
        "examples": improvements[:limit],
        "metrics": metrics,
        "confusion_matrices": confusion,
        "methodology": {
            "saved_prediction_rows": len(rows),
            "data_provenance": "synthetic",
            "reference_labels": "saved synthetic evaluation labels",
            "independent_test": False,
            "leakage_warning": (
                "The 24-row repository holdout overlaps the 500-message CAMeLBERT fine-tuning "
                "corpus and is not an independent estimate. It may demonstrate pipeline behavior "
                "but must not be presented as unbiased generalization accuracy."
            ),
            "selection_rule": "baseline incorrect AND CAMeLBERT correct in saved predictions",
            "available_genuine_improvements": len(improvements),
            "errors": {
                "baseline": len(errors["baseline"]),
                "camelbert": len(errors["camelbert"]),
            },
        },
    }


# Kept as a complete definition after the error-analysis builder so the two
# artifact readers remain independent and neither can truncate the other.
def model_comparison_evidence_payload(limit: int = 10) -> dict[str, Any]:
    rows = read_csv_records(PROJECT_ROOT / "results/camelbert/same_holdout_predictions.csv")
    metrics_rows = read_csv_records(PROJECT_ROOT / "results/camelbert/same_holdout_metrics.csv")
    labels = ["new_task", "reschedule", "cancellation", "info_only"]
    confusion = {model: {truth: {prediction: 0 for prediction in labels} for truth in labels} for model in ("baseline", "camelbert")}
    improvements: list[dict[str, Any]] = []
    errors: dict[str, list[dict[str, Any]]] = {"baseline": [], "camelbert": []}
    for row in rows:
        truth = str(row["true_intent"]); baseline_prediction = str(row["baseline_prediction"]); camelbert_prediction = str(row["camelbert_prediction"])
        if truth in labels and baseline_prediction in labels: confusion["baseline"][truth][baseline_prediction] += 1
        if truth in labels and camelbert_prediction in labels: confusion["camelbert"][truth][camelbert_prediction] += 1
        example = {
            "message": str(row["message"]), "expected_label": truth,
            "baseline_prediction": baseline_prediction, "baseline_score": float(row["baseline_uncalibrated_score"]),
            "baseline_latency_ms": float(row["baseline_latency_ms"]), "baseline_correct": _csv_bool(row["baseline_correct"]),
            "camelbert_prediction": camelbert_prediction, "camelbert_score": float(row["camelbert_uncalibrated_score"]),
            "camelbert_latency_ms": float(row["camelbert_latency_ms"]), "camelbert_correct": _csv_bool(row["camelbert_correct"]),
            "reference_status": "saved_synthetic_reference_label",
        }
        if not example["baseline_correct"]: errors["baseline"].append(example)
        if not example["camelbert_correct"]: errors["camelbert"].append(example)
        if not example["baseline_correct"] and example["camelbert_correct"]: improvements.append(example)
    metrics = {row["model"]: {"model_identifier": row["model_identifier"], "accuracy": row["accuracy"], "macro_f1": row["macro_f1"], "rows": row["rows"], "mean_inference_latency_ms": row["mean_inference_latency_ms"], "provenance": row["data_provenance"]} for row in metrics_rows}
    metrics["reported_colab_125"] = {"rows": 125, "provenance": "user_reported_synthetic_colab_evaluation", "baseline_accuracy": 0.72, "baseline_macro_f1": 0.719, "camelbert_accuracy": 0.896, "camelbert_macro_f1": 0.895}
    return {
        "examples": improvements[:limit], "metrics": metrics, "confusion_matrices": confusion,
        "methodology": {
            "saved_prediction_rows": len(rows), "data_provenance": "synthetic", "reference_labels": "saved synthetic evaluation labels",
            "independent_test": False,
            "leakage_warning": "The 24-row repository holdout overlaps the 500-message CAMeLBERT fine-tuning corpus and is not an independent estimate. It may demonstrate pipeline behavior but must not be presented as unbiased generalization accuracy.",
            "selection_rule": "baseline incorrect AND CAMeLBERT correct in saved predictions",
            "available_genuine_improvements": len(improvements), "errors": {"baseline": len(errors["baseline"]), "camelbert": len(errors["camelbert"])},
        },
    }


def analytics_payload(model_statuses: dict[str, dict[str, Any]], session: Session) -> dict[str, Any]:
    baseline = read_json(PROJECT_ROOT / "results/baseline/error_analysis_summary.json", {})
    dataset = read_json(PROJECT_ROOT / "results/data/dataset_summary.json", {})
    context_matching = read_json(PROJECT_ROOT / "results/context_matching/summary.json", {})
    class_metrics = read_csv_records(PROJECT_ROOT / "results/baseline/classification_report.csv")
    comparison = read_csv_records(PROJECT_ROOT / "results/model_comparison.csv")
    camelbert_comparison = read_csv_records(
        PROJECT_ROOT / "results/camelbert/same_holdout_metrics.csv"
    )
    comparison.extend(
        {
            "model": row["model_identifier"],
            "status": "overlapping_synthetic_holdout_not_independent",
            "accuracy": row["accuracy"],
            "macro_f1": row["macro_f1"],
            "weighted_f1": row["weighted_f1"],
        }
        for row in camelbert_comparison
        if row.get("model") == "camelbert"
    )
    confusion_path = PROJECT_ROOT / "results/baseline/confusion_matrix.csv"
    confusion = read_csv_records(confusion_path)
    task_counts = {
        task_status: len(list_tasks(session, task_status))
        for task_status in ("pending", "completed", "canceled")
    }
    feedback_count = len(list(session.scalars(select(UserCorrection.id))))
    prediction_count = len(list(session.scalars(select(ModelPrediction.id))))
    dataset["registry"] = [
        {
            "key": "baseline_96", "name": "المجموعة الاصطناعية الأصلية", "examples": 96,
            "source": "تأليف اصطناعي داخل المشروع", "label_schema": "FI'L AI — أربع فئات",
            "language": "العربية مع أمثلة خليجية محدودة", "status": "synthetic",
            "usage": "تدريب النموذج الأساسي وتقسيم اختبار محفوظ من 24 رسالة",
            "models": ["TF-IDF + Logistic Regression"], "splits": "72 تطوير / 24 اختبار محفوظ",
            "license": "ملف مشروع داخلي", "limitations": "صغيرة واصطناعية ولا تقيس الأداء الواقعي.", "file_available": True,
        },
        {
            "key": "camelbert_500", "name": "مجموعة الضبط الدقيق الموسعة", "examples": 500,
            "source": "تجربة Google Colab الموثقة من المستخدم", "label_schema": "FI'L AI — أربع فئات",
            "language": "العربية وأمثلة سعودية اصطناعية", "status": "synthetic",
            "usage": "ضبط CAMeLBERT ومقارنة النموذج الكلاسيكي على التقسيم نفسه",
            "models": ["CAMeLBERT-DA", "Classical baseline on Colab split"], "splits": "300 تدريب / 75 تحقق / 125 اختبار",
            "license": "لم يوثّق ترخيص مستقل", "limitations": "ملف الـ500 صف وتقسيم العائلات غير موجودين في المستودع؛ لا يمكن تدقيق تسرب الصياغات المتقاربة محليًا.", "file_available": False,
        },
        {
            "key": "massive_ar_sa", "name": "Amazon MASSIVE ar-SA", "examples": 16521,
            "source": "AmazonScience/massive", "label_schema": "60 نية أصلية للمساعد الافتراضي",
            "language": "ar-SA منشورة", "status": "published",
            "usage": "استكشاف اللغة والكيانات الزمنية فقط؛ لم تستخدم لضبط مصنف FI'L AI",
            "models": [], "splits": "11,514 تدريب / 2,033 تحقق / 2,974 اختبار",
            "license": "CC BY 4.0", "limitations": "ملصقاتها ليست مكافئة لفئات FI'L AI الأربع.", "file_available": True,
        },
        {
            "key": "human_reviewed", "name": "بيانات المجال المراجعة بشريًا", "examples": 0,
            "source": "لم تجمع بعد", "label_schema": "FI'L AI — أربع فئات + أفعال سياقية",
            "language": "العربية السعودية المستهدفة", "status": "human_reviewed",
            "usage": "مرشح للتقييم الواقعي والضبط المستقبلي", "models": [], "splits": "غير متاح",
            "license": "يحدد عند الجمع", "limitations": "العدد الحالي صفر.", "file_available": False,
        },
    ]
    return {
        "model": {
            "active": model_statuses["baseline"]["identifier"],
            "warning": model_statuses["baseline"]["warning"],
            "transformer_trained": model_statuses["camelbert"]["available"],
            "available": model_statuses,
            "camelbert_reported_accuracy": 0.896,
            "camelbert_metric_provenance": (
                "User-reported 125-example synthetic Colab evaluation; it is not real-world accuracy."
            ),
            "reported_colab_125": {
                "baseline_accuracy": 0.72,
                "baseline_macro_f1": 0.719,
                "camelbert_accuracy": 0.896,
                "camelbert_macro_f1": 0.895,
            },
        },
        "baseline": baseline,
        "class_metrics": class_metrics,
        "confusion_matrix": confusion,
        "model_comparison": comparison,
        "dataset": dataset,
        "context_matching": context_matching,
        "application": {
            "task_counts": task_counts,
            "prediction_count": prediction_count,
            "feedback_candidate_count": feedback_count,
        },
        "limitations": [
            "The preserved TF-IDF baseline was trained on 96 synthetic messages.",
            "Synthetic holdout metrics cannot establish real-world accuracy.",
            "CAMeLBERT's reported 89.6% test accuracy is from synthetic data only.",
            "The separate 24-row 95.8% result overlaps the 500-message fine-tuning corpus and is not an independent comparison.",
            "Extraction and contextual matching lack a reviewed quantitative test set.",
        ],
    }
