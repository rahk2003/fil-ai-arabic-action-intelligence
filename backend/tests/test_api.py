import base64
import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.settings import Settings

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def client(tmp_path: Path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'api.db'}",
        model_path=str(ROOT / "models/intent_baseline.joblib"),
        cors_origins="http://localhost:5173",
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def test_health_reports_real_model_and_database(client: TestClient):
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["database"] == "sqlite"
    assert payload["model"] == "tfidf-logreg:intent_baseline"
    assert payload["models"]["baseline"]["loaded"] is True
    assert payload["models"]["camelbert"]["available"] is True
    assert payload["models"]["camelbert"]["loaded"] is False


def test_analyze_persists_real_prediction(client: TestClient):
    response = client.post(
        "/api/analyze",
        json={
            "message": "ارسلي التقرير بكرة الساعة ٩ الصباح",
            "reference_time": "2026-10-14T12:00:00+03:00",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["message_id"] > 0 and payload["prediction_id"] > 0
    assert payload["analysis"]["prediction"]["model_name"] == "tfidf-logreg:intent_baseline"
    assert payload["analysis"]["prediction"]["uncalibrated_score"] > 0
    assert payload["analysis"]["prediction"]["inference_latency_ms"] >= 0
    assert payload["analysis"]["prediction"]["label"] in {
        "new_task", "reschedule", "cancellation", "info_only"
    }
    assert payload["analysis"]["actions"][0]["normalized_datetime"] == "2026-10-15T09:00:00+03:00"


def test_task_mutations_require_confirmation_and_keep_history(client: TestClient):
    unconfirmed = client.post(
        "/api/tasks",
        json={"title": "إرسال التقرير", "priority": "high", "confirmed": False},
    )
    assert unconfirmed.status_code == 409
    created = client.post(
        "/api/tasks",
        json={
            "title": "إرسال التقرير",
            "deadline": "2026-10-15T09:00:00+03:00",
            "priority": "high",
            "confirmed": True,
        },
    )
    assert created.status_code == 201
    task_id = created.json()["id"]
    updated = client.patch(
        f"/api/tasks/{task_id}",
        json={
            "event_type": "rescheduled",
            "deadline": "2026-10-16T14:00:00+03:00",
            "evidence": "خلوه الخميس الساعة ٢",
            "confirmed": True,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["deadline"] == "2026-10-16T14:00:00+03:00"
    history = client.get(f"/api/tasks/{task_id}/history")
    assert [event["event_type"] for event in history.json()] == ["created", "rescheduled"]


def test_conversation_analysis_and_feedback_queue(client: TestClient):
    response = client.post(
        "/api/conversations/analyze",
        json={
            "title": "اجتماع الفريق",
            "reference_time": "2026-10-14T12:00:00+03:00",
            "messages": [
                "اجتماعنا يوم الأحد الساعة 10 الصباح",
                "خلاص خلوه الخميس الساعة 12 الظهر",
            ],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["conversation_id"] > 0
    assert len(payload["analyses"]) == 2
    assert payload["automatic_task_mutations"] is False
    prediction_id = payload["analyses"][0]["prediction_id"]
    feedback = client.post(
        "/api/feedback",
        json={
            "prediction_id": prediction_id,
            "corrected_intent": "info_only",
            "reviewer": "capstone-reviewer",
            "notes": "Requires conversational context",
            "confirmed": True,
        },
    )
    assert feedback.status_code == 201
    assert feedback.json()["review_status"] == "reviewed_candidate"
    assert feedback.json()["online_retraining"] is False


def test_analytics_uses_saved_artifacts(client: TestClient):
    response = client.get("/api/analytics")
    assert response.status_code == 200
    payload = response.json()
    assert payload["baseline"]["accuracy"] == 0.5
    assert payload["baseline"]["macro_f1"] == 0.494353
    assert payload["dataset"]["split_counts"] == {
        "train": 11514, "validation": 2033, "test": 2974
    }
    assert payload["model"]["transformer_trained"] is True
    assert payload["model"]["camelbert_reported_accuracy"] == 0.896


def test_camelbert_and_compare_use_the_requested_real_models(client: TestClient):
    known_failure = client.post(
        "/api/analyze",
        json={"message": "بكرة الدوام أون لاين", "model": "camelbert"},
    )
    assert known_failure.status_code == 200
    transformer = known_failure.json()["analysis"]["prediction"]
    assert transformer["model_identifier"] == "camelbert-da:FIL_AI_CAMeLBERT"
    assert transformer["label"] == "reschedule"
    assert transformer["uncalibrated_score"] > 0
    assert transformer["inference_latency_ms"] >= 0

    comparison = client.post(
        "/api/analyze/compare",
        json={"message": "تم اعتماد التقرير النهائي"},
    )
    assert comparison.status_code == 200
    payload = comparison.json()
    assert payload["same_message"] is True
    assert payload["results"]["baseline"]["message_id"] == payload["message_id"]
    assert payload["results"]["camelbert"]["message_id"] == payload["message_id"]
    assert payload["results"]["baseline"]["prediction_id"] != payload["results"]["camelbert"]["prediction_id"]
    assert payload["results"]["camelbert"]["analysis"]["prediction"]["label"] == "cancellation"
    assert client.get("/api/health").json()["models"]["camelbert"]["loaded"] is True


def test_explicit_camelbert_failure_does_not_fall_back(tmp_path: Path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'missing-model.db'}",
        model_path=str(ROOT / "models/intent_baseline.joblib"),
        camelbert_model_path=str(tmp_path / "missing-camelbert"),
    )
    with TestClient(create_app(settings)) as test_client:
        response = test_client.post(
            "/api/analyze",
            json={"message": "ارسلي التقرير", "model": "camelbert"},
        )
    assert response.status_code == 503
    assert "does not exist" in response.json()["detail"]


def test_analysis_creates_reviewable_suggestion_but_info_only_does_not(client: TestClient):
    detected = client.post(
        "/api/analyze",
        json={"message": "لو سمحتي أرسلي نسخة التقرير النهائي قبل نهاية الأسبوع."},
    )
    assert detected.status_code == 200
    suggestion_id = detected.json()["suggestion_id"]
    assert suggestion_id is not None
    assert client.get("/api/tasks").json() == []

    pending = client.get("/api/task-suggestions").json()
    assert [item["id"] for item in pending] == [suggestion_id]
    confirmed = client.post(
        f"/api/task-suggestions/{suggestion_id}/confirm",
        json={"confirmed": True, "priority": "high"},
    )
    assert confirmed.status_code == 200
    task = confirmed.json()
    assert task["original_message"].startswith("لو سمحتي")
    assert task["source"] == "api"
    assert task["workflow_status"] == "pending"

    informational = client.post(
        "/api/analyze",
        json={"message": "وصلنا تحديث النظام"},
    )
    assert informational.status_code == 200
    assert informational.json()["analysis"]["prediction"]["label"] == "info_only"
    assert informational.json()["suggestion_id"] is None


def test_reschedule_and_cancel_update_one_task_and_preserve_history(client: TestClient):
    created = client.post(
        "/api/tasks",
        json={
            "title": "حجز الموعد",
            "description": "موعد العميل",
            "deadline": "2026-10-15T10:00:00+03:00",
            "priority": "medium",
            "original_message": "احجزي الموعد الخميس الساعة 10 صباحًا",
            "confirmed": True,
        },
    ).json()
    task_id = created["id"]

    reschedule = client.post(
        "/api/analyze",
        json={
            "message": "غيرنا موعد حجز الموعد إلى الخميس الساعة 2 الظهر",
            "reference_time": "2026-10-14T12:00:00+03:00",
        },
    ).json()
    reschedule_id = reschedule["suggestion_id"]
    assert reschedule_id is not None
    reschedule_suggestion = next(
        item for item in client.get("/api/task-suggestions").json()
        if item["id"] == reschedule_id
    )
    assert reschedule_suggestion["task_id"] == task_id
    changed = client.post(
        f"/api/task-suggestions/{reschedule_id}/confirm",
        json={"confirmed": True},
    )
    assert changed.status_code == 200
    assert changed.json()["workflow_status"] == "rescheduled"
    assert changed.json()["original_deadline"] == "2026-10-15T10:00:00+03:00"
    assert changed.json()["deadline"] == "2026-10-15T14:00:00+03:00"
    assert len(client.get("/api/tasks").json()) == 1

    cancellation = client.post(
        "/api/analyze",
        json={"message": "تم إلغاء الموعد وحذف الحجز."},
    ).json()
    cancellation_id = cancellation["suggestion_id"]
    assert cancellation_id is not None
    canceled = client.post(
        f"/api/task-suggestions/{cancellation_id}/confirm",
        json={"confirmed": True, "task_id": task_id},
    )
    assert canceled.status_code == 200
    assert canceled.json()["workflow_status"] == "canceled"
    assert len(client.get("/api/tasks").json()) == 1

    detail = client.get(f"/api/tasks/{task_id}")
    assert detail.status_code == 200
    history = detail.json()["history"]
    assert [event["event_type"] for event in history] == ["created", "rescheduled", "canceled"]
    assert history[1]["related_message"] == "غيرنا موعد حجز الموعد إلى الخميس الساعة 2 الظهر"
    assert history[1]["model_intent"] == "reschedule"
    assert "تغيير الموعد" in history[1]["summary"] or "ربط النظام" in history[1]["summary"]


def test_calendar_uses_one_task_for_old_and_new_deadline(client: TestClient):
    created = client.post(
        "/api/tasks",
        json={
            "title": "اجتماع المشروع",
            "deadline": "2026-10-18T10:00",
            "original_message": "اجتماع المشروع يوم الأحد الساعة 10 صباحًا.",
            "priority": "high",
            "confirmed": True,
        },
    ).json()
    task_id = created["id"]
    assert created["deadline"] == "2026-10-18T10:00:00+03:00"
    updated = client.patch(
        f"/api/tasks/{task_id}",
        json={
            "event_type": "rescheduled",
            "deadline": "2026-10-22T14:00:00+03:00",
            "evidence": "خلاص أجلوا الاجتماع للخميس الساعة 2 الظهر.",
            "confirmed": True,
        },
    )
    assert updated.status_code == 200

    response = client.get(
        "/api/calendar",
        params={
            "start": "2026-10-17T00:00:00+03:00",
            "end": "2026-10-24T00:00:00+03:00",
            "include_history": "true",
        },
    )
    assert response.status_code == 200
    events = response.json()["events"]
    task_events = [event for event in events if event["task_id"] == task_id]
    assert len(task_events) == 2
    assert {event["color"] for event in task_events} == {"red", "green"}
    assert {event["task_id"] for event in task_events} == {task_id}
    assert next(event for event in task_events if event["color"] == "red")["is_current"] is False
    assert next(event for event in task_events if event["color"] == "green")["is_current"] is True

    current_only = client.get(
        "/api/calendar",
        params={
            "start": "2026-10-17T00:00:00+03:00",
            "end": "2026-10-24T00:00:00+03:00",
            "include_history": "false",
        },
    ).json()["events"]
    assert [event["color"] for event in current_only if event["task_id"] == task_id] == ["green"]


def test_calendar_lists_unscheduled_and_pending_review_without_fake_dates(client: TestClient):
    task = client.post(
        "/api/tasks",
        json={"title": "مهمة دون موعد", "priority": "medium", "confirmed": True},
    ).json()
    analyzed = client.post(
        "/api/analyze",
        json={
            "message": "ارسلي التقرير بكرة الساعة ٩ الصباح",
            "reference_time": "2026-10-14T12:00:00+03:00",
        },
    ).json()
    assert analyzed["suggestion_id"] is not None
    calendar = client.get(
        "/api/calendar",
        params={
            "start": "2026-10-14T00:00:00+03:00",
            "end": "2026-10-17T00:00:00+03:00",
        },
    ).json()
    assert [item["id"] for item in calendar["unscheduled_tasks"]] == [task["id"]]
    pending = [event for event in calendar["events"] if event["suggestion_id"] == analyzed["suggestion_id"]]
    assert len(pending) == 1
    assert pending[0]["color"] == "yellow"
    assert pending[0]["task_status"] == "pending_review"


def test_model_comparison_evidence_is_saved_and_leakage_labeled(client: TestClient):
    response = client.get("/api/evaluation/model-comparison?limit=10")
    assert response.status_code == 200
    payload = response.json()
    assert 5 <= len(payload["examples"]) <= 10
    assert all(not row["baseline_correct"] and row["camelbert_correct"] for row in payload["examples"])
    assert payload["metrics"]["reported_colab_125"]["baseline_accuracy"] == 0.72
    assert payload["metrics"]["reported_colab_125"]["camelbert_accuracy"] == 0.896
    assert payload["methodology"]["independent_test"] is False
    assert "تتداخل" in payload["methodology"]["leakage_warning"]


def test_csv_import_preview_duplicate_validation_and_commit(client: TestClient):
    csv_bytes = (
        "اسم المهمة,الوصف,التاريخ,الوقت,الأولوية,الحالة\n"
        "مراجعة العقد,مراجعة النسخة النهائية,2026-10-24,09:30,عالية,قيد الانتظار\n"
        "صف غير صالح,,ليس-تاريخ,,متوسطة,قيد الانتظار\n"
    ).encode("utf-8-sig")
    upload = {"filename": "tasks.csv", "content_base64": base64.b64encode(csv_bytes).decode()}
    preview = client.post("/api/tasks/import/preview", json=upload)
    assert preview.status_code == 200
    body = preview.json()
    assert body["summary"] == {"total": 2, "valid": 1, "duplicates": 0, "invalid": 1}
    assert body["rows"][0]["deadline"] == "2026-10-24T09:30:00+03:00"
    valid_rows = [row for row in body["rows"] if row["valid"]]
    committed = client.post("/api/tasks/import/commit", json={"rows": valid_rows, "confirmed": True})
    assert committed.status_code == 200
    assert committed.json()["imported"] == 1
    duplicate = client.post("/api/tasks/import/preview", json=upload).json()
    assert duplicate["summary"]["duplicates"] == 1


def test_xlsx_import_preview_when_engine_is_available(client: TestClient):
    openpyxl = pytest.importorskip("openpyxl")
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(["title", "deadline", "priority", "status"])
    sheet.append(["تحضير العرض", "2026-10-25T14:00:00+03:00", "urgent", "in_progress"])
    buffer = io.BytesIO(); workbook.save(buffer)
    preview = client.post("/api/tasks/import/preview", json={"filename": "tasks.xlsx", "content_base64": base64.b64encode(buffer.getvalue()).decode()})
    assert preview.status_code == 200
    row = preview.json()["rows"][0]
    assert row["valid"] is True
    assert row["status"] == "in_progress"


@pytest.mark.parametrize(
    ("messages", "expected_actions"),
    [
        (["حلل كل البيانات", "خلاص حلل بس جزء"], ["create_task", "update_task_scope"]),
        (["جهز التقرير كامل", "خلاص خله مختصر"], ["create_task", "update_task_scope"]),
        (["حلل بيانات كل الفروع", "ركز بس على فرع الرياض"], ["create_task", "update_task_scope"]),
        (["اجتماعنا يوم الأحد الساعة 10", "خلاص خلوه الخميس الساعة 2"], ["create_task", "reschedule_task"]),
        (["ارسل التقرير بكرة", "لا ترسله خلاص"], ["create_task", "cancel_task"]),
        (["جهز العرض", "وخله باللغة الإنجليزية"], ["create_task", "update_task_requirement"]),
    ],
)
def test_contextual_followups_are_separate_from_raw_classifier(client: TestClient, messages, expected_actions):
    response = client.post(
        "/api/conversations/analyze",
        json={"messages": messages, "reference_time": "2026-10-14T12:00:00+03:00"},
    )
    assert response.status_code == 200
    analyses = response.json()["analyses"]
    assert [item["analysis"]["interpretation"]["action_type"] for item in analyses] == expected_actions
    assert analyses[1]["analysis"]["interpretation"]["related_task_id"] == "conversation-1"
    assert response.json()["automatic_task_mutations"] is False


def test_error_analysis_separates_saved_sources(client: TestClient):
    response = client.get("/api/evaluation/errors")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["failures"]) >= 10
    assert payload["sections"]["colab_125"]["prediction_rows_available"] is False
    assert payload["sections"]["overlapping_24"]["independent_comparison"] is False


def test_word_bassit_does_not_trigger_scope_change(client: TestClient):
    response = client.post(
        "/api/analyze",
        json={"message": "عندي طلب بسيط: اكتبي مقدمة عربية للمبادرة"},
    )
    assert response.status_code == 200
    analysis = response.json()["analysis"]
    assert analysis["prediction"]["label"] == "cancellation"
    assert analysis["actions"][0]["intent"] == "new_task"
    assert analysis["interpretation"]["action_type"] == "create_task"
    assert analysis["interpretation"]["classifier_extraction_consistency"] == "conflict"
