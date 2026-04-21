"""Anthropic Message Batches for Sonnet extraction (PRD §8.1 batch discount)."""

from __future__ import annotations

import json
import time
from typing import Any

import requests

from ..settings import SignalSettings, get_settings
from .llm_extract import _parse_json_loose, build_extractor_user_prompt, message_blocks_to_text


def _anthropic_client(settings: SignalSettings | None = None):
    import anthropic

    s = settings or get_settings()
    if not s.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is required for batch extraction")
    return anthropic.Anthropic(api_key=s.anthropic_api_key), s


def build_batch_requests(
    candidates: list[tuple[int, str, str]],
    *,
    source_label: str,
    settings: SignalSettings | None = None,
) -> list[dict[str, Any]]:
    """
    candidates: (raw_signal_id, prompt_variant, raw_text)
    Returns list of Request dicts for client.messages.batches.create(requests=...)
    """
    s = settings or get_settings()
    out: list[dict[str, Any]] = []
    for rid, variant, raw_text in candidates:
        prompt = build_extractor_user_prompt(
            source_label=source_label, raw_text=raw_text, prompt_variant=variant
        )
        out.append(
            {
                "custom_id": str(rid),
                "params": {
                    "model": s.anthropic_model_extract,
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": prompt}],
                },
            }
        )
    return out


def submit_extraction_batch(
    candidates: list[tuple[int, str, str]],
    *,
    source_label: str,
    settings: SignalSettings | None = None,
) -> str:
    """Create a Message Batch; returns message_batch_id."""
    client, _ = _anthropic_client(settings)
    reqs = build_batch_requests(candidates, source_label=source_label, settings=settings)
    if not reqs:
        raise ValueError("No batch requests")
    batch = client.messages.batches.create(requests=reqs)
    return str(batch.id)


def poll_batch_until_ended(
    message_batch_id: str,
    *,
    poll_interval_sec: float = 15.0,
    max_wait_sec: float = 7200.0,
    settings: SignalSettings | None = None,
) -> dict[str, Any]:
    client, _ = _anthropic_client(settings)
    deadline = time.monotonic() + max_wait_sec
    last: Any = None
    while time.monotonic() < deadline:
        last = client.messages.batches.retrieve(message_batch_id)
        if last.processing_status == "ended":
            return {
                "id": last.id,
                "processing_status": last.processing_status,
                "results_url": last.results_url,
                "request_counts": last.request_counts.model_dump() if last.request_counts else {},
            }
        time.sleep(poll_interval_sec)
    raise TimeoutError(f"Batch {message_batch_id} did not finish within {max_wait_sec}s; last={last}")


def download_batch_results_jsonl(results_url: str, *, settings: SignalSettings | None = None) -> list[dict[str, Any]]:
    s = settings or get_settings()
    if not s.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is required")
    r = requests.get(
        results_url,
        headers={
            "x-api-key": s.anthropic_api_key,
            "anthropic-version": "2023-06-01",
        },
        timeout=120,
    )
    r.raise_for_status()
    lines: list[dict[str, Any]] = []
    for line in r.text.splitlines():
        line = line.strip()
        if not line:
            continue
        lines.append(json.loads(line))
    return lines


def parse_batch_jsonl_to_extractions(lines: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Map custom_id (raw_signal id str) -> parsed extraction dict (or empty if error)."""
    out: dict[str, dict[str, Any]] = {}
    for row in lines:
        cid = str(row.get("custom_id", ""))
        result = row.get("result") or {}
        rtype = result.get("type")
        if rtype != "succeeded":
            out[cid] = {"is_problem_signal": False, "_batch_error": result}
            continue
        msg = result.get("message")
        if not msg:
            out[cid] = {"is_problem_signal": False}
            continue
        # SDK returns dict when from JSONL
        content = msg.get("content") if isinstance(msg, dict) else None
        text = ""
        if content:
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text += block.get("text", "")
        elif hasattr(msg, "content"):
            text = message_blocks_to_text(msg)
        out[cid] = _parse_json_loose(text)
    return out
