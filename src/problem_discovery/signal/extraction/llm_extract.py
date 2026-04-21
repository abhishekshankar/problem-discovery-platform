"""Pass 3 — structured extraction via Anthropic (PRD §8.2)."""

from __future__ import annotations

import json
import re
from typing import Any

from ..settings import SignalSettings, get_settings

EXTRACTOR_JSON_SCHEMA_HINT = """
Return a single JSON object with keys:
is_problem_signal (bool),
problem_statement (string or null),
exact_quote (string or null),
specificity_score (number 1-10 or null),
wtp_level (one of: none, weak, strong, proven),
wtp_evidence (string or null),
layer (one of: unformed, formed, frustrated, paying),
domain_tags (array of strings),
buyer_hint (string or null),
workaround_described (string or null),
admiralty_source_reliability (single letter A-F or null),
admiralty_info_credibility (integer 1-6 or null)
"""


def haiku_problem_signal_gate(
    *,
    source_label: str,
    raw_text: str,
    settings: SignalSettings | None = None,
) -> bool:
    """Fast Haiku yes/no before expensive Sonnet extraction (PRD §8.1)."""
    s = settings or get_settings()
    if not s.anthropic_api_key:
        return True
    try:
        import anthropic
    except ImportError as e:
        raise RuntimeError("anthropic package required") from e

    client = anthropic.Anthropic(api_key=s.anthropic_api_key)
    prompt = f"""Does the following {source_label} text describe a concrete workflow/product problem
( friction, workaround, tool gap, cost of manual process ) — not marketing, hiring, or pure venting without workflow?
Answer JSON only: {{"is_problem_signal": true or false}}

Text:
---
{raw_text[:8000]}
---
"""
    msg = client.messages.create(
        model=s.anthropic_model_haiku,
        max_tokens=64,
        messages=[{"role": "user", "content": prompt}],
    )
    text = ""
    for block in msg.content:
        if hasattr(block, "text"):
            text += block.text
    data = _parse_json_loose(text)
    return bool(data.get("is_problem_signal"))


def build_extractor_user_prompt(
    *,
    source_label: str,
    raw_text: str,
    prompt_variant: str = "default",
) -> str:
    """Full user message for Sonnet extraction (sync or Message Batches)."""
    variant_note = f"\n(prompt_variant={prompt_variant})\n" if prompt_variant != "default" else ""
    return f"""You are extracting one problem signal from a {source_label} post.
{variant_note}
Rules:
1. The "exact_quote" field MUST be a verbatim contiguous substring of the input.
   If no such quote exists that describes a problem, set is_problem_signal=false.

2. "problem_statement" must be one sentence. Specific. No solution mentioned.

3. specificity_score (1-10): 1-3 vague, 4-6 workflow without cost, 7-10 tool+workflow+cost/time.

4. wtp_level: none | weak | strong | proven per PRD §8.2.

5. layer: unformed | formed | frustrated | paying.

6. Set is_problem_signal=false for marketing, off-topic, announcements, pure venting without workflow.

{EXTRACTOR_JSON_SCHEMA_HINT}

Input:
---
{raw_text}
---
"""


def extract_problem_from_raw(
    *,
    source_label: str,
    raw_text: str,
    settings: SignalSettings | None = None,
    prompt_variant: str = "default",
) -> dict[str, Any]:
    s = settings or get_settings()
    if not s.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    try:
        import anthropic
    except ImportError as e:
        raise RuntimeError("anthropic package required") from e

    client = anthropic.Anthropic(api_key=s.anthropic_api_key)
    prompt = build_extractor_user_prompt(
        source_label=source_label, raw_text=raw_text, prompt_variant=prompt_variant
    )
    msg = client.messages.create(
        model=s.anthropic_model_extract,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    text = ""
    for block in msg.content:
        if hasattr(block, "text"):
            text += block.text
    return _parse_json_loose(text)


def _parse_json_loose(text: str) -> dict[str, Any]:
    text = text.strip()
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return {"is_problem_signal": False, "problem_statement": None, "exact_quote": None}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {"is_problem_signal": False, "problem_statement": None, "exact_quote": None}


def message_blocks_to_text(msg: Any) -> str:
    """Extract text from Anthropic Message content blocks."""
    parts: list[str] = []
    for block in getattr(msg, "content", []) or []:
        if hasattr(block, "text"):
            parts.append(block.text)
    return "".join(parts)


def stub_extraction_for_dev(raw_text: str) -> dict[str, Any]:
    """When LLM unavailable: minimal record for plumbing tests."""
    snippet = raw_text[:200] if raw_text else ""
    return {
        "is_problem_signal": bool(snippet),
        "problem_statement": snippet[:120] + ("…" if len(snippet) > 120 else ""),
        "exact_quote": snippet[:80] if snippet else None,
        "specificity_score": 5,
        "wtp_level": "weak",
        "wtp_evidence": None,
        "layer": "formed",
        "domain_tags": [],
        "buyer_hint": None,
        "workaround_described": None,
        "admiralty_source_reliability": "C",
        "admiralty_info_credibility": 3,
    }
