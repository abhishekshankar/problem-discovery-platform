"""Polymarket Gamma API (public) — PRD §7.1 Tier 1."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterator

import requests

from .protocol import Collector, RawRecord


class PolymarketCollector(Collector):
    source_name = "polymarket"
    tier = 1
    version = "0.1.0"
    cadence_cron = "15 */4 * * *"

    def __init__(self, *, limit: int = 30) -> None:
        self.limit = limit

    def fetch(self, since: datetime | None, run_id: str) -> Iterator[RawRecord]:
        r = requests.get(
            "https://gamma-api.polymarket.com/events",
            params={"limit": self.limit, "closed": "false"},
            timeout=60,
            headers={"User-Agent": "signal-problem-discovery/0.1"},
        )
        r.raise_for_status()
        events = r.json()
        if not isinstance(events, list):
            return
        for ev in events:
            if not isinstance(ev, dict):
                continue
            eid = str(ev.get("id") or ev.get("slug") or "")
            title = str(ev.get("title") or ev.get("question") or "")
            desc = str(ev.get("description") or "")[:8000]
            ts: datetime | None = None
            if ev.get("createdAt") or ev.get("startDate"):
                raw = str(ev.get("createdAt") or ev.get("startDate"))
                try:
                    ts = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                except Exception:
                    ts = None
            if since and ts and ts < since:
                continue
            if not eid:
                continue
            yield RawRecord(
                external_id=eid[:180],
                source_timestamp=ts,
                url=f"https://polymarket.com/event/{ev.get('slug') or eid}",
                raw_payload={"platform": "polymarket", "id": eid, "title": title, "description": desc},
                metadata={"run_id": run_id},
            )
