"""Decision throughput vs brief surfacing (PRD §15.4)."""

from __future__ import annotations

from typing import Any

from psycopg.rows import dict_row

from ..db import connection
from ..settings import SignalSettings, get_settings


def compute_action_within_7d(window_days: int, settings: SignalSettings | None = None) -> dict[str, Any]:
    """
    Share of current (non-superseded, non-archived) briefs generated in the rolling window
    that received a decision within 7 days of `generated_at`.
    """
    s = settings or get_settings()
    if not s.database_url:
        return {
            "window_days": window_days,
            "total_briefs": 0,
            "acted_within_7d": 0,
            "pct": None,
            "error": "DATABASE_URL required",
        }
    wd = max(1, int(window_days))
    with connection(autocommit=True) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                WITH briefs AS (
                  SELECT b.id, b.generated_at
                  FROM cluster_briefs b
                  WHERE b.superseded_by IS NULL
                    AND (b.archived_at IS NULL)
                    AND b.generated_at >= NOW() - make_interval(days => %s)
                )
                SELECT
                  COUNT(*)::int AS total,
                  COUNT(*) FILTER (
                    WHERE EXISTS (
                      SELECT 1 FROM decisions d
                      WHERE d.brief_id = briefs.id
                        AND d.decided_at IS NOT NULL
                        AND d.decided_at <= briefs.generated_at + INTERVAL '7 days'
                        AND d.decided_at >= briefs.generated_at
                    )
                  )::int AS acted
                FROM briefs
                """,
                (wd,),
            )
            row = cur.fetchone() or {}
    total = int(row.get("total") or 0)
    acted = int(row.get("acted") or 0)
    pct = (100.0 * acted / total) if total else None
    return {
        "window_days": wd,
        "total_briefs": total,
        "acted_within_7d": acted,
        "pct": round(pct, 2) if pct is not None else None,
        "below_target_60pct": (pct is not None and pct < 60.0),
    }
