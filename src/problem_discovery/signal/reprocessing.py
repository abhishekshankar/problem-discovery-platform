"""Reprocess raw signals with a new extractor version (PRD §14.3)."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from psycopg.rows import dict_row

from .clustering.service import run_clustering_pipeline
from .db import connection
from .extraction.pipeline import run_extraction_batch
from .settings import SignalSettings, get_settings


def _cluster_raw_map(conn: Any, raw_ids: list[int]) -> dict[str, set[int]]:
    """Map cluster_id -> set(raw_signal_id) for clusters touching these raw rows."""
    if not raw_ids:
        return {}
    out: dict[str, set[int]] = {}
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT m.cluster_id::text AS cid, e.raw_signal_id AS rid
            FROM extracted_problems e
            JOIN cluster_members m ON m.extracted_problem_id = e.id
            WHERE e.raw_signal_id = ANY(%s)
            """,
            (raw_ids,),
        )
        for row in cur.fetchall():
            cid = str(row["cid"])
            rid = int(row["rid"])
            out.setdefault(cid, set()).add(rid)
    return out


def _jaccard(a: set[int], b: set[int]) -> float:
    if not a and not b:
        return 1.0
    u = a | b
    if not u:
        return 0.0
    return len(a & b) / len(u)


def _diff_cluster_maps(
    old_map: dict[str, set[int]],
    new_map: dict[str, set[int]],
    universe: set[int],
) -> dict[str, Any]:
    """Heuristic diff: new / removed / merged / membership-changed (PRD §14.3)."""
    U = universe

    def restrict(m: dict[str, set[int]]) -> dict[str, set[int]]:
        r: dict[str, set[int]] = {}
        for cid, members in m.items():
            inter = members & U
            if inter:
                r[cid] = inter
        return r

    O = restrict(old_map)
    N = restrict(new_map)

    # Greedy match old clusters to new clusters by best Jaccard (many-old -> one-new = merge)
    old_ids = sorted(O.keys(), key=lambda k: len(O[k]), reverse=True)
    assigned_old: set[str] = set()
    new_to_olds: dict[str, list[str]] = {}

    for ocid in old_ids:
        best_j = -1.0
        best_n: str | None = None
        for ncid, nmem in N.items():
            j = _jaccard(O[ocid], nmem)
            if j > best_j:
                best_j = j
                best_n = ncid
        if best_n is not None and best_j >= 0.15:
            assigned_old.add(ocid)
            new_to_olds.setdefault(best_n, []).append(ocid)

    removed = [oc for oc in O if oc not in assigned_old]
    matched_new_ids = set(new_to_olds.keys())
    new_only = [nc for nc in N if nc not in matched_new_ids]

    merge_events: list[dict[str, Any]] = []
    membership_changed_details: list[dict[str, Any]] = []
    merge_count = 0
    membership_changed_clusters = 0

    for ncid, olist in new_to_olds.items():
        if len(olist) > 1:
            merge_count += 1
            merge_events.append({"new_cluster_id": ncid, "merged_old_cluster_ids": olist})
        elif len(olist) == 1:
            ocid = olist[0]
            omem, nmem = O[ocid] & U, N[ncid] & U
            if omem != nmem:
                membership_changed_clusters += 1
                membership_changed_details.append(
                    {
                        "old_cluster_id": ocid,
                        "new_cluster_id": ncid,
                        "jaccard": round(_jaccard(omem, nmem), 4),
                        "symmetric_diff_raw_count": len((omem ^ nmem) & U),
                    }
                )

    return {
        "clusters_removed_count": len(removed),
        "clusters_new_count": len(new_only),
        "clusters_merged_count": merge_count,
        "clusters_membership_changed_count": membership_changed_clusters,
        "removed_cluster_ids_sample": removed[:50],
        "new_cluster_ids_sample": new_only[:50],
        "merge_events": merge_events[:200],
        "membership_changed": membership_changed_details[:200],
    }


