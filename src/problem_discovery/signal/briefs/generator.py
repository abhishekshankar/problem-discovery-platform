"""Opus cluster briefs with quote verification (PRD §11)."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from psycopg.rows import dict_row

from ..db import connection
from ..settings import SignalSettings, get_settings


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_json_loose(text: str) -> dict[str, Any]:
    text = text.strip()
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}


def _verify_quotes_in_brief(brief_md: str, quotes: list[str]) -> bool:
    blob = brief_md.lower()
    for q in quotes:
        if not q or q.lower() not in blob.lower():
            return False
    return True


def _verify_brief_sections(brief_md: str, contradicting_text: str, open_questions: list[str]) -> bool:
    """PRD §11.3 — mandatory sections present."""
    if "## contradicting evidence" not in brief_md.lower():
        return False
    if "## open questions" not in brief_md.lower():
        return False
    ct = (contradicting_text or "").strip()
    no_ev = "No disconfirming evidence found in member quotes."
    if no_ev not in brief_md and len(ct) < 12:
        return False
    if len([x for x in open_questions if str(x).strip()]) < 3:
        return False
    return True


def _generate_contradicting_evidence(
    client: Any,
    *,
    model: str,
    quotes: list[str],
    cluster_id: str,
) -> str:
    """Second Opus pass — disconfirming signals from member quotes only."""
    quotes_blob = "\n".join(f"- {q[:2000]}" for q in quotes[:40] if q)
    prompt = f"""You analyze member quotes for a problem-discovery cluster.

Return JSON with a single key "contradicting_evidence" (string, markdown plain text, no heading).

Rules:
- Cite tensions, counterexamples, or quotes that weaken the apparent problem narrative, using ONLY the quotes below.
- If there are no disconfirming signals in these quotes, the value must be EXACTLY this sentence (nothing else):
  No disconfirming evidence found in member quotes.

Member quotes:
{quotes_blob[:14000]}

Cluster id (context only): {cluster_id}
"""
    msg = client.messages.create(
        model=model,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    text = ""
    for block in msg.content:
        if hasattr(block, "text"):
            text += block.text
    data = _parse_json_loose(text)
    out = str(data.get("contradicting_evidence", "")).strip()
    if not out:
        return "No disconfirming evidence found in member quotes."
    return out


def generate_brief_for_cluster(
    cluster_id: str,
    *,
    settings: SignalSettings | None = None,
    max_attempts: int = 2,
) -> dict[str, Any]:
    s = settings or get_settings()
    if not s.database_url:
        raise RuntimeError("DATABASE_URL is required")
    if not s.anthropic_api_key or s.extraction_use_stub:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is required for brief generation (PRD §11). "
            "Unset SIGNAL_EXTRACTION_STUB for production briefs."
        )

    with connection(autocommit=True) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT e.exact_quote, e.layer, e.problem_statement, e.buyer_hint, e.workaround_described,
                       e.admiralty_source_reliability, e.admiralty_info_credibility,
                       s.name AS source_name, r.source_timestamp, r.source_id
                FROM cluster_members m
                JOIN extracted_problems e ON e.id = m.extracted_problem_id
                JOIN raw_signals_index r ON r.id = e.raw_signal_id
                JOIN sources s ON s.id = r.source_id
                WHERE m.cluster_id = %s::uuid AND e.is_problem_signal IS TRUE
                ORDER BY m.added_at
                LIMIT 50
                """,
                (cluster_id,),
            )
            rows = cur.fetchall()
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT COALESCE(is_exploration, FALSE) AS is_exploration,
                       member_count_last_14d, deviation_from_baseline_sigma
                FROM clusters WHERE id = %s::uuid
                """,
                (cluster_id,),
            )
            stats = dict(cur.fetchone() or {})

    creds = [float(r["admiralty_info_credibility"]) for r in rows if r.get("admiralty_info_credibility") is not None]
    rels = [str(r["admiralty_source_reliability"]) for r in rows if r.get("admiralty_source_reliability")]
    avg_cred = round(sum(creds) / len(creds), 2) if creds else None
    rel_summary = ",".join(sorted(set(rels))) if rels else "n/a"
    n_sources = len({r["source_id"] for r in rows if r.get("source_id") is not None})

    quotes = [str(r["exact_quote"]) for r in rows if r.get("exact_quote")]
    evidence_lines = "\n".join(
        f"- layer={r.get('layer')} source={r.get('source_name')} ts={r.get('source_timestamp')}: "
        f"quote={r.get('exact_quote')} buyer_hint={r.get('buyer_hint')} "
        f"workaround={r.get('workaround_described')} problem={r.get('problem_statement')}"
        for r in rows[:35]
    )

    try:
        import anthropic
    except ImportError as e:
        raise RuntimeError("anthropic package required") from e

    client = anthropic.Anthropic(api_key=s.anthropic_api_key)
    verified = False
    brief_md = ""
    interview: list[str] = []
    open_questions: list[str] = []
    contradicting_body = ""
    attempts = 0

    exploration_note = ""
    if stats.get("is_exploration"):
        exploration_note = (
            "\nIMPORTANT: This cluster is flagged **exploration** (PRD §16.4) — "
            "it may not match the operator's typical preferences; say so under Canonical problem.\n"
        )

    for attempt in range(max_attempts):
        attempts = attempt + 1
        prompt = f"""You are writing a cluster brief for a single-user problem discovery system.
