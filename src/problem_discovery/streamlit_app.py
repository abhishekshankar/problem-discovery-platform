"""Signal review UI (PRD §12) — single-user Streamlit."""

from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Ensure `src` is on path so `problem_discovery.signal` resolves (subfolder named `signal` avoids stdlib clash).
_SRC = Path(__file__).resolve().parent.parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import streamlit as st

from problem_discovery.signal.briefs.generator import generate_brief_for_cluster
from problem_discovery.signal.db import connection
from problem_discovery.signal.ops.metrics import bump_review_metrics
from problem_discovery.signal.ops.throughput import compute_action_within_7d
from problem_discovery.signal.meta.rebalance import confirm_throttle_proposal, list_pending_throttle_proposals
from problem_discovery.signal.ranker.service import select_surface_candidates
from problem_discovery.signal.settings import get_settings


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


st.set_page_config(page_title="Signal — Problem Discovery", layout="wide")
st.title("Signal")
st.caption("Latent demand discovery — no opportunity scores, human judgment only.")

settings = get_settings()
if not settings.database_url:
    st.error("Set DATABASE_URL to use the review UI.")
    st.stop()

if "queue_metrics_bumped" not in st.session_state:
    st.session_state.queue_metrics_bumped = True
    bump_review_metrics(briefs_opened=1)

tab_queue, tab_watch, tab_accepted, tab_throughput, tab_health, tab_eval = st.tabs(
    ["Daily queue", "Watchlist", "Accepted", "Throughput", "Source health", "Eval status"]
)

with tab_queue:
    st.subheader("Ranked briefs (surfaced clusters)")
    with connection() as conn:
        from psycopg.rows import dict_row

        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT b.id, b.cluster_id, b.generated_at, b.brief_markdown, b.verification_failed,
                       c.canonical_statement, c.status, COALESCE(c.is_exploration, FALSE) AS is_exploration,
                       COALESCE(c.version_status, 'clean') AS version_status
                FROM cluster_briefs b
                JOIN clusters c ON c.id = b.cluster_id
                WHERE b.superseded_by IS NULL AND b.archived_at IS NULL
                ORDER BY b.generated_at DESC
                LIMIT 50
                """
            )
            briefs = cur.fetchall()

    if not briefs:
        st.info("No briefs yet. Run the pipeline CLI to collect, extract, cluster, rank, and generate briefs.")
    for row in briefs:
        key = str(row["id"])
        expl = " **exploration**" if row.get("is_exploration") else ""
        with st.expander(f"{row.get('canonical_statement') or 'Cluster'}{expl} — {row['generated_at']}"):
            st.markdown(row.get("brief_markdown") or "")
            if str(row.get("version_status") or "").lower() == "mixed":
                st.warning(
                    "**Mixed extractor versions** — cluster members span more than one `extraction_runs.extractor_version` (PRD §14.4). Interpret evidence carefully."
                )
            if row.get("verification_failed"):
                st.warning("Brief verification flagged — manual inspection recommended (PRD §11.4).")
            if row.get("is_exploration"):
                st.info("Exploration cluster (PRD §16.4) — intentionally outside typical preference patterns.")
            action = st.selectbox(
                "Action",
                ["accept", "reject", "snooze_30d", "snooze_60d", "snooze_90d", "needs_more_signal"],
                key=f"act_{key}",
            )
            reason = st.selectbox(
                "Reject reason (if reject)",
                [
                    "too-crowded",
                    "wrong-buyer",
                    "not-my-domain",
                    "signal-too-weak",
                    "already-tried",
                    "incumbent-will-own",
                    "other",
                ],
                key=f"rej_{key}",
            )
            detail = st.text_input("Notes", key=f"note_{key}")
            if st.button("Submit decision", key=f"sub_{key}"):
                did = str(uuid.uuid4())
                snooze_until = None
                if action.startswith("snooze"):
                    from datetime import timedelta

                    days = {"snooze_30d": 30, "snooze_60d": 60, "snooze_90d": 90}.get(action, 30)
                    snooze_until = datetime.now(timezone.utc) + timedelta(days=days)
                with connection(autocommit=True) as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO decisions (id, cluster_id, brief_id, action, reason_code, reason_text, decided_at, snooze_until)
                            VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, NOW(), %s)
                            """,
                            (
                                did,
                                str(row["cluster_id"]),
                                str(row["id"]),
                                action,
                                reason if action == "reject" else None,
                                detail or None,
                                snooze_until,
                            ),
                        )
                        if action.startswith("snooze"):
                            st_code = "snoozed"
                        elif action == "accept":
                            st_code = "accepted"
                        elif action == "needs_more_signal":
                            st_code = "watching"
                        else:
                            st_code = "rejected"
                        cur.execute(
                            "UPDATE clusters SET status = %s WHERE id = %s::uuid",
                            (st_code, str(row["cluster_id"])),
                        )
                bump_review_metrics(decisions_made=1)
                st.success("Saved.")

