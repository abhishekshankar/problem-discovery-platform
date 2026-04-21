"""Collector health — PRD §7.6."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from psycopg.rows import dict_row

from ..db import connection
from ..settings import SignalSettings, get_settings
from .notify import send_email, send_slack_message


def run_collector_health_check(settings: SignalSettings | None = None) -> dict[str, Any]:
    """Alert if latest run <20% of 7d MA volume or 3 consecutive failures; auto-disable collector."""
    s = settings or get_settings()
    if not s.database_url:
        raise RuntimeError("DATABASE_URL is required")

    now = datetime.now(timezone.utc)
    alerts: list[str] = []
    disabled: list[str] = []

    with connection(autocommit=True) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT c.id, c.name, col.id AS collector_db_id, col.name AS collector_name, col.status
                FROM sources c
                JOIN collectors col ON col.source_id = c.id
                """
            )
            collectors = cur.fetchall()

        for row in collectors:
            cid = int(row["collector_db_id"])
            cname = str(row["collector_name"])
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT record_count, status, completed_at
                    FROM collector_runs
                    WHERE collector_id = %s AND completed_at IS NOT NULL
                    ORDER BY completed_at DESC
                    LIMIT 10
                    """,
                    (cid,),
                )
                runs = cur.fetchall()
            if not runs:
                continue
            counts = [int(r["record_count"] or 0) for r in runs[1:8] if r.get("completed_at")]
            ma = sum(counts) / max(len(counts), 1) if counts else 0
            last = runs[0]
            last_n = int(last["record_count"] or 0)
            last_st = str(last.get("status") or "")

            if ma > 0 and last_n < 0.2 * ma:
                alerts.append(f"{cname}: volume {last_n} < 20% of 7-run MA ~{ma:.1f}")

            fails = [str(r.get("status") or "") != "ok" for r in runs[:3]]
            if len(fails) == 3 and all(fails):
                alerts.append(f"{cname}: 3 consecutive failed runs")
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE collectors SET status = 'disabled' WHERE id = %s",
                        (cid,),
                    )
                disabled.append(cname)

    msg = "\n".join(alerts) if alerts else "All collectors within thresholds."
    if alerts:
        send_slack_message(f"Signal collector health:\n{msg}", settings=s)
        send_email("Signal collector health", msg, settings=s)

    return {"alerts": alerts, "disabled_collectors": disabled, "checked_at": now.isoformat()}
