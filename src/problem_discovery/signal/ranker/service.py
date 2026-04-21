"""SQL ranker (PRD §10) — filter cascade, not ML."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import mean, median, pstdev
from typing import Any

from psycopg.rows import dict_row

from ..db import connection
from ..settings import SignalSettings, get_settings


def refresh_cluster_stats(settings: SignalSettings | None = None) -> int:
    """Recompute member_count, layer_coverage, source_diversity from members."""
    s = settings or get_settings()
    if not s.database_url:
        raise RuntimeError("DATABASE_URL is required")
    updated = 0
    with connection(autocommit=True) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT id FROM clusters")
            cids = [str(r["id"]) for r in cur.fetchall()]
        for cid in cids:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT COUNT(*)::int AS n,
                           COALESCE(
                             ARRAY_AGG(DISTINCT e.layer) FILTER (WHERE e.layer IS NOT NULL),
                             ARRAY[]::varchar[]
                           ) AS layers,
                           COUNT(DISTINCT r.source_id)::int AS src_div
                    FROM cluster_members m
                    JOIN extracted_problems e ON e.id = m.extracted_problem_id
                    JOIN raw_signals_index r ON r.id = e.raw_signal_id
                    WHERE m.cluster_id = %s::uuid
                    """,
                    (cid,),
                )
                row = cur.fetchone()
                if not row:
                    continue
                n = int(row["n"] or 0)
                layers = list(row["layers"] or [])
                src_div = int(row["src_div"] or 0)
                cur.execute(
                    """
                    UPDATE clusters
                    SET member_count = %s,
                        layer_coverage = %s::varchar[],
                        source_diversity_count = %s,
                        last_seen_at = NOW()
                    WHERE id = %s::uuid
                    """,
                    (n, layers, src_div, cid),
                )
                updated += 1
    return updated


