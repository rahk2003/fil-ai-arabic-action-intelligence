"""Local SQLite persistence with confirmation-gated task mutations."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .config import DATABASE_PATH

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    source TEXT NOT NULL DEFAULT 'local'
);
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','completed','canceled')),
    deadline TEXT,
    original_message_id INTEGER REFERENCES messages(id),
    model_version TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS task_events (
    id INTEGER PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES tasks(id),
    event_type TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    evidence TEXT,
    confirmed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS model_predictions (
    id INTEGER PRIMARY KEY,
    message_id INTEGER NOT NULL REFERENCES messages(id),
    model_version TEXT NOT NULL,
    intent TEXT NOT NULL,
    confidence REAL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS user_corrections (
    id INTEGER PRIMARY KEY,
    prediction_id INTEGER REFERENCES model_predictions(id),
    corrected_intent TEXT,
    corrected_payload_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


class TaskStore:
    def __init__(self, path: Path | str = DATABASE_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    def save_analysis(self, message: str, analysis: dict[str, Any]) -> int:
        prediction = analysis["prediction"]
        with self.connect() as connection:
            cursor = connection.execute("INSERT INTO messages(text) VALUES (?)", (message,))
            message_id = int(cursor.lastrowid)
            connection.execute(
                "INSERT INTO model_predictions(message_id, model_version, intent, confidence, payload_json) VALUES (?,?,?,?,?)",
                (
                    message_id,
                    prediction["model_name"],
                    prediction["label"],
                    prediction["confidence"],
                    json.dumps(analysis, ensure_ascii=False),
                ),
            )
        return message_id

    def create_task(
        self,
        title: str,
        *,
        deadline: str | None = None,
        original_message: str | None = None,
        model_version: str = "manual",
        confirmed: bool = False,
    ) -> int:
        if not confirmed:
            raise PermissionError("Task creation requires explicit user confirmation")
        if not title.strip():
            raise ValueError("Task title cannot be empty")
        with self.connect() as connection:
            message_id = None
            if original_message:
                cursor = connection.execute("INSERT INTO messages(text) VALUES (?)", (original_message,))
                message_id = int(cursor.lastrowid)
            cursor = connection.execute(
                "INSERT INTO tasks(title, deadline, original_message_id, model_version) VALUES (?,?,?,?)",
                (title.strip(), deadline or None, message_id, model_version),
            )
            task_id = int(cursor.lastrowid)
            connection.execute(
                "INSERT INTO task_events(task_id, event_type, new_value, evidence, confirmed) VALUES (?,?,?,?,1)",
                (task_id, "created", deadline, original_message),
            )
        return task_id

    def update_task(
        self,
        task_id: int,
        *,
        event_type: str,
        new_deadline: str | None = None,
        evidence: str | None = None,
        confirmed: bool = False,
    ) -> None:
        if not confirmed:
            raise PermissionError("Task updates require explicit user confirmation")
        if event_type not in {"rescheduled", "canceled", "completed"}:
            raise ValueError("Unsupported task event")
        with self.connect() as connection:
            current = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if current is None:
                raise KeyError(f"Unknown task id: {task_id}")
            old_value = current["deadline"]
            status = "canceled" if event_type == "canceled" else "completed" if event_type == "completed" else current["status"]
            deadline = new_deadline if event_type == "rescheduled" else current["deadline"]
            connection.execute(
                "UPDATE tasks SET status=?, deadline=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (status, deadline, task_id),
            )
            connection.execute(
                "INSERT INTO task_events(task_id,event_type,old_value,new_value,evidence,confirmed) VALUES (?,?,?,?,?,1)",
                (task_id, event_type, old_value, deadline if event_type == "rescheduled" else status, evidence),
            )

    def list_tasks(self, status: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM tasks"
        parameters: tuple[Any, ...] = ()
        if status:
            query += " WHERE status = ?"
            parameters = (status,)
        query += " ORDER BY CASE WHEN deadline IS NULL THEN 1 ELSE 0 END, deadline, id DESC"
        with self.connect() as connection:
            return [dict(row) for row in connection.execute(query, parameters).fetchall()]

    def history(self, task_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM task_events WHERE task_id=? ORDER BY id", (task_id,)
            ).fetchall()
        return [dict(row) for row in rows]
