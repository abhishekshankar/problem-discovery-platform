"""Product Hunt GraphQL API."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Iterator

import requests

from ..protocol import Collector, HealthStatus, RawRecord


class ProductHuntCollector(Collector):
    source_name = "producthunt"
    tier = 3
    version = "0.1.0"
    cadence_cron = "0 7 * * *"

    def __init__(self, *, token: str | None = None, posts_first: int = 15) -> None:
        self.token = token or os.environ.get("PRODUCTHUNT_TOKEN")
        self.posts_first = min(posts_first, 20)

    def fetch(self, since: datetime | None, run_id: str) -> Iterator[RawRecord]:
        _ = since
        if not self.token:
            return
        q = """
        query ($n: Int!) {
          posts(first: $n) {
            edges { node { id name tagline description url createdAt votesCount } }
          }
        }
        """
        r = requests.post(
            "https://api.producthunt.com/v2/api/graphql",
            json={"query": q, "variables": {"n": self.posts_first}},
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "User-Agent": "signal-problem-discovery/0.1",
            },
            timeout=60,
        )
        if r.status_code != 200:
            return
        data = r.json() if r.content else {}
        edges = (((data.get("data") or {}).get("posts") or {}).get("edges")) or []
        for edge in edges:
            node = (edge or {}).get("node") or {}
            pid = str(node.get("id") or "")
            if not pid:
                continue
            ts_s = node.get("createdAt")
            ts = datetime.now(timezone.utc)
            if ts_s:
                try:
                    ts = datetime.fromisoformat(str(ts_s).replace("Z", "+00:00"))
                except Exception:
                    pass
            yield RawRecord(
                external_id=pid[:180],
                source_timestamp=ts,
                url=str(node.get("url") or f"https://www.producthunt.com/posts/{node.get('name')}"),
                raw_payload={
                    "platform": "producthunt",
                    "name": node.get("name"),
                    "tagline": node.get("tagline"),
                    "description": node.get("description"),
                    "votes": node.get("votesCount"),
                },
                metadata={"run_id": run_id},
            )

    def healthcheck(self) -> HealthStatus:
        if not self.token:
            return HealthStatus(ok=False, message="Set PRODUCTHUNT_TOKEN")
        return HealthStatus(ok=True)