def _weekly_member_counts(conn: Any, cluster_id: str, *, now: datetime) -> list[int]:
    """12 weeks × 7 days buckets — member adds per week (oldest first)."""
    counts: list[int] = []
    for w in range(12, 0, -1):
        end = now - timedelta(days=7 * (w - 1))
        start = now - timedelta(days=7 * w)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*)::int FROM cluster_members
                WHERE cluster_id = %s::uuid AND added_at >= %s AND added_at < %s
                """,
                (cluster_id, start, end),
            )
            row = cur.fetchone()
            counts.append(int(row[0]) if row else 0)
    return counts


def update_baseline_sigma(settings: SignalSettings | None = None) -> None:
    """12-week rolling baseline per PRD §9.4; warmup clusters use global median."""
    s = settings or get_settings()
    if not s.database_url:
        return
    now = datetime.now(timezone.utc)
    with connection(autocommit=True) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id::text AS id, first_seen_at
                FROM clusters
                WHERE status NOT IN ('archived')
                """
            )
            clusters = cur.fetchall()

        mature_last_weeks: list[int] = []
        preliminary_sigma: dict[str, float] = {}
        mature_sigma: dict[str, float] = {}
        cluster_meta: list[dict[str, Any]] = []

        for row in clusters:
            cid = str(row["id"])
            first = row.get("first_seen_at")
            if isinstance(first, datetime) and first.tzinfo is None:
                first = first.replace(tzinfo=timezone.utc)
            weeks = _weekly_member_counts(conn, cid, now=now)
            last_week = weeks[-1] if weeks else 0
            history = weeks[:-1] if len(weeks) > 1 else []

            warmup = first is not None and isinstance(first, datetime) and first > now - timedelta(days=84)
            cluster_meta.append(
                {
                    "id": cid,
                    "warmup": warmup,
                    "history": history,
                    "weeks": weeks,
                }
            )

            if warmup:
                preliminary_sigma[cid] = float(last_week)
                continue

            if len(history) >= 2:
                baseline = mean(history)
                std = pstdev(history) or 1.0
            elif weeks:
                baseline = mean(weeks)
                std = pstdev(weeks) or 1.0
            else:
                baseline = 0.0
                std = 1.0
            sigma = (last_week - baseline) / std
            mature_sigma[cid] = max(-5.0, min(5.0, float(sigma)))
            mature_last_weeks.append(last_week)

        g_med = float(median(mature_last_weeks)) if mature_last_weeks else 1.0
        g_std = float(pstdev(mature_last_weeks)) if len(mature_last_weeks) > 1 else 1.0
        if g_std < 1e-6:
            g_std = 1.0

        for cid, lw in preliminary_sigma.items():
            sigma = (lw - g_med) / g_std
            mature_sigma[cid] = max(-5.0, min(5.0, sigma))

        baseline_14d: dict[str, float] = {}
        for cm in cluster_meta:
            cid = cm["id"]
            if cm["warmup"]:
                baseline_14d[cid] = 2.0 * g_med
            else:
                h, w = cm["history"], cm["weeks"]
                if len(h) >= 2:
                    bw = mean(h)
                elif w:
                    bw = mean(w)
                else:
                    bw = 0.0
                baseline_14d[cid] = 2.0 * float(bw)

        with conn.cursor() as cur:
            for cid, sigma in mature_sigma.items():
                cur.execute(
                    """
                    UPDATE clusters
                    SET deviation_from_baseline_sigma = %s,
                        is_newly_discovered_14d = (first_seen_at > NOW() - INTERVAL '14 days')
                    WHERE id = %s::uuid
                    """,
                    (sigma, cid),
                )

        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE clusters
                SET member_count_last_14d = 0
                WHERE status NOT IN ('archived')
                """
            )
            cur.execute(
                """
                UPDATE clusters c
                SET member_count_last_14d = sub.n
                FROM (
                  SELECT cluster_id, COUNT(*)::int AS n
                  FROM cluster_members
                  WHERE added_at >= NOW() - INTERVAL '14 days'
                  GROUP BY cluster_id
                ) sub
                WHERE c.id = sub.cluster_id
                """
            )

        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id::text AS id, COALESCE(member_count_last_14d, 0)::numeric AS n14
                FROM clusters
                WHERE status NOT IN ('archived')
                """
            )
            rows_14 = cur.fetchall()
        with conn.cursor() as cur_u:
            for r in rows_14:
                cid = str(r["id"])
                n14 = float(r["n14"] or 0)
                base = float(baseline_14d.get(cid, 0.0))
                denom = max(base, 1.0)
                rate = (n14 - base) / denom
                cur_u.execute(
                    """
                    UPDATE clusters
                    SET growth_rate_14d = %s
                    WHERE id = %s::uuid
                    """,
                    (rate, cid),
                )


