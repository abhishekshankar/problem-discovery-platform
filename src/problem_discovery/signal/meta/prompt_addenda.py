"""Weekly prompt addenda candidates — PRD §16.1."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from psycopg.rows import dict_row

from ..db import connection
from ..settings import SignalSettings, get_settings


def propose_feedback_patterns(settings: SignalSettings | None = None) -> dict[str, Any]:
    """Summarize last 30 rejection reasons into inactive feedback_patterns rows for human review."""
    s = settings or get_settings()
    if not s.database_url:
        raise RuntimeError("DATABASE_URL is required")

    since = datetime.now(timezone.utc) - timedelta(days=30)
    created: list[str] = []
    rows: list[Any] = []
    with connection(autocommit=True) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT reason_code, COUNT(*)::int AS n
                FROM decisions
                WHERE action = 'reject' AND decided_at >= %s AND reason_code IS NOT NULL
                GROUP BY reason_code
                ORDER BY n DESC
                LIMIT 10
                """,
                (since,),
            )
            rows = list(cur.fetchall())
        for row in rows:
            code = str(row["reason_code"])
            n = int(row["n"])
            desc = f"Top rejection pattern last 30d: {code} (n={n})"
            addendum = f"Avoid surfacing clusters that match historical rejection pattern: {code}."
            pid = str(uuid.uuid4())
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO feedback_patterns (
                      id, derived_at, pattern_description, affected_layer, prompt_addendum, active, human_reviewed
                    )
                    VALUES (%s::uuid, NOW(), %s, %s, %s, FALSE, FALSE)
                    """,
                    (pid, desc, "extractor", addendum),
                )
            created.append(pid)
    return {"pattern_ids": created, "from_rejections": [dict(r) for r in rows], "note": "Review and set active=TRUE after human approval"}
