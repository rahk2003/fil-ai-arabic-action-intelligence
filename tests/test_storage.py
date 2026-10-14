from pathlib import Path

import pytest

from fil_ai.storage import TaskStore


def test_task_creation_requires_confirmation(tmp_path: Path):
    store = TaskStore(tmp_path / "test.db")
    with pytest.raises(PermissionError):
        store.create_task("إرسال التقرير")


def test_task_history_and_persistence(tmp_path: Path):
    store = TaskStore(tmp_path / "test.db")
    task_id = store.create_task("اجتماع الفريق", deadline="2026-10-18T10:00:00+03:00", confirmed=True)
    store.update_task(task_id, event_type="rescheduled", new_deadline="2026-10-22T12:00:00+03:00", evidence="خلوه الخميس", confirmed=True)
    assert store.list_tasks("pending")[0]["deadline"] == "2026-10-22T12:00:00+03:00"
    assert [event["event_type"] for event in store.history(task_id)] == ["created", "rescheduled"]


def test_cancellation_requires_confirmation(tmp_path: Path):
    store = TaskStore(tmp_path / "test.db")
    task_id = store.create_task("اجتماع", confirmed=True)
    with pytest.raises(PermissionError):
        store.update_task(task_id, event_type="canceled")
    store.update_task(task_id, event_type="canceled", confirmed=True)
    assert store.list_tasks("canceled")[0]["id"] == task_id