def _write_reports(base: Path, summary: dict[str, Any]) -> dict[str, str]:
    base.mkdir(parents=True, exist_ok=True)
    jp = base / "reprocess_cluster_diff.json"
    mp = base / "reprocess_cluster_diff.md"
    jp.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    d = summary.get("diff", {})
    md_lines = [
        "# Reprocess cluster diff",
        "",
        f"- raw_signals_in_window: {summary.get('raw_ids_count')}",
        f"- clusters_removed: {d.get('clusters_removed_count')}",
        f"- clusters_new: {d.get('clusters_new_count')}",
        f"- merges_detected: {d.get('clusters_merged_count')}",
        f"- membership_changed_clusters: {d.get('clusters_membership_changed_count')}",
        "",
        "## Merge events (truncated)",
        "",
        "```",
        json.dumps(d.get("merge_events", [])[:30], indent=2, default=str),
        "```",
        "",
        "## Membership changes (truncated)",
        "",
        "```",
        json.dumps(d.get("membership_changed", [])[:30], indent=2, default=str),
        "```",
    ]
    mp.write_text("\n".join(md_lines), encoding="utf-8")
    return {"json": str(jp), "markdown": str(mp)}


def reprocess_raw_signals_from(
    from_date: date | datetime,
    *,
    settings: SignalSettings | None = None,
    extract_limit: int = 5000,
    source_label: str = "reddit",
    run_clustering_after: bool = True,
    report_dir: Path | None = None,
) -> dict[str, Any]:
    """
    Delete derived rows for raw signals captured on/after from_date, then re-run extraction.
    Optionally re-cluster and emit JSON/Markdown diff keyed by raw_signal_id (PRD §14.3).
    """
    s = settings or get_settings()
    if not s.database_url:
        raise RuntimeError("DATABASE_URL is required")

    if isinstance(from_date, datetime):
        cutoff = from_date
    else:
        cutoff = datetime(from_date.year, from_date.month, from_date.day, tzinfo=timezone.utc)

    old_snapshot: dict[str, set[int]] = {}
    raw_ids: list[int] = []

    with connection(autocommit=False) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id FROM raw_signals_index
                WHERE captured_at >= %s
                ORDER BY id
                LIMIT %s
                """,
                (cutoff, extract_limit),
            )
            raw_rows = cur.fetchall()
        raw_ids = [int(r["id"]) for r in raw_rows]

        if not raw_ids:
            conn.rollback()
            return {"raw_ids": [], "deleted_problems": 0, "extraction": None, "note": "no raw rows in window"}

        old_snapshot = _cluster_raw_map(conn, raw_ids)

        deleted = 0
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM cluster_members
                WHERE extracted_problem_id IN (
                  SELECT id FROM extracted_problems WHERE raw_signal_id = ANY(%s)
                )
                """,
                (raw_ids,),
            )
            cur.execute(
                """
                WITH del AS (
                  DELETE FROM extracted_problems WHERE raw_signal_id = ANY(%s) RETURNING id
                )
                SELECT COUNT(*)::int FROM del
                """,
                (raw_ids,),
            )
            row = cur.fetchone()
            deleted = int(row[0]) if row else 0
        conn.commit()

    ext = run_extraction_batch(limit=len(raw_ids), settings=s, source_label=source_label, raw_signal_ids=raw_ids)

    cluster_out: dict[str, Any] | None = None
    if run_clustering_after:
        cluster_out = run_clustering_pipeline(settings=s)

    new_snapshot: dict[str, set[int]] = {}
    with connection(autocommit=False) as conn:
        new_snapshot = _cluster_raw_map(conn, raw_ids)

    U = set(raw_ids)
    diff = _diff_cluster_maps(old_snapshot, new_snapshot, U)
    summary = {
        "from": cutoff.isoformat(),
        "raw_ids_count": len(raw_ids),
        "deleted_extracted_problems": deleted,
        "extraction": ext,
        "clustering": cluster_out,
        "diff": diff,
        "old_cluster_count_touching_window": len(old_snapshot),
        "new_cluster_count_touching_window": len(new_snapshot),
    }

    paths: dict[str, str] | None = None
    if report_dir is not None:
        paths = _write_reports(report_dir, summary)

    summary["report_paths"] = paths
    summary["note"] = "Review cluster diff before promoting (PRD §14.3)."
    return summary
