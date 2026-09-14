"""Persistence layer. Uses SQLAlchemy so the same code works against a local SQLite file
(default, fine for local/VPS cron) or a hosted Postgres DB via DATABASE_URL (required for
GitHub Actions, since the runner's disk does not persist between runs -- see README).
"""
from __future__ import annotations

import datetime as dt
from contextlib import contextmanager
from zoneinfo import ZoneInfo

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    TypeDecorator,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


# Human-readable league name per The Odds API sport_key, for Telegram alerts and /status --
# makes it obvious at a glance which sportsbook tab to search without decoding the raw key.
# Only needs entries for config/settings.yaml's `sports:` list; Alert.league_display() falls
# back to the raw key for anything not listed here (e.g. a sport removed from config after
# alerts on it were already stored).
LEAGUE_LABELS = {
    "americanfootball_nfl": "NFL",
    "americanfootball_ncaaf": "NCAAF",
    "americanfootball_cfl": "CFL",
    "basketball_nba": "NBA",
    "basketball_ncaab": "NCAAB",
    "icehockey_nhl": "NHL",
    "baseball_mlb": "MLB",
    "mma_mixed_martial_arts": "MMA",
    "soccer_epl": "EPL",
    "soccer_spain_la_liga": "La Liga",
    "soccer_germany_bundesliga": "Bundesliga",
    "soccer_italy_serie_a": "Serie A",
    "soccer_usa_mls": "MLS",
    "soccer_uefa_champs_league": "Champions League",
}


def local_time_str(commence_time: dt.datetime, timezone: str) -> str:
    """Formats a game's start time in the given local timezone, e.g. "Sun 1:00pm ET" --
    shared by Telegram scan alerts and /status so both show the same at-a-glance sense of
    when a bet will settle. `timezone` is an IANA zone name (config/settings.yaml
    `scheduling.timezone`, "America/Toronto"); the "ET" suffix is hardcoded since that's the
    only timezone this bot is configured for today."""
    local = commence_time.astimezone(ZoneInfo(timezone))
    hour12 = local.hour % 12 or 12
    ampm = "am" if local.hour < 12 else "pm"
    return f"{local.strftime('%a')} {hour12}:{local.minute:02d}{ampm} ET"


