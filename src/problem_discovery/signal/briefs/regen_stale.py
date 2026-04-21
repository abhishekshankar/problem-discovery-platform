"""Regenerate briefs when cluster membership grew ≥20% since last brief (PRD §11.1)."""

from __future__ import annotations

from typing import Any

from psycopg.rows import dict_row

from ..db import connection
from ..settings import SignalSettings, get_settings
from .generator import generate_brief_for_cluster


def find_stale_brief_clusters(
    *,
    growth_threshold: float = 0.20,
    settings: SignalSettings | None = None,
) -> list[dict[str, Any]]:
    """Clusters whose current member_count is at least (1+threshold) × count at latest brief time."""
    s = settings or get_settings()
    if not s.database_url:
        return []
    out: list[dict[str, Any]] = []
    with connection(autocommit=True) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT c.id::text AS cluster_id,
                       b.id::text AS brief_id,
                       b.generated_at,
                       c.member_count AS member_now,
                       (
                         SELECT COUNT(*)::int
                         FROM cluster_members m
                         WHERE m.cluster_id = c.id
                           AND m.added_at <= b.generated_at
                       ) AS members_at_brief
                FROM clusters c
                INNER JOIN LATERAL (
                  SELECT id, generated_at
                  FROM cluster_briefs
                  WHERE cluster_id = c.id
                    AND superseded_by IS NULL
                    AND (archived_at IS NULL)
                  ORDER BY generated_at DESC
                  LIMIT 1
                ) b ON TRUE
                WHERE c.status NOT IN ('archived')
                  AND c.member_count IS NOT NULL
                  AND c.member_count > 0
                """
            )
            for row in cur.fetchall():
                at_brief = int(row["members_at_brief"] or 0)
                now = int(row["member_now"] or 0)
                base = max(at_brief, 1)
                if now >= base * (1.0 + growth_threshold):
                    out.append(dict(row))
    return out


def regen_stale_briefs(
    *,
    growth_threshold: float = 0.20,
    limit: int = 20,
    settings: SignalSettings | None = None,
) -> dict[str, Any]:
    """Regenerate briefs for stale clusters; mark prior brief superseded_by the new row."""
    s = settings or get_settings()
    stale = find_stale_brief_clusters(growth_threshold=growth_threshold, settings=s)[:limit]
    results: list[dict[str, Any]] = []
    for row in stale:
        cid = row["cluster_id"]
        old_brief = row["brief_id"]
        try:
            gen = generate_brief_for_cluster(cid, settings=s)
            new_id = gen.get("brief_id")
            if new_id and old_brief:
                with connection(autocommit=True) as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            UPDATE cluster_briefs
                            SET superseded_by = %s::uuid
                            WHERE id = %s::uuid AND superseded_by IS NULL
                            """,
                            (new_id, old_brief),
                        )
            results.append({"cluster_id": cid, "old_brief_id": old_brief, "new_brief_id": new_id, **gen})
        except Exception as e:
            results.append({"cluster_id": cid, "error": str(e)})
    return {"regenerated": len([r for r in results if "error" not in r]), "details": results}
