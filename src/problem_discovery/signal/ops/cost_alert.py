"""Cost blowout alert — PRD §21."""

from __future__ import annotations

from typing import Any

from psycopg.rows import dict_row

from ..db import connection
from ..settings import SignalSettings, get_settings
from .notify import send_slack_message


def check_cost_baseline(
    *,
    current_month_llm_usd: float | None = None,
    settings: SignalSettings | None = None,
) -> dict[str, Any]:
    """Alert if spend >150% of baseline (operator passes current_month_llm_usd from invoice)."""
    s = settings or get_settings()
    if not s.database_url:
        return {"ok": True, "note": "no database"}

    baseline = 50.0
    with connection(autocommit=True) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT monthly_llm_usd FROM cost_baselines WHERE singleton_lock = 1 LIMIT 1")
            row = cur.fetchone()
            if row and row.get("monthly_llm_usd") is not None:
                baseline = float(row["monthly_llm_usd"])

    if current_month_llm_usd is None:
        return {"ok": True, "baseline_llm_usd": baseline, "note": "pass current_month_llm_usd to check"}

    ratio = current_month_llm_usd / max(baseline, 1e-6)
    triggered = ratio >= 1.5
    if triggered:
        send_slack_message(
            f"Signal cost alert: LLM spend ${current_month_llm_usd:.2f} is {ratio:.0%} of baseline ${baseline:.2f}",
            settings=s,
        )
    return {"ok": not triggered, "ratio": ratio, "baseline_llm_usd": baseline}
