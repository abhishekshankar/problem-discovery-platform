"""Daily digest email — PRD §12.3."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from psycopg.rows import dict_row

from ..db import connection
from ..settings import SignalSettings, get_settings
from .notify import send_email


def send_daily_digest(settings: SignalSettings | None = None) -> dict[str, int]:
    s = settings or get_settings()
    if not s.database_url or not s.digest_email_to:
        return {"sent": 0}

    since = datetime.now(timezone.utc) - timedelta(hours=24)
    lines: list[str] = []
    with connection(autocommit=True) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT c.canonical_statement, b.generated_at
                FROM cluster_briefs b
                JOIN clusters c ON c.id = b.cluster_id
                WHERE b.superseded_by IS NULL
                  AND b.archived_at IS NULL
                  AND b.generated_at >= %s
                ORDER BY b.generated_at DESC
                LIMIT 20
                """,
                (since,),
            )
            for row in cur.fetchall():
                lines.append(f"- {row.get('canonical_statement') or 'Cluster'} ({row['generated_at']})")

    body = "Signal — surfaced briefs (24h)\n\n" + ("\n".join(lines) if lines else "(none)")
    ok = send_email("Signal daily digest — surfaced briefs", body, settings=s, to=s.digest_email_to)
    return {"sent": 1 if ok else 0, "count": len(lines)}
