"""Copy existing SQLite records into PostgreSQL without altering SQLite."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from sqlalchemy import MetaData, create_engine, inspect, select, text
from sqlalchemy.dialects.postgresql import insert

from backend.app.database import Database
from backend.app.settings import Settings

ROOT = Path(__file__).resolve().parents[2]
TABLE_ORDER = [
    "conversations", "messages", "tasks", "task_events", "model_predictions", "user_corrections"
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite", default=f"sqlite:///{ROOT / 'data/fil_ai.db'}")
    parser.add_argument("--postgres", default=os.getenv("FIL_AI_DATABASE_URL"))
    args = parser.parse_args()
    if not args.postgres or not args.postgres.startswith("postgresql"):
        raise SystemExit("Provide a PostgreSQL FIL_AI_DATABASE_URL or --postgres URL")
    source_db = Database(Settings(database_url=args.sqlite))
    source_db.initialize()
    source, target = source_db.engine, create_engine(args.postgres, pool_pre_ping=True)
    target_tables = set(inspect(target).get_table_names())
    missing = set(TABLE_ORDER).difference(target_tables)
    if missing:
        raise SystemExit(f"PostgreSQL schema is missing {sorted(missing)}; run Alembic first")
    source_meta, target_meta = MetaData(), MetaData()
    source_meta.reflect(source)
    target_meta.reflect(target)
    copied = {}
    with source.connect() as source_connection, target.begin() as target_connection:
        for name in TABLE_ORDER:
            rows = [dict(row._mapping) for row in source_connection.execute(select(source_meta.tables[name]))]
            if rows:
                statement = insert(target_meta.tables[name]).values(rows).on_conflict_do_nothing(index_elements=["id"])
                result = target_connection.execute(statement)
                copied[name] = result.rowcount
                target_connection.execute(
                    text(
                        "SELECT setval(pg_get_serial_sequence(:table_name, 'id'), "
                        "COALESCE((SELECT MAX(id) FROM " + name + "), 1), true)"
                    ),
                    {"table_name": name},
                )
            else:
                copied[name] = 0
    print("Copy complete; SQLite was not modified or deleted.")
    for table, count in copied.items():
        print(f"{table}: {count} new rows")


if __name__ == "__main__":
    main()
