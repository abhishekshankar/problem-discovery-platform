"""Throughput calibration — PRD §15.2."""

from __future__ import annotations

from typing import Any

from psycopg.rows import dict_row

from ..db import connection
from ..settings import SignalSettings, get_settings


def adjust_threshold(current_threshold: float, metrics_28d: dict[str, float]) -> float:
    """PRD §15.2 — weekly job adjusts ranker sigma threshold."""
    surfaced = max(metrics_28d.get("briefs_surfaced", 0), 1)
    opened = metrics_28d.get("briefs_opened", 0)
    decided = metrics_28d.get("decisions_made", 0)
    review_rate = opened / surfaced
    decision_rate = decided / max(opened, 1)
    if review_rate < 0.70:
        return current_threshold * 1.10
    if review_rate > 0.95 and decision_rate > 0.80:
        return current_threshold * 0.95
    return current_threshold


def run_weekly_calibration(settings: SignalSettings | None = None) -> dict[str, Any]:
    s = settings or get_settings()
    if not s.database_url:
        raise RuntimeError("DATABASE_URL is required")

    current = 1.5
    new_t = current
    metrics: dict[str, float] = {}
    with connection(autocommit=True) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                  COALESCE(SUM(briefs_surfaced), 0)::float AS briefs_surfaced,
                  COALESCE(SUM(briefs_opened), 0)::float AS briefs_opened,
                  COALESCE(SUM(decisions_made), 0)::float AS decisions_made
                FROM review_metrics_daily
                WHERE day >= CURRENT_DATE - INTERVAL '28 days'
                """
            )
            m = cur.fetchone() or {}
            metrics = {k: float(m[k] or 0) for k in ("briefs_surfaced", "briefs_opened", "decisions_made")}
            cur.execute(
                "SELECT deviation_sigma_threshold, surfacing_cap_per_day FROM ranker_settings WHERE singleton_lock = 1"
            )
            rs = cur.fetchone()
            if rs:
                current = float(rs["deviation_sigma_threshold"])
            new_t = adjust_threshold(current, metrics)
            cur.execute(
                """
                UPDATE ranker_settings
                SET deviation_sigma_threshold = %s, updated_at = NOW()
                WHERE singleton_lock = 1
                """,
                (new_t,),
            )
    return {
        "previous_threshold": current,
        "new_threshold": new_t,
        "metrics_28d": metrics,
        "formula": "PRD §15.2",
    }
