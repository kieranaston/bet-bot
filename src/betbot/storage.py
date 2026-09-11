"""Persistence layer. Uses SQLAlchemy so the same code works against a local SQLite file
(default, fine for local/VPS cron) or a hosted Postgres DB via DATABASE_URL (required for
GitHub Actions, since the runner's disk does not persist between runs -- see README).
"""
from __future__ import annotations

import datetime as dt
from contextlib import contextmanager

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class KVState(Base):
    """Generic key/value store: telegram update offset, current bankroll, etc."""

    __tablename__ = "kv_state"
    key = Column(String, primary_key=True)
    value = Column(String, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class BankrollHistory(Base):
    __tablename__ = "bankroll_history"
    id = Column(Integer, primary_key=True, autoincrement=True)
    amount = Column(Float, nullable=False)
    reason = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)


class Alert(Base):
    """One +EV opportunity the bot found and (maybe) notified about. Also doubles as the
    "bet slip" the user acts on via Telegram commands (/placed, /skip, /settle)."""

    __tablename__ = "alerts"
    __table_args__ = (
        UniqueConstraint(
            "event_id", "market", "outcome_name", "point", "bookmaker_key",
            name="uq_alert_identity",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String, nullable=False)
    sport_key = Column(String, nullable=False)
    commence_time = Column(DateTime(timezone=True), nullable=False)
    home_team = Column(String, nullable=False)
    away_team = Column(String, nullable=False)
    market = Column(String, nullable=False)  # h2h | spreads | totals
    outcome_name = Column(String, nullable=False)
    point = Column(Float, nullable=True)  # spread/total line, null for h2h
    bookmaker_key = Column(String, nullable=False)
    book_odds = Column(Float, nullable=False)
    sharp_book_key = Column(String, nullable=False)
    true_prob = Column(Float, nullable=False)
    ev_pct = Column(Float, nullable=False)
    recommended_stake = Column(Float, nullable=False)
    deep_link = Column(String, nullable=True)  # direct betslip/event link, if the book offers one

    # Lifecycle: new -> notified -> placed|skipped -> settled_win|settled_loss|settled_push
    status = Column(String, nullable=False, default="new")
    placed_stake = Column(Float, nullable=True)
    closing_odds = Column(Float, nullable=True)  # for CLV, filled in at /settle time
    profit = Column(Float, nullable=True)  # realized profit/loss once settled

    first_seen_at = Column(DateTime(timezone=True), default=utcnow)
    last_alerted_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Database:
    def __init__(self, database_url: str) -> None:
        self.engine = create_engine(database_url, future=True)
        self.Session = sessionmaker(bind=self.engine, future=True)
        Base.metadata.create_all(self.engine)

    @contextmanager
    def session(self):
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_kv(self, key: str, default: str | None = None) -> str | None:
        with self.session() as s:
            row = s.get(KVState, key)
            return row.value if row else default

    def set_kv(self, key: str, value: str) -> None:
        with self.session() as s:
            row = s.get(KVState, key)
            if row:
                row.value = value
            else:
                s.add(KVState(key=key, value=value))

    def current_bankroll(self, starting_amount: float) -> float:
        with self.session() as s:
            latest = (
                s.query(BankrollHistory)
                .order_by(BankrollHistory.created_at.desc())
                .first()
            )
            if latest:
                return latest.amount
            s.add(BankrollHistory(amount=starting_amount, reason="initial"))
            return starting_amount

    def set_bankroll(self, amount: float, reason: str) -> None:
        with self.session() as s:
            s.add(BankrollHistory(amount=amount, reason=reason))