with tab_watch:
    st.subheader("Watching / needs more signal")
    with connection() as conn:
        from psycopg.rows import dict_row

        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT c.id, c.canonical_statement, c.status, c.last_seen_at
                FROM clusters c
                WHERE c.status IN ('watching', 'snoozed')
                ORDER BY c.last_seen_at DESC NULLS LAST
                LIMIT 100
                """
            )
            w = cur.fetchall()
    if not w:
        st.info("No clusters in watchlist.")
    for r in w:
        st.write(f"- **{r.get('canonical_statement') or r['id']}** — `{r['status']}`")

with tab_accepted:
    st.subheader("Accepted clusters — interview notes (PRD §12)")
    with connection() as conn:
        from psycopg.rows import dict_row

        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id::text AS id, canonical_statement, interview_notes, surfaced_at
                FROM clusters
                WHERE status = 'accepted'
                ORDER BY surfaced_at DESC NULLS LAST
                """
            )
            a = cur.fetchall()
    if not a:
        st.info("No accepted clusters yet.")
    for r in a:
        cid = str(r["id"])
        with st.expander(r.get("canonical_statement") or cid):
            notes = st.text_area(
                "Interview / validation notes",
                value=r.get("interview_notes") or "",
                key=f"in_{cid}",
                height=120,
            )
            if st.button("Save notes", key=f"sv_{cid}"):
                with connection(autocommit=True) as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE clusters SET interview_notes = %s WHERE id = %s::uuid",
                            (notes, cid),
                        )
                st.success("Notes saved.")

with tab_throughput:
    st.subheader("Brief → decision within 7 days (PRD §15.4)")
    m30 = compute_action_within_7d(30)
    m90 = compute_action_within_7d(90)
    c1, c2 = st.columns(2)
    with c1:
        st.metric("30-day rolling %", f"{m30.get('pct') if m30.get('pct') is not None else '—'}%")
        st.caption(f"Briefs in window: {m30.get('total_briefs', 0)} · acted ≤7d: {m30.get('acted_within_7d', 0)}")
        if m30.get("below_target_60pct"):
            st.error("Below 60% target — review queue load or SLAs.")
    with c2:
        st.metric("90-day rolling %", f"{m90.get('pct') if m90.get('pct') is not None else '—'}%")
        st.caption(f"Briefs in window: {m90.get('total_briefs', 0)} · acted ≤7d: {m90.get('acted_within_7d', 0)}")
        if m90.get("below_target_60pct"):
            st.error("Below 60% target — review queue load or SLAs.")
    st.json({"30d": m30, "90d": m90})

with tab_health:
    st.subheader("Collector runs (PRD §7.6)")
    with connection() as conn:
        from psycopg.rows import dict_row

        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT col.name AS collector, cr.started_at, cr.completed_at, cr.record_count, cr.status, cr.error_message
                FROM collector_runs cr
                JOIN collectors col ON col.id = cr.collector_id
                ORDER BY cr.started_at DESC
                LIMIT 100
                """
            )
            runs = cur.fetchall()
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT s.name, s.status, s.accept_rate_rolling, c.name AS collector, c.last_run_at, c.last_output_count, c.status AS collector_status
                FROM sources s
                LEFT JOIN collectors c ON c.source_id = s.id
                ORDER BY s.name
                """
            )
            h = cur.fetchall()
    st.markdown("**Latest runs**")
    st.dataframe(runs or [])
    st.markdown("**Sources / collectors**")
    st.dataframe(h or [])
    st.markdown("**Throttle proposals (PRD §16.2)**")
    try:
        pending = list_pending_throttle_proposals()
    except Exception as e:
        pending = []
        st.warning(str(e))
    st.dataframe(pending or [])
    prop_id = st.text_input("Confirm proposal UUID")
    op = st.text_input("Operator id", value="streamlit")
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Apply throttle") and prop_id.strip():
            st.json(confirm_throttle_proposal(proposal_id=prop_id.strip(), action="throttle", confirmed_by=op))
    with c2:
        if st.button("Apply disable") and prop_id.strip():
            st.json(confirm_throttle_proposal(proposal_id=prop_id.strip(), action="disable", confirmed_by=op))
    with c3:
        if st.button("Reject proposal") and prop_id.strip():
            st.json(confirm_throttle_proposal(proposal_id=prop_id.strip(), action="reject", confirmed_by=op))

with tab_eval:
    st.subheader("Eval runs (PRD §13)")
    with connection() as conn:
        from psycopg.rows import dict_row

        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT er.run_at, er.target_version, er.passed, er.scores_json, es.name AS eval_set
                FROM eval_runs er
                LEFT JOIN eval_sets es ON es.id = er.eval_set_id
                ORDER BY er.run_at DESC
                LIMIT 50
                """
            )
            ev = cur.fetchall()
    st.dataframe(ev or [])

with st.sidebar:
    st.header("Operator tools")
    if st.button("Run ranker (preview eligible clusters)"):
        try:
            cands = select_surface_candidates(limit=10)
            st.session_state["cands"] = cands
        except Exception as e:
            st.error(str(e))
    if st.session_state.get("cands"):
        st.json(st.session_state["cands"][:5])
    cid = st.text_input("Generate brief for cluster UUID")
    if st.button("Generate brief") and cid.strip():
        try:
            out = generate_brief_for_cluster(cid.strip())
            st.success(json.dumps(out))
        except Exception as e:
            st.error(str(e))
