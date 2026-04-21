"""Auto-archive unreviewed briefs — PRD §15.3."""

from __future__ import annotations

from ..db import connection
from ..settings import SignalSettings, get_settings


def archive_stale_briefs(*, days: int = 14, settings: SignalSettings | None = None) -> int:
    s = settings or get_settings()
    if not s.database_url:
        return 0
    n = 0
    with connection(autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE cluster_briefs b
                SET archived_at = NOW()
                WHERE b.archived_at IS NULL
                  AND b.superseded_by IS NULL
                  AND b.generated_at < NOW() - make_interval(days => %s)
                  AND NOT EXISTS (SELECT 1 FROM decisions d WHERE d.brief_id = b.id)
                RETURNING b.id
                """,
                (days,),
            )
            rows = cur.fetchall()
            n = len(rows)
    return int(n)
