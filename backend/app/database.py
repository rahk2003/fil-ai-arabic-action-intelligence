"""Database engine, sessions, and non-destructive SQLite compatibility upgrade."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from .models import Base
from .settings import Settings


SQLITE_COLUMN_UPGRADES = {
    "messages": {
        "conversation_id": "INTEGER REFERENCES conversations(id) ON DELETE SET NULL",
        # SQLite cannot add a non-constant CURRENT_TIMESTAMP default via ALTER.
        # Existing rows are backfilled below and ORM writes provide the value.
        "updated_at": "TEXT",
    },
    "tasks": {
        "conversation_id": "INTEGER REFERENCES conversations(id) ON DELETE SET NULL",
        "priority": "TEXT NOT NULL DEFAULT 'medium'",
        "description": "TEXT",
        "workflow_status": "TEXT NOT NULL DEFAULT 'pending'",
        "original_deadline": "TEXT",
    },
    "task_events": {
        "summary": "TEXT",
        "related_message_id": "INTEGER REFERENCES messages(id) ON DELETE SET NULL",
        "model_prediction_id": "INTEGER REFERENCES model_predictions(id) ON DELETE SET NULL",
    },
    "user_corrections": {
        "message_id": "INTEGER REFERENCES messages(id) ON DELETE SET NULL",
        "reviewer": "TEXT",
        "review_status": "TEXT NOT NULL DEFAULT 'reviewed_candidate'",
        "notes": "TEXT",
    },
}


class Database:
    def __init__(self, settings: Settings):
        self.settings = settings
        kwargs = {"echo": settings.sql_echo, "pool_pre_ping": True}
        if settings.is_sqlite:
            kwargs["connect_args"] = {"check_same_thread": False}
        self.engine: Engine = create_engine(settings.database_url, **kwargs)
        if settings.is_sqlite:
            event.listen(self.engine, "connect", self._enable_sqlite_foreign_keys)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False)

    @staticmethod
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    def initialize(self) -> None:
        if self.settings.is_sqlite:
            self._upgrade_existing_sqlite()
            Base.metadata.create_all(self.engine)
        elif self.settings.auto_create_db:
            Base.metadata.create_all(self.engine)

    def _upgrade_existing_sqlite(self) -> None:
        with self.engine.begin() as connection:
            connection.exec_driver_sql(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY,
                    title TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            existing_tables = {
                row[0]
                for row in connection.exec_driver_sql(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            # A brand-new database contains only the conversations table created
            # above.  Let SQLAlchemy create the rest instead of issuing legacy
            # compatibility statements against tables that do not exist yet.
            if "messages" not in existing_tables:
                return
            for table, additions in SQLITE_COLUMN_UPGRADES.items():
                if table not in existing_tables:
                    continue
                existing_columns = {
                    row[1]
                    for row in connection.exec_driver_sql(f"PRAGMA table_info({table})")
                }
                for column, definition in additions.items():
                    if column not in existing_columns:
                        connection.exec_driver_sql(
                            f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
                        )
            connection.exec_driver_sql(
                "UPDATE messages SET updated_at = COALESCE(updated_at, created_at)"
            )
            if "tasks" in existing_tables:
                connection.exec_driver_sql(
                    "UPDATE tasks SET original_deadline = COALESCE(original_deadline, deadline)"
                )
                connection.exec_driver_sql(
                    "UPDATE tasks SET workflow_status = status "
                    "WHERE workflow_status IS NULL OR workflow_status = 'pending'"
                )
            indexes = [
                "CREATE INDEX IF NOT EXISTS ix_messages_conversation_id ON messages(conversation_id)",
                "CREATE INDEX IF NOT EXISTS ix_tasks_conversation_id ON tasks(conversation_id)",
                "CREATE INDEX IF NOT EXISTS ix_tasks_status_deadline ON tasks(status, deadline)",
                "CREATE INDEX IF NOT EXISTS ix_task_events_task_created ON task_events(task_id, created_at)",
                "CREATE INDEX IF NOT EXISTS ix_task_events_related_message_id ON task_events(related_message_id)",
                "CREATE INDEX IF NOT EXISTS ix_task_events_model_prediction_id ON task_events(model_prediction_id)",
                "CREATE INDEX IF NOT EXISTS ix_model_predictions_message_id ON model_predictions(message_id)",
                "CREATE INDEX IF NOT EXISTS ix_user_corrections_review_status ON user_corrections(review_status, created_at)",
            ]
            for statement in indexes:
                connection.exec_driver_sql(statement)

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def ping(self) -> bool:
        with self.engine.connect() as connection:
            return connection.execute(text("SELECT 1")).scalar_one() == 1
