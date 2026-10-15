"""Regression coverage for the additive legacy SQLite upgrade."""

import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config

from backend.app.database import Database
from backend.app.settings import Settings, get_settings


def test_legacy_sqlite_rows_survive_compatibility_upgrade(tmp_path: Path):
    path = tmp_path / "legacy.db"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY,
            text TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            source TEXT NOT NULL DEFAULT 'local'
        );
        CREATE TABLE tasks (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            deadline TEXT,
            original_message_id INTEGER REFERENCES messages(id),
            model_version TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE task_events (
            id INTEGER PRIMARY KEY,
            task_id INTEGER NOT NULL REFERENCES tasks(id),
            event_type TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            evidence TEXT,
            confirmed INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE model_predictions (
            id INTEGER PRIMARY KEY,
            message_id INTEGER NOT NULL REFERENCES messages(id),
            model_version TEXT NOT NULL,
            intent TEXT NOT NULL,
            confidence REAL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE user_corrections (
            id INTEGER PRIMARY KEY,
            prediction_id INTEGER REFERENCES model_predictions(id),
            corrected_intent TEXT,
            corrected_payload_json TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO messages (id, text) VALUES (7, 'رسالة محفوظة');
        INSERT INTO model_predictions
            (id, message_id, model_version, intent, payload_json)
            VALUES (9, 7, 'intent_baseline', 'info_only', '{}');
        """
    )
    connection.commit()
    connection.close()

    database = Database(Settings(database_url=f"sqlite:///{path}"))
    database.initialize()
    with database.engine.connect() as upgraded:
        assert upgraded.exec_driver_sql("SELECT text FROM messages WHERE id=7").scalar_one() == "رسالة محفوظة"
        assert upgraded.exec_driver_sql("SELECT COUNT(*) FROM model_predictions").scalar_one() == 1
        assert upgraded.exec_driver_sql("SELECT COUNT(*) FROM conversations").scalar_one() == 0
        message_columns = {
            row[1] for row in upgraded.exec_driver_sql("PRAGMA table_info(messages)")
        }
        correction_columns = {
            row[1] for row in upgraded.exec_driver_sql("PRAGMA table_info(user_corrections)")
        }
        assert {"conversation_id", "updated_at"}.issubset(message_columns)
        assert {"message_id", "reviewer", "review_status", "notes"}.issubset(correction_columns)
        assert upgraded.exec_driver_sql(
            "SELECT COUNT(*) FROM messages WHERE updated_at IS NULL"
        ).scalar_one() == 0
    database.engine.dispose()


def test_alembic_upgrades_empty_sqlite_database_to_head(
    tmp_path: Path, monkeypatch
):
    path = tmp_path / "fresh.db"
    monkeypatch.setenv("FIL_AI_DATABASE_URL", f"sqlite:///{path}")
    get_settings.cache_clear()
    try:
        config = Config("backend/alembic.ini")
        command.upgrade(config, "head")
    finally:
        get_settings.cache_clear()

    connection = sqlite3.connect(path)
    try:
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()
        assert revision == ("20261014_0002",)
        task_event_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(task_events)")
        }
        task_event_foreign_keys = {
            (row[3], row[2]) for row in connection.execute("PRAGMA foreign_key_list(task_events)")
        }
        assert {"summary", "related_message_id", "model_prediction_id"}.issubset(
            task_event_columns
        )
        assert ("related_message_id", "messages") in task_event_foreign_keys
        assert ("model_prediction_id", "model_predictions") in task_event_foreign_keys
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    finally:
        connection.close()
