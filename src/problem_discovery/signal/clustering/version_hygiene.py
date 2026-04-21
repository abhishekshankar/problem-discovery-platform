"""Mixed extractor-version detection per cluster (PRD §14.4)."""

from __future__ import annotations

from typing import Any

from ..db import connection
from ..settings import SignalSettings, get_settings


def flag_mixed_version_clusters(settings: SignalSettings | None = None) -> dict[str, Any]:
    """
    Set clusters.version_status = 'mixed' when members map to >1 distinct extraction_runs.extractor_version.
    Otherwise 'clean'. Empty clusters are 'clean'.
    """
    s = settings or get_settings()
    if not s.database_url:
        return {"updated": 0, "error": "DATABASE_URL required"}
    with connection(autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH v AS (
                  SELECT m.cluster_id,
                         COUNT(DISTINCT er.extractor_version)::int AS n_versions
                  FROM cluster_members m
                  JOIN extracted_problems e ON e.id = m.extracted_problem_id
                  LEFT JOIN extraction_runs er ON er.id = e.extraction_run_id
                  GROUP BY m.cluster_id
                )
                UPDATE clusters c
                SET version_status = CASE WHEN COALESCE(v.n_versions, 0) > 1 THEN 'mixed' ELSE 'clean' END
                FROM v
                WHERE c.id = v.cluster_id
                  AND c.status NOT IN ('archived')
                """
            )
            n_member = cur.rowcount or 0
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE clusters c
                SET version_status = 'clean'
                WHERE c.status NOT IN ('archived')
                  AND NOT EXISTS (SELECT 1 FROM cluster_members m WHERE m.cluster_id = c.id)
                """
            )
            n_empty = cur.rowcount or 0
    return {"clusters_with_members_updated": n_member, "empty_clusters_marked_clean": n_empty}
