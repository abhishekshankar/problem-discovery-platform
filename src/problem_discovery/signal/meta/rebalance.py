"""Monthly source accept-rate rebalancing — PRD §16.2."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Any

from psycopg.rows import dict_row

from ..db import connection
from ..settings import SignalSettings, get_settings


def run_source_accept_rebalance(settings: SignalSettings | None = None) -> dict[str, Any]:
    """Update sources.accept_rate_rolling; propose throttle candidates vs median (no auto-disable)."""
    s = settings or get_settings()
    if not s.database_url:
        raise RuntimeError("DATABASE_URL is required")

    since = datetime.now(timezone.utc) - timedelta(days=90)
    updates: list[dict[str, Any]] = []
    proposals: list[dict[str, Any]] = []
    with connection(autocommit=True) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT src.id AS source_id, src.name,
                       AVG(CASE WHEN d.action = 'accept' THEN 1.0 ELSE 0.0 END)::float AS accept_rate,
                       COUNT(*)::int AS n
                FROM decisions d
                JOIN clusters c ON c.id = d.cluster_id
                JOIN cluster_members m ON m.cluster_id = c.id
                JOIN extracted_problems e ON e.id = m.extracted_problem_id
                JOIN raw_signals_index r ON r.id = e.raw_signal_id
                JOIN sources src ON src.id = r.source_id
                WHERE d.decided_at >= %s
                GROUP BY src.id, src.name
                HAVING COUNT(*) >= 3
                """,
                (since,),
            )
            rows = cur.fetchall()

        rates = [float(r["accept_rate"] or 0) for r in rows]
        med = float(median(rates)) if rates else 0.0

        for row in rows:
            rate = float(row["accept_rate"] or 0)
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE sources SET accept_rate_rolling = %s, last_success_at = NOW() WHERE id = %s",
                    (rate, int(row["source_id"])),
                )
            updates.append({"source": row["name"], "accept_rate_rolling": rate, "n": int(row["n"])})

            if med > 0 and int(row["n"]) >= 5 and rate < med * 0.5:
                pid = str(uuid.uuid4())
                reason = f"accept_rate {rate:.3f} < 0.5×median {med:.3f} (PRD §16.2 proposal)"
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(
                        """
                        SELECT id FROM source_rebalance_proposals
                        WHERE source_id = %s AND confirmed_at IS NULL AND rejected_at IS NULL
                        LIMIT 1
                        """,
                        (int(row["source_id"]),),
                    )
                    if cur.fetchone():
                        continue
                    cur.execute(
                        """
                        INSERT INTO source_rebalance_proposals (
                          id, source_id, proposed_status, reason, median_accept_rate, source_accept_rate
                        )
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (pid, int(row["source_id"]), "throttle_candidate", reason, med, rate),
                    )
                    proposals.append(
                        {
                            "proposal_id": str(cur.fetchone()["id"]),
                            "source": row["name"],
                            "proposed_status": "throttle_candidate",
                        }
                    )

    return {
        "updated_sources": updates,
        "window_start": since.isoformat(),
        "median_accept_rate": med,
        "new_proposals": proposals,
    }


def list_pending_throttle_proposals(settings: SignalSettings | None = None) -> list[dict[str, Any]]:
    s = settings or get_settings()
    if not s.database_url:
        raise RuntimeError("DATABASE_URL is required")
    with connection(autocommit=True) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT p.id, p.source_id, p.proposed_status, p.reason, p.median_accept_rate,
                       p.source_accept_rate, p.created_at, s.name AS source_name
                FROM source_rebalance_proposals p
                JOIN sources s ON s.id = p.source_id
                WHERE p.confirmed_at IS NULL AND p.rejected_at IS NULL
                ORDER BY p.created_at DESC
                """
            )
            return [dict(r) for r in cur.fetchall()]


def confirm_throttle_proposal(
    *,
    proposal_id: str,
    action: str,
    confirmed_by: str,
    settings: SignalSettings | None = None,
) -> dict[str, Any]:
    """Human confirm: throttle / disable source, or reject proposal (audit in row)."""
    s = settings or get_settings()
    if not s.database_url:
        raise RuntimeError("DATABASE_URL is required")
    if action == "reject":
        with connection(autocommit=True) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    UPDATE source_rebalance_proposals
                    SET rejected_at = NOW()
                    WHERE id = %s::uuid AND confirmed_at IS NULL AND rejected_at IS NULL
                    RETURNING id, source_id
                    """,
                    (proposal_id,),
                )
                row = cur.fetchone()
        if not row:
            return {"ok": False, "error": "proposal not found or already closed"}
        return {"ok": True, "rejected": True, "proposal_id": proposal_id}

    new_status = "throttled" if action == "throttle" else "disabled"
    with connection(autocommit=False) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                UPDATE source_rebalance_proposals
                SET confirmed_at = NOW(), confirmed_by = %s
                WHERE id = %s::uuid AND confirmed_at IS NULL AND rejected_at IS NULL
                RETURNING id, source_id
                """,
                (confirmed_by, proposal_id),
            )
            row = cur.fetchone()
            if not row:
                conn.rollback()
                return {"ok": False, "error": "proposal not found or already closed"}
            sid = int(row["source_id"])
            cur.execute(
                "UPDATE sources SET status = %s, notes = COALESCE(notes,'') || %s WHERE id = %s",
                (
                    new_status,
                    f"\n[{datetime.now(timezone.utc).isoformat()}] {confirmed_by} applied {new_status} via proposal {proposal_id}\n",
                    sid,
                ),
            )
        conn.commit()
    return {"ok": True, "proposal_id": proposal_id, "source_id": sid, "sources_status": new_status}
