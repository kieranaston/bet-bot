#!/usr/bin/env python3
"""One-off migration for the player-props rollout: adds the `alerts.participant` column
and rebuilds `uq_alert_identity` to include it, on an *existing* database.

Base.metadata.create_all (what Database.__init__ runs on every startup) only creates
tables that don't exist yet -- it never alters an existing table's columns or constraints
-- so a DB created before this rollout needs this script run once. Idempotent: no-ops if
`participant` already exists. Existing alert/settlement history is preserved either way.

Run this against the VPS's local SQLite file (the only real database as of 2026-09-13 --
Supabase/Postgres is no longer used, see README's GitHub Actions backup section) before
deploying the new code. A local dev checkout's own `data/betbot.db` is a separate file from
the VPS's -- running this locally does not migrate the VPS's copy.

Usage:
    python scripts/migrate_add_participant.py                # uses .env's DATABASE_URL
    DATABASE_URL=postgresql://... python scripts/migrate_add_participant.py
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
    if "participant" in existing_columns:
        print("`alerts.participant` already exists -- nothing to do.")
        return

    dialect = engine.dialect.name
    print(f"Migrating `alerts` on dialect={dialect!r} ...")

    with engine.begin() as conn:
        if dialect == "postgresql":
            conn.execute(text(
                "ALTER TABLE alerts ADD COLUMN participant VARCHAR NOT NULL DEFAULT ''"
            ))
            conn.execute(text("ALTER TABLE alerts DROP CONSTRAINT IF EXISTS uq_alert_identity"))
            conn.execute(text(
                "ALTER TABLE alerts ADD CONSTRAINT uq_alert_identity UNIQUE "
                "(event_id, market, outcome_name, point, bookmaker_key, participant)"
            ))
        elif dialect == "sqlite":
            # SQLite can't alter a UNIQUE constraint in place -- rebuild: rename the old
            # table aside, let SQLAlchemy recreate `alerts` from the current (already
            # participant-aware) model, copy every existing row across naming columns
            # explicitly (old rows get participant=''), then drop the renamed original.
            from betbot.storage import Base  # only needed on this branch

            conn.execute(text("ALTER TABLE alerts RENAME TO alerts_old"))
            Base.metadata.create_all(conn)
            col_list = ", ".join(existing_columns)
            conn.execute(text(
                f"INSERT INTO alerts ({col_list}, participant) "
                f"SELECT {col_list}, '' FROM alerts_old"
            ))
            conn.execute(text("DROP TABLE alerts_old"))
        else:
            raise RuntimeError(f"Unsupported dialect for this migration: {dialect}")

    print("Migration complete: `alerts.participant` added, uq_alert_identity updated.")


if __name__ == "__main__":
    main()
