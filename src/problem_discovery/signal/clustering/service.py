"""BERTopic + incremental centroid assignment (PRD §9)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import numpy as np
from psycopg.rows import dict_row

from ..db import connection
from ..settings import SignalSettings, get_settings

COSINE_ASSIGN_THRESHOLD = 0.82
MIN_TOPIC_SIZE = 3
BERTOPIC_VERSION = "0.16"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _cosine(a: list[float], b: list[float]) -> float:
    va = np.asarray(a, dtype=np.float64)
    vb = np.asarray(b, dtype=np.float64)
    na = np.linalg.norm(va)
    nb = np.linalg.norm(vb)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))


def run_clustering_pipeline(
    *,
    settings: SignalSettings | None = None,
    extractor_version_filter: str | None = None,
) -> dict[str, Any]:
    """Assign to existing centroids where sim>0.82; run BERTopic on remainder."""
    s = settings or get_settings()
    if not s.database_url:
        raise RuntimeError("DATABASE_URL is required")

    try:
        from pgvector.psycopg import register_vector
    except ImportError:
        register_vector = None  # type: ignore[assignment]

    run_id = uuid.uuid4()
    assigned = 0
    new_clusters = 0

    with connection(autocommit=False) as conn:
        if register_vector:
            register_vector(conn)

        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT c.id, c.centroid_embedding
                FROM clusters c
                WHERE c.status NOT IN ('archived')
                  AND c.centroid_embedding IS NOT NULL
                """
            )
            existing = cur.fetchall()

        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT e.id, e.embedding, e.problem_statement, e.exact_quote, e.layer, e.raw_signal_id
                FROM extracted_problems e
                WHERE e.embedding IS NOT NULL
                  AND e.is_problem_signal IS TRUE
                  AND NOT EXISTS (SELECT 1 FROM cluster_members m WHERE m.extracted_problem_id = e.id)
                ORDER BY e.id
                """
            )
            unassigned = cur.fetchall()

        if not unassigned:
            conn.rollback()
            return {"clustering_run_id": str(run_id), "assigned_incremental": 0, "new_clusters": 0, "note": "nothing to cluster"}

        # Incremental assignment
        centroids: list[tuple[Any, list[float]]] = []
        for row in existing:
            ce = row["centroid_embedding"]
            if ce is not None:
                centroids.append((str(row["id"]), list(ce)))

        still_unassigned: list[dict[str, Any]] = []
        for row in unassigned:
            eid = int(row["id"])
            emb = list(row["embedding"])
            best: tuple[str, float] | None = None
            for cid, cemb in centroids:
                sim = _cosine(emb, cemb)
                if best is None or sim > best[1]:
                    best = (cid, sim)
            if best and best[1] >= COSINE_ASSIGN_THRESHOLD:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO cluster_members (cluster_id, extracted_problem_id, similarity_score, added_at)
                        VALUES (%s::uuid, %s, %s, NOW())
                        ON CONFLICT DO NOTHING
                        """,
                        (best[0], eid, best[1]),
                    )
                assigned += 1
            else:
                still_unassigned.append(dict(row))

        # BERTopic on remainder (need min size)
        bertopic_docs: list[str] = []
        bertopic_ids: list[int] = []
        bertopic_embs: list[list[float]] = []
        for row in still_unassigned:
            text = (row.get("problem_statement") or row.get("exact_quote") or "").strip()
            if len(text) < 10:
                continue
            bertopic_docs.append(text[:2000])
            bertopic_ids.append(int(row["id"]))
            bertopic_embs.append(list(row["embedding"]))

        if len(bertopic_docs) >= MIN_TOPIC_SIZE:
            try:
                from bertopic import BERTopic
            except ImportError as e:
                conn.rollback()
                raise RuntimeError("bertopic is required for nightly clustering") from e

            emb_np = np.asarray(bertopic_embs, dtype=np.float32)
            topic_model = BERTopic(min_topic_size=MIN_TOPIC_SIZE, verbose=False)
            topics, _ = topic_model.fit_transform(bertopic_docs, emb_np)

            # Group by topic id (-1 is outlier)
            from collections import defaultdict

            groups: dict[int, list[int]] = defaultdict(list)
            for i, t in enumerate(topics):
                ti = int(t) if hasattr(t, "item") else int(t)
                if ti >= 0:
                    groups[ti].append(bertopic_ids[i])

            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO clustering_runs (
                      id, algorithm, algorithm_version, parameters_json, extractor_version_filter,
                      started_at, completed_at, cluster_count, noise_point_count, promoted
                    )
                    VALUES (%s, %s, %s, %s::jsonb, %s, NOW(), NOW(), %s, %s, TRUE)
                    """,
                    (
                        str(run_id),
                        "bertopic",
                        BERTOPIC_VERSION,
                        '{"min_topic_size": 3, "min_samples": 2}',
                        extractor_version_filter,
                        len(groups),
                        max(0, len(bertopic_docs) - sum(len(v) for v in groups.values())),
                    ),
                )

            label_map: dict[int, str] = {}
            try:
                lbls = topic_model.get_topic_info()
                for _, r in lbls.iterrows():
                    label_map[int(r["Topic"])] = str(r.get("Name", ""))[:500]
            except Exception:
                pass

            for tid, eids in groups.items():
                if len(eids) < MIN_TOPIC_SIZE:
                    continue
                cid = str(uuid.uuid4())
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(
                        "SELECT id, embedding FROM extracted_problems WHERE id = ANY(%s)",
                        (eids,),
                    )
                    erows = cur.fetchall()
                mat = np.asarray([list(r["embedding"]) for r in erows], dtype=np.float64)
                centroid = mat.mean(axis=0).tolist()
                ctfidf = label_map.get(tid, f"topic_{tid}")
                now = _utc_now()
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO clusters (
                          id, clustering_run_id, canonical_statement, c_tfidf_label,
                          first_seen_at, last_seen_at, member_count, layer_coverage, source_diversity_count,
                          centroid_embedding, status, deviation_from_baseline_sigma, is_newly_discovered_14d,
                          member_count_last_14d, version_status
                        )
                        VALUES (
                          %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s::vector, %s, %s, TRUE, %s, %s
                        )
                        """,
                        (
                            cid,
                            str(run_id),
                            ctfidf,
                            ctfidf,
                            now,
                            now,
                            len(eids),
                            ["unformed", "formed", "frustrated", "paying"],
                            1,
                            centroid,
                            "new",
                            0.0,
                            len(eids),
                            "clean",
                        ),
                    )
                    for eid in eids:
                        cur.execute(
                            """
                            INSERT INTO cluster_members (cluster_id, extracted_problem_id, similarity_score, added_at)
                            VALUES (%s::uuid, %s, %s, NOW())
                            """,
                            (cid, eid, 1.0),
                        )
                new_clusters += 1
        else:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO clustering_runs (
                      id, algorithm, algorithm_version, parameters_json, extractor_version_filter,
                      started_at, completed_at, cluster_count, noise_point_count, promoted
                    )
                    VALUES (%s, %s, %s, %s::jsonb, %s, NOW(), NOW(), 0, %s, FALSE)
                    """,
                    (
                        str(run_id),
                        "bertopic",
                        BERTOPIC_VERSION,
                        "{}",
                        extractor_version_filter,
                        len(bertopic_docs),
                    ),
                )

        conn.commit()

    return {
        "clustering_run_id": str(run_id),
        "assigned_incremental": assigned,
        "new_clusters": new_clusters,
    }
