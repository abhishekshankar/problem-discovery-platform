"""Cluster hygiene — PRD §9.3 merge / split flag / retire."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np
from psycopg.rows import dict_row

from ..db import connection
from ..settings import SignalSettings, get_settings


def _cosine(a: list[float], b: list[float]) -> float:
    va = np.asarray(a, dtype=np.float64)
    vb = np.asarray(b, dtype=np.float64)
    na = np.linalg.norm(va)
    nb = np.linalg.norm(vb)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))


def run_cluster_hygiene(
    *,
    settings: SignalSettings | None = None,
    merge_threshold: float = 0.90,
) -> dict[str, Any]:
    """Merge clusters with centroid similarity > merge_threshold; archive stale (60d no new members)."""
    s = settings or get_settings()
    if not s.database_url:
        raise RuntimeError("DATABASE_URL is required")

    merged = 0
    archived = 0
    now = datetime.now(timezone.utc)

    with connection(autocommit=False) as conn:
        try:
            from pgvector.psycopg import register_vector
        except ImportError:
            register_vector = None  # type: ignore[assignment]
        if register_vector:
            register_vector(conn)

        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id::text AS id, centroid_embedding, status
                FROM clusters
                WHERE status NOT IN ('archived') AND centroid_embedding IS NOT NULL
                """
            )
            rows = cur.fetchall()

        centroids = [(str(r["id"]), list(r["centroid_embedding"])) for r in rows if r.get("centroid_embedding")]
        parent: dict[str, str] = {}

        for i, (id_a, emb_a) in enumerate(centroids):
            if id_a in parent:
                continue
            for j in range(i + 1, len(centroids)):
                id_b, emb_b = centroids[j]
                if id_b in parent:
                    continue
                if _cosine(emb_a, emb_b) >= merge_threshold:
                    # merge smaller into larger by member count
                    with conn.cursor(row_factory=dict_row) as cur:
                        cur.execute(
                            "SELECT member_count FROM clusters WHERE id = %s::uuid",
                            (id_a,),
                        )
                        ca = cur.fetchone()
                        cur.execute(
                            "SELECT member_count FROM clusters WHERE id = %s::uuid",
                            (id_b,),
                        )
                        cb = cur.fetchone()
                    a_count = int(ca["member_count"] or 0) if ca else 0
                    b_count = int(cb["member_count"] or 0) if cb else 0
                    keep, absorb = (id_a, id_b) if a_count >= b_count else (id_b, id_a)
                    if absorb == keep:
                        continue
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO cluster_members (cluster_id, extracted_problem_id, similarity_score, added_at)
                            SELECT %s::uuid, extracted_problem_id, similarity_score, added_at
                            FROM cluster_members WHERE cluster_id = %s::uuid
                            ON CONFLICT (cluster_id, extracted_problem_id) DO NOTHING
                            """,
                            (keep, absorb),
                        )
                        cur.execute("DELETE FROM cluster_members WHERE cluster_id = %s::uuid", (absorb,))
                        cur.execute(
                            "UPDATE clusters SET status = 'archived' WHERE id = %s::uuid",
                            (absorb,),
                        )
                    parent[absorb] = keep
                    merged += 1

        cutoff = now - timedelta(days=60)
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT c.id::text AS id
                FROM clusters c
                WHERE c.status NOT IN ('archived')
                  AND NOT EXISTS (
                    SELECT 1 FROM cluster_members m
                    WHERE m.cluster_id = c.id AND m.added_at >= %s
                  )
                  AND c.last_seen_at < %s
                """,
                (cutoff, cutoff),
            )
            stale = [str(r["id"]) for r in cur.fetchall()]
        for cid in stale:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE clusters SET status = 'archived' WHERE id = %s::uuid",
                    (cid,),
                )
                archived += 1

        conn.commit()

    return {"merged_pairs": merged, "archived_stale": archived, "merge_threshold": merge_threshold}


def flag_low_silhouette_clusters(
    *,
    settings: SignalSettings | None = None,
    threshold: float = 0.15,
) -> dict[str, Any]:
    """PRD §9.3 split hint — compute silhouette offline on exported embeddings; this returns large clusters to review."""
    s = settings or get_settings()
    if not s.database_url:
        raise RuntimeError("DATABASE_URL is required")
    flagged: list[str] = []
    with connection(autocommit=True) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT c.id::text AS id, c.member_count
                FROM clusters c
                WHERE c.status NOT IN ('archived') AND COALESCE(c.member_count, 0) >= 25
                ORDER BY c.member_count DESC
                LIMIT 15
                """
            )
            flagged = [str(r["id"]) for r in cur.fetchall()]
    return {"flagged_for_review": flagged, "note": f"review for split if silhouette < {threshold}"}