class AwareDateTime(TypeDecorator):
    """DateTime(timezone=True) doesn't actually round-trip tzinfo through SQLite -- it has
    no native timezone-aware type, so a stored aware datetime silently comes back naive
    (confirmed: tzinfo is None after a commit+reload). That crashes the very first
    naive-vs-aware subtraction against an aware "now" (e.g. scheduler.should_alert comparing
    against a previously-alerted Alert's last_alerted_at), which only bit us once alerts
    started actually being re-evaluated across scans on the VPS's local SQLite DB -- it
    never showed up under Postgres, which preserves tzinfo correctly. Always returns a
    UTC-aware datetime on read regardless of backend, so callers never have to think about
    which DB is behind DATABASE_URL."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_result_value(self, value: dt.datetime | None, dialect) -> dt.datetime | None:
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=dt.timezone.utc)
        return value


class KVState(Base):
    """Generic key/value store: telegram update offset, current bankroll, etc."""

    __tablename__ = "kv_state"
    key = Column(String, primary_key=True)
    value = Column(String, nullable=False)
    updated_at = Column(AwareDateTime, default=utcnow, onupdate=utcnow)


class BankrollHistory(Base):
    __tablename__ = "bankroll_history"
    id = Column(Integer, primary_key=True, autoincrement=True)
    amount = Column(Float, nullable=False)
    reason = Column(String, nullable=False)
    created_at = Column(AwareDateTime, default=utcnow)


class Alert(Base):
    """One +EV opportunity the bot found and (maybe) notified about. Also doubles as the
    "bet slip" the user acts on via Telegram commands (/placed, /skip, /settle)."""

    __tablename__ = "alerts"
    __table_args__ = (
        UniqueConstraint(
            "event_id", "market", "outcome_name", "point", "bookmaker_key", "participant",
            name="uq_alert_identity",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String, nullable=False)
    sport_key = Column(String, nullable=False)
    commence_time = Column(AwareDateTime, nullable=False)
    home_team = Column(String, nullable=False)
    away_team = Column(String, nullable=False)
    market = Column(String, nullable=False)  # h2h | spreads | totals | player_* | batter_* | ...
    outcome_name = Column(String, nullable=False)
    point = Column(Float, nullable=True)  # spread/total/prop line, null for h2h and Yes/No props
    # Player name for prop markets, "" for team markets (h2h/spreads/totals). Deliberately
    # not nullable: Postgres treats NULL != NULL in a unique constraint, which would
    # silently stop enforcing uniqueness among all the (NULL-participant) team-market
    # alerts sharing this row's other columns. "" behaves like any other equal value on
    # both SQLite and Postgres, so the constraint below works the same as it always has for
    # team markets, and correctly as intended for props.
    participant = Column(String, nullable=False, default="")
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
    # Set once `auto_settle_pending` sees this bet's event finish but can't grade the
    # market itself (player props -- /scores never returns player-level box scores). Guards
    # the one-time "needs manual /settle" nudge from re-sending every scan thereafter; see
    # betbot.settlement.auto_settle_pending.
    settlement_reminder_sent_at = Column(AwareDateTime, nullable=True)

    first_seen_at = Column(AwareDateTime, default=utcnow)
    last_alerted_at = Column(AwareDateTime, nullable=True)
    updated_at = Column(AwareDateTime, default=utcnow, onupdate=utcnow)

    def outcome_display(self) -> str:
        """Outcome name with the spread/total/prop line attached, e.g. "Bills -3.5" or
        "Over 224.5", prefixed with the player name for props (e.g. "P. Mahomes Over
        274.5") -- bare outcome_name for h2h, where there's no line to show. This is the
        one place every caller (Telegram alerts, /status, the daily report) renders an
        outcome, so nothing else needs to know about participant/point formatting."""
        if self.market == "spreads" and self.point is not None:
            base = f"{self.outcome_name} {self.point:+g}"
        elif self.point is not None:  # totals, and Over/Under player props
            base = f"{self.outcome_name} {self.point:g}"
        else:
            base = self.outcome_name  # h2h, and Yes/No player props (e.g. anytime TD)
        return f"{self.participant} {base}" if self.participant else base

    def book_odds_display(self) -> str:
        """book_odds formatted as American odds (e.g. "+150", "-110") for display only --
        stored value and all EV/Kelly math stay in decimal, since that's the format The
        Odds API returns and the formulas in devig.py/ev.py/kelly.py are written for."""
        return american_odds(self.book_odds)

    def true_odds_display(self) -> str:
        """The devigged "fair" probability (true_prob) converted to American odds for
        display, e.g. true_prob=0.55 -> decimal 1.818 -> "-122". Lets a user compare the
        line we're betting against what we think it's actually worth, same format as
        book_odds_display -- never feed this back into EV/Kelly math, which uses true_prob
        directly."""
        return american_odds(1.0 / self.true_prob)

    def league_display(self) -> str:
        """Human-readable league name (e.g. "NFL") for sport_key, so alerts/`/status` are
        quick to place without decoding the raw Odds API key."""
        return LEAGUE_LABELS.get(self.sport_key, self.sport_key)


def american_odds(decimal_odds: float) -> str:
    """Convert decimal odds to an American odds display string, e.g. 2.50 -> "+150",
    1.91 -> "-110". Display-only conversion -- never feed the result back into decimal-odds
    math (devig/ev/kelly)."""
    if decimal_odds >= 2.0:
        return f"+{round((decimal_odds - 1) * 100):.0f}"
    return f"{round(-100 / (decimal_odds - 1)):.0f}"


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
