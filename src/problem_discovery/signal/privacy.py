"""Pseudonymization for EU-origin sources (PRD §17.2)."""

from __future__ import annotations

import copy
import hashlib
import hmac
import json
from typing import Any

_SENSITIVE_KEYS = frozenset(
    {"author", "username", "user", "commenter", "name", "author_name", "user_name", "display_name"}
)


def pseudonymize_payload(raw_payload: dict[str, Any], salt: str) -> dict[str, Any]:
    """
    Return a deep copy of payload with string values under sensitive keys replaced by
    deterministic HMAC-SHA256 hex digests (first 32 chars), keyed by salt.
    Recurses into dicts and lists.
    """
    if not salt:
        return copy.deepcopy(raw_payload)

    def _token(value: str) -> str:
        digest = hmac.new(salt.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"pseudo_{digest[:32]}"

    def _walk(obj: Any) -> Any:
        if isinstance(obj, dict):
            out: dict[str, Any] = {}
            for k, v in obj.items():
                lk = str(k).lower()
                if lk in _SENSITIVE_KEYS and isinstance(v, str) and v.strip():
                    out[k] = _token(v)
                else:
                    out[k] = _walk(v)
            return out
        if isinstance(obj, list):
            return [_walk(x) for x in obj]
        return obj

    return _walk(copy.deepcopy(raw_payload))


def author_pseudonym_from_payload(raw_payload: Any, salt: str) -> str | None:
    """Best-effort single pseudonym for DB column from first sensitive string in payload."""
    if not salt:
        return None
    if isinstance(raw_payload, str):
        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError:
            return None
    elif isinstance(raw_payload, dict):
        payload = raw_payload
    else:
        return None

    def _find(d: Any) -> str | None:
        if isinstance(d, dict):
            for k, v in d.items():
                if str(k).lower() in _SENSITIVE_KEYS and isinstance(v, str) and v.strip():
                    return v
                got = _find(v)
                if got:
                    return got
        elif isinstance(d, list):
            for x in d:
                got = _find(x)
                if got:
                    return got
        return None

    raw = _find(payload)
    if not raw:
        return None
    digest = hmac.new(salt.encode("utf-8"), raw.encode("utf-8"), hashlib.sha256).hexdigest()
    return digest[:64]