Follow this EXACT markdown structure (PRD §11.3):

# Cluster: <short title>

## Canonical problem
One sentence. If exploration cluster, note that explicitly.

## Evidence
### Layer 1 (unformed): N signals from <sources>
> "verbatim quote" — source, date
(repeat for formed / frustrated / paying as applicable — use only evidence lines below)

## Who appears to be the buyer
Synthesize from buyer_hint fields.

## Existing solutions named in signals
Bullets from workarounds / problem_statement (tools, vendors). If none named, say "None named explicitly."

## Admiralty assessment
- Source reliability letters seen: {rel_summary}
- Avg information credibility (1-6): {avg_cred}
- Independent platforms represented: {n_sources}
- Distinct contributing records in sample: {len(rows)}

## Growth signal
- member_count_last_14d (from DB): {stats.get('member_count_last_14d')}
- deviation sigma (from DB): {stats.get('deviation_from_baseline_sigma')}

## Interview prompts
Exactly 5 numbered prompts (Past behavior, Workaround, Ranking, Trigger, Commitment test — PRD §11.3).

Do NOT include "## Contradicting evidence" or "## Open questions" in brief_markdown — those are appended by the system.

Rules:
- Use ONLY verbatim quotes from the evidence block for quoted lines in ## Evidence.
- Do not invent quotes or URLs.
{exploration_note}
Evidence (ground truth quotes and fields):
{evidence_lines[:12000]}

Return JSON with keys:
- brief_markdown (string, markdown through ## Interview prompts inclusive)
- interview_prompts (array of 5 strings)

Cluster id: {cluster_id}
"""
        msg = client.messages.create(
            model=s.anthropic_model_brief,
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}],
        )
        text = ""
        for block in msg.content:
            if hasattr(block, "text"):
                text += block.text
        data = _parse_json_loose(text)
        brief_md = str(data.get("brief_markdown", "")).strip()
        interview = [str(x).strip() for x in (data.get("interview_prompts") or []) if str(x).strip()]
        open_questions: list[str] = []
        for i in range(3):
            if i < len(interview):
                open_questions.append(interview[i])
            elif interview:
                open_questions.append(interview[-1])
            else:
                open_questions.append("What evidence would falsify this cluster's problem narrative?")
        contradicting_body = _generate_contradicting_evidence(
            client, model=s.anthropic_model_brief, quotes=quotes, cluster_id=cluster_id
        )
        oq_block = "\n".join(f"- {q}" for q in open_questions[:3])
        brief_md = (
            f"{brief_md.rstrip()}\n\n## Contradicting evidence (mandatory)\n\n{contradicting_body}\n\n"
            f"## Open questions to validate\n\n{oq_block}\n"
        )
        if _verify_quotes_in_brief(brief_md, [q for q in quotes[:10] if len(q) > 10]) and _verify_brief_sections(
            brief_md, contradicting_body, open_questions[:3]
        ):
            verified = True
            break

    brief_id = str(uuid.uuid4())
    interview_payload = {"prompts": interview, "open_questions": open_questions[:3]}
    with connection(autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO cluster_briefs (
                  id, cluster_id, generated_at, model_identifier, brief_markdown,
                  interview_prompts_json, verification_attempts, verification_failed
                )
                VALUES (%s::uuid, %s::uuid, NOW(), %s, %s, %s::jsonb, %s, %s)
                """,
                (
                    brief_id,
                    cluster_id,
                    s.anthropic_model_brief,
                    brief_md,
                    json.dumps(interview_payload),
                    attempts,
                    not verified,
                ),
            )
            cur.execute(
                "UPDATE clusters SET status = 'surfaced', surfaced_at = NOW() WHERE id = %s::uuid",
                (cluster_id,),
            )
        conn.commit()

    return {"brief_id": brief_id, "verified": verified, "attempts": attempts}
