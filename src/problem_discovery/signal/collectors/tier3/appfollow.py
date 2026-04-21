"""AppFollow REST API — APPFOLLOW_TOKEN."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Iterator

import requests

from ..protocol import Collector, HealthStatus, RawRecord


class AppFollowCollector(Collector):
    source_name = "appfollow"
    tier = 3
    version = "0.1.0"
    cadence_cron = "0 8 * * *"

    def __init__(self, *, token: str | None = None, ext_store_id: str = "284882215", country: str = "us") -> None:
        self.token = token or os.environ.get("APPFOLLOW_TOKEN")
        self.ext_store_id = ext_store_id
        self.country = country

    def fetch(self, since: datetime | None, run_id: str) -> Iterator[RawRecord]:
        _ = since
        if not self.token:
            return
        url = "https://api.appfollow.io/api/v2/reviews"
        params: dict[str, Any] = {
            "ext_id": self.ext_store_id,
            "country": self.country,
            "lang": "en",
            "limit": 30,
        }
        r = requests.get(
            url,
            params=params,
            headers={"Authorization": f"Bearer {self.token}", "User-Agent": "signal-problem-discovery/0.1"},
            timeout=60,
        )
        if r.status_code != 200:
            return
        data = r.json() if r.content else {}
        reviews = data.get("reviews") or data.get("list") or []
        if isinstance(data, list):
            reviews = data
        for rev in reviews[:50]:
            if not isinstance(rev, dict):
                continue
            rid = str(rev.get("id") or rev.get("review_id") or "")
            if not rid:
                continue
            yield RawRecord(
                external_id=f"{self.ext_store_id}_{rid}"[:180],
                source_timestamp=datetime.now(timezone.utc),
                url=str(rev.get("url") or ""),
                raw_payload={"platform": "appfollow", "store_id": self.ext_store_id, "review": rev},
                metadata={"run_id": run_id},
            )

    def healthcheck(self) -> HealthStatus:
        if not self.token:
            return HealthStatus(ok=False, message="Set APPFOLLOW_TOKEN")
        return HealthStatus(ok=True)
