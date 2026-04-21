"""Anti-calcification — PRD §16.4."""

from __future__ import annotations

import random
import re
from typing import Any

from psycopg.rows import dict_row

from ..db import connection
from ..settings import SignalSettings, get_settings


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]{3,}", text.lower()))


def mark_monthly_exploration_cluster(settings: SignalSettings | None = None) -> dict[str, Any]:
    """
    Prefer a cluster whose brief/title overlaps top rejection reason tokens and active feedback_patterns.
    Falls back to random eligible cluster and sets fallback=true in the returned note.
    """
    s = settings or get_settings()
    if not s.database_url:
        raise RuntimeError("DATABASE_URL is required")

    kw: set[str] = set()
    with connection(autocommit=True) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT reason_code, COUNT(*)::int AS n
                FROM decisions
                WHERE action = 'reject'
                  AND decided_at >= NOW() - INTERVAL '90 days'
                  AND reason_code IS NOT NULL
                GROUP BY reason_code
                ORDER BY n DESC
                LIMIT 8
                """
            )
            for row in cur.fetchall():
                rc = str(row.get("reason_code") or "")
                kw |= _tokens(rc.replace("_", " "))

        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT pattern_description, prompt_addendum
                FROM feedback_patterns
                WHERE active IS TRUE
                """
            )
            for row in cur.fetchall():
                kw |= _tokens(str(row.get("pattern_description") or ""))
                kw |= _tokens(str(row.get("prompt_addendum") or ""))

    fallback = False
    chosen: str | None = None
    score = 0

    with connection(autocommit=True) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id::text AS id, canonical_statement, c_tfidf_label
                FROM clusters
                WHERE status IN ('new', 'surfaced', 'watching')
                  AND COALESCE(member_count, 0) >= 2
                """
            )
            candidates = cur.fetchall()

        if not candidates:
            return {"exploration_cluster_id": None, "note": "No eligible clusters (PRD §16.4)"}

        scored: list[tuple[int, str]] = []
        for row in candidates:
            blob = f"{row.get('canonical_statement') or ''} {row.get('c_tfidf_label') or ''}"
            tset = _tokens(blob)
            sc = len(kw & tset) if kw else 0
            scored.append((sc, str(row["id"])))

        scored.sort(key=lambda x: (-x[0], x[1]))
        best_s = scored[0][0]
        if best_s == 0 or not kw:
            fallback = True
            chosen = random.choice([str(r["id"]) for r in candidates])
            score = 0
        else:
            top = [sid for s, sid in scored if s == best_s]
            chosen = random.choice(top)
            score = best_s

        with conn.cursor() as cur:
            cur.execute("UPDATE clusters SET is_exploration = FALSE WHERE COALESCE(is_exploration, FALSE) IS TRUE")
            cur.execute(
                "UPDATE clusters SET is_exploration = TRUE WHERE id = %s::uuid RETURNING id::text",
                (chosen,),
            )
            row = cur.fetchone()
            cid = str(row[0]) if row else chosen

    note = (
        "Exploration cluster (PRD §16.4) — scored via rejection/pattern token overlap; "
        f"fallback={fallback}; score={score}."
    )
    return {"exploration_cluster_id": cid, "fallback": fallback, "keyword_overlap_score": score, "note": note}
