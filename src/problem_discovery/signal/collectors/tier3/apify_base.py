"""Apify run-sync-get-dataset-items helper (PRD §7.3)."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Iterator

import requests

from ..protocol import Collector, HealthStatus, RawRecord


def _run_id_meta(run_id: str) -> dict[str, str]:
    return {"run_id": run_id}


class ApifyActorCollector(Collector):
    """POST run-sync-get-dataset-items for a given actor id."""

    source_name = "apify_actor"
    tier = 3
    version = "0.1.0"
    cadence_cron = "0 0 * * 0"

    def __init__(
        self,
        *,
        actor_id: str,
        run_input: dict[str, Any],
        token: str | None = None,
        source_label: str | None = None,
    ) -> None:
        self.actor_id = actor_id
        self.run_input = run_input
        self.token = token or os.environ.get("APIFY_TOKEN")
        self.source_name = source_label or f"apify_{actor_id.replace('/', '_')}"[:99]

    def fetch(self, since: datetime | None, run_id: str) -> Iterator[RawRecord]:
        _ = since
        if not self.token:
            return
        url = (
            f"https://api.apify.com/v2/acts/{self.actor_id}/"
            f"run-sync-get-dataset-items?token={self.token}"
        )
        r = requests.post(url, json=self.run_input, timeout=300)
        if r.status_code != 200:
            return
        try:
            items = r.json()
        except Exception:
            return
        if not isinstance(items, list):
            return
        for i, item in enumerate(items[:500]):
            if not isinstance(item, dict):
                continue
            ext = str(item.get("url") or item.get("id") or item.get("title") or f"item_{i}")[:180]
            yield RawRecord(
                external_id=ext,
                source_timestamp=datetime.now(timezone.utc),
                url=str(item.get("url") or "") or None,
                raw_payload={"platform": "apify", "actor": self.actor_id, "item": item},
                metadata=_run_id_meta(run_id),
            )

    def healthcheck(self) -> HealthStatus:
        if not self.token:
            return HealthStatus(ok=False, message="Set APIFY_TOKEN")
        return HealthStatus(ok=True)
