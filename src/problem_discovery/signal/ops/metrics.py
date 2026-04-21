"""review_metrics_daily — PRD §15."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from ..db import connection
from ..settings import SignalSettings, get_settings


def _today_utc() -> date:
    return datetime.now(timezone.utc).date()


def bump_review_metrics(
    *,
    briefs_surfaced: int = 0,
    briefs_opened: int = 0,
    decisions_made: int = 0,
    day: date | None = None,
    settings: SignalSettings | None = None,
) -> None:
    s = settings or get_settings()
    if not s.database_url:
        return
    d = day or _today_utc()
    with connection(autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO review_metrics_daily (day, briefs_surfaced, briefs_opened, decisions_made)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (day) DO UPDATE SET
                  briefs_surfaced = review_metrics_daily.briefs_surfaced + EXCLUDED.briefs_surfaced,
                  briefs_opened = review_metrics_daily.briefs_opened + EXCLUDED.briefs_opened,
                  decisions_made = review_metrics_daily.decisions_made + EXCLUDED.decisions_made
                """,
                (d, briefs_surfaced, briefs_opened, decisions_made),
            )