def ranker_surface_eligibility(
    cluster_id: str,
    *,
    settings: SignalSettings | None = None,
    refresh_stats: bool = True,
) -> dict[str, Any]:
    """
    True if this cluster satisfies the same SQL cascade as `select_surface_candidates` (PRD §10.1).
    Used for Set C `--replay-from-db` (live cluster row + ranker_settings; not a full historical snapshot).
    """
    s = settings or get_settings()
    if not s.database_url:
        raise RuntimeError("DATABASE_URL is required")
    if refresh_stats:
        refresh_cluster_stats(s)
        update_baseline_sigma(s)

    with connection(autocommit=True) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT deviation_sigma_threshold FROM ranker_settings WHERE singleton_lock = 1"
            )
            rs = cur.fetchone()
            thresh = float(rs["deviation_sigma_threshold"]) if rs else 1.5
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT c.id
                FROM clusters c
                WHERE c.id = %s::uuid
                  AND c.member_count >= 3
                  AND c.source_diversity_count >= 2
                  AND COALESCE(array_length(c.layer_coverage, 1), 0) >= 3
                  AND EXISTS (
                    SELECT 1 FROM cluster_members m
                    JOIN extracted_problems e ON e.id = m.extracted_problem_id
                    WHERE m.cluster_id = c.id AND e.wtp_level IN ('strong', 'proven')
                  )
                  AND EXISTS (
                    SELECT 1 FROM cluster_members m
                    JOIN extracted_problems e ON e.id = m.extracted_problem_id
                    WHERE m.cluster_id = c.id AND e.admiralty_source_reliability IN ('A','B','C')
                  )
                  AND COALESCE(
                    (
                      SELECT AVG(e.admiralty_info_credibility)::float
                      FROM cluster_members m
                      JOIN extracted_problems e ON e.id = m.extracted_problem_id
                      WHERE m.cluster_id = c.id
                    ),
                    99
                  ) <= 3.5
                  AND (
                    c.deviation_from_baseline_sigma > %s
                    OR c.is_newly_discovered_14d IS TRUE
                  )
                  AND c.status NOT IN ('rejected', 'archived', 'snoozed')
                  AND NOT EXISTS (
                    SELECT 1 FROM cluster_briefs b
                    WHERE b.cluster_id = c.id AND b.superseded_by IS NULL
                      AND b.archived_at IS NULL
                  )
                """,
                (cluster_id, thresh),
            )
            ok = cur.fetchone() is not None
    return {
        "cluster_id": cluster_id,
        "surface_eligible": ok,
        "refresh_stats": refresh_stats,
        "note": "Compared to gold: treat accept as expecting eligibility; other actions expect ineligible (PRD Set C replay proxy).",
    }


def select_surface_candidates(
    *,
    limit: int = 5,
    settings: SignalSettings | None = None,
) -> list[dict[str, Any]]:
    """Eligible clusters per PRD §10.1; ORDER BY §10.1."""
    s = settings or get_settings()
    if not s.database_url:
        raise RuntimeError("DATABASE_URL is required")

    refresh_cluster_stats(s)
    update_baseline_sigma(s)

    with connection(autocommit=True) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT deviation_sigma_threshold, surfacing_cap_per_day FROM ranker_settings WHERE singleton_lock = 1")
            rs = cur.fetchone()
            thresh = float(rs["deviation_sigma_threshold"]) if rs else 1.5
            cap = int(rs["surfacing_cap_per_day"]) if rs else 5
            lim = min(limit, cap)

        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT c.id, c.canonical_statement, c.c_tfidf_label, c.member_count,
                       c.layer_coverage, c.source_diversity_count, c.deviation_from_baseline_sigma,
                       c.is_newly_discovered_14d, c.member_count_last_14d, c.status
                FROM clusters c
                WHERE c.member_count >= 3
                  AND c.source_diversity_count >= 2
                  AND COALESCE(array_length(c.layer_coverage, 1), 0) >= 3
                  AND EXISTS (
                    SELECT 1 FROM cluster_members m
                    JOIN extracted_problems e ON e.id = m.extracted_problem_id
                    WHERE m.cluster_id = c.id AND e.wtp_level IN ('strong', 'proven')
                  )
                  AND EXISTS (
                    SELECT 1 FROM cluster_members m
                    JOIN extracted_problems e ON e.id = m.extracted_problem_id
                    WHERE m.cluster_id = c.id AND e.admiralty_source_reliability IN ('A','B','C')
                  )
                  AND COALESCE(
                    (
                      SELECT AVG(e.admiralty_info_credibility)::float
                      FROM cluster_members m
                      JOIN extracted_problems e ON e.id = m.extracted_problem_id
                      WHERE m.cluster_id = c.id
                    ),
                    99
                  ) <= 3.5
                  AND (
                    c.deviation_from_baseline_sigma > %s
                    OR c.is_newly_discovered_14d IS TRUE
                  )
                  AND c.status NOT IN ('rejected', 'archived', 'snoozed')
                  AND NOT EXISTS (
                    SELECT 1 FROM cluster_briefs b
                    WHERE b.cluster_id = c.id AND b.superseded_by IS NULL
                      AND b.archived_at IS NULL
                  )
                ORDER BY
                  CASE WHEN COALESCE(c.is_exploration, FALSE) THEN 1 ELSE 0 END DESC,
                  COALESCE(array_length(c.layer_coverage, 1), 0) DESC,
                  c.deviation_from_baseline_sigma DESC NULLS LAST,
                  c.source_diversity_count DESC,
                  c.member_count_last_14d DESC NULLS LAST
                LIMIT %s
                """,
                (thresh, lim),
            )
            return list(cur.fetchall())
