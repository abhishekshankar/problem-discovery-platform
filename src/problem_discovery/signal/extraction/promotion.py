"""Extractor canary rollout in DB (PRD §14.2)."""

from __future__ import annotations

import json
from typing import Any

from psycopg.rows import dict_row

from ..db import connection
from ..settings import SignalSettings, get_settings


def get_effective_candidate_rollout_fraction(conn: Any, settings: SignalSettings) -> float:
    """
    Fraction of records that receive the candidate prompt variant (deterministic hash routing).
    If DB value is 0, fall back to SIGNAL_CANARY_FRACTION env.
    If DB value is 1.0, all records use candidate.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT candidate_rollout_fraction FROM extractor_promotion_state WHERE singleton_lock = 1 LIMIT 1"
        )
        row = cur.fetchone()
    dbv = float(row[0]) if row and row[0] is not None else 0.0
    if dbv <= 0:
        return float(settings.extraction_canary_fraction)
    return min(1.0, max(0.0, dbv))


def record_eval_outcome(*, passed: bool, eval_run_id: str | None = None) -> None:
    with connection(autocommit=True) as conn:
        with conn.cursor() as cur:
            if eval_run_id:
                cur.execute(
                    """
                    UPDATE extractor_promotion_state
                    SET last_eval_passed = %s, last_eval_run_id = %s::uuid, updated_at = NOW()
                    WHERE singleton_lock = 1
                    """,
                    (passed, eval_run_id),
                )
            else:
                cur.execute(
                    """
                    UPDATE extractor_promotion_state
                    SET last_eval_passed = %s, last_eval_run_id = NULL, updated_at = NOW()
                    WHERE singleton_lock = 1
                    """,
                    (passed,),
                )


def advance_rollout_after_passing_eval() -> dict[str, Any]:
    """After Set A passes: 0 -> 0.1 -> 0.5 -> 1.0 (PRD §14.2)."""
    with connection(autocommit=True) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT candidate_rollout_fraction FROM extractor_promotion_state WHERE singleton_lock = 1"
            )
            row = cur.fetchone()
            cur_frac = float(row["candidate_rollout_fraction"] or 0) if row else 0.0

        if cur_frac < 0.05:
            new_frac = 0.1
        elif cur_frac < 0.2:
            new_frac = 0.5
        elif cur_frac < 0.75:
            new_frac = 1.0
        else:
            new_frac = 1.0

        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE extractor_promotion_state
                SET candidate_rollout_fraction = %s, last_eval_passed = TRUE, updated_at = NOW()
                WHERE singleton_lock = 1
                """,
                (new_frac,),
            )
    return {"previous_fraction": cur_frac, "new_fraction": new_frac}


def _attach_eval_scores_to_latest_extraction_run(scores: dict[str, Any], settings: SignalSettings) -> str | None:
    """Persist Set A scores on the most recently completed extraction_run (joinable audit)."""
    if not settings.database_url:
        return None
    with connection(autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE extraction_runs
                SET eval_scores_json = %s::jsonb
                WHERE id = (
                  SELECT id FROM extraction_runs
                  WHERE completed_at IS NOT NULL
                  ORDER BY completed_at DESC NULLS LAST
                  LIMIT 1
                )
                RETURNING id::text
                """,
                (json.dumps(scores),),
            )
            row = cur.fetchone()
    return str(row[0]) if row and row[0] else None


def canary_promote_run_eval_and_maybe_advance(
    *,
    jsonl_path: Any = None,
    week2_gate: bool = True,
    settings: SignalSettings | None = None,
) -> dict[str, Any]:
    """Run Set A; on pass, advance rollout one step."""
    from ..evals.runner import run_extractor_eval

    s = settings or get_settings()
    out = run_extractor_eval(jsonl_path, target_version="canary_promote", week2_gate=week2_gate, settings=s)
    passed = bool(out.get("passed"))
    record_eval_outcome(passed=passed, eval_run_id=out.get("eval_run_id"))
    extraction_run_id = _attach_eval_scores_to_latest_extraction_run(out.get("scores") or {}, s)
    advance: dict[str, Any] | None = None
    if passed:
        advance = advance_rollout_after_passing_eval()
    return {"eval": out, "advanced": advance, "eval_scores_attached_extraction_run_id": extraction_run_id}


def reset_rollout_to_env_only() -> None:
    with connection(autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE extractor_promotion_state
                SET candidate_rollout_fraction = 0, updated_at = NOW()
                WHERE singleton_lock = 1
                """
            )


def get_promotion_status() -> dict[str, Any]:
    with connection(autocommit=True) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT candidate_rollout_fraction, last_eval_passed, last_eval_run_id, notes, updated_at
                FROM extractor_promotion_state WHERE singleton_lock = 1
                """
            )
            row = cur.fetchone()
    return dict(row) if row else {}
