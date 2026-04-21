"""PRD §8.1 — verbatim quote must be substring of raw."""

from __future__ import annotations

import json
from typing import Any


def flatten_raw_text(raw_payload: str | dict[str, Any]) -> str:
    if isinstance(raw_payload, str):
        try:
            obj = json.loads(raw_payload)
        except json.JSONDecodeError:
            return raw_payload
    else:
        obj = raw_payload
    if isinstance(obj, dict):
        return str(obj.get("text", "")) + " " + str(obj.get("title", ""))
    return str(obj)


def quote_is_verified(exact_quote: str | None, raw_payload: str | dict[str, Any]) -> bool:
    if not exact_quote:
        return False
    haystack = flatten_raw_text(raw_payload)
    return exact_quote in haystack
