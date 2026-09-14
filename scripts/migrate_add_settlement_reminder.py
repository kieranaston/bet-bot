#!/usr/bin/env python3
"""One-off migration: adds the `alerts.settlement_reminder_sent_at` column, needed for the
manual-settlement reminder (see betbot.settlement.auto_settle_pending) that nudges the user
once a player-prop bet's game ends, since those can never be auto-graded from /scores.

Base.metadata.create_all (what Database.__init__ runs on every startup) only creates tables
that don't exist yet -- it never alters an existing table's columns -- so a DB created before
this rollout needs this script run once. Idempotent: no-ops if the column already exists.
Unlike migrate_add_participant.py, this is a plain nullable column with no constraint to
rebuild, so a simple ALTER TABLE ADD COLUMN works on both SQLite and Postgres directly.

Run this against the VPS's local SQLite file (the only real database -- see CLAUDE.md,
Supabase/Postgres is no longer used) before deploying the new code. A local dev checkout's
own `data/betbot.db` is a separate file from the VPS's -- running this locally does not
migrate the VPS's copy.

Usage:
    python scripts/migrate_add_settlement_reminder.py       # uses .env's DATABASE_URL
"""
from __future__ import annotations

from sqlalchemy import create_engine, inspect, text

from betbot.config import Secrets


def main() -> None:
    secrets = Secrets.from_env()
    engine = create_engine(secrets.database_url, future=True)
    inspector = inspect(engine)

    if "alerts" not in inspector.get_table_names():
        print("No `alerts` table yet -- nothing to migrate (a fresh run creates it with "
              "the new schema already).")
        return

    existing_columns = [col["name"] for col in inspector.get_columns("alerts")]
    if "settlement_reminder_sent_at" in existing_columns:
        print("`alerts.settlement_reminder_sent_at` already exists -- nothing to do.")
        return

    dialect = engine.dialect.name
    print(f"Migrating `alerts` on dialect={dialect!r} ...")
    column_type = "TIMESTAMP WITH TIME ZONE" if dialect == "postgresql" else "DATETIME"

    with engine.begin() as conn:
        conn.execute(text(
            f"ALTER TABLE alerts ADD COLUMN settlement_reminder_sent_at {column_type}"
        ))

    print("Migration complete: `alerts.settlement_reminder_sent_at` added.")


if __name__ == "__main__":
    main()
