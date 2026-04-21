"""Google Ads Transparency (public report API) — Tier 1, no API key."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Iterator

import requests

from .protocol import Collector, HealthStatus, RawRecord


class GoogleAdsTransparencyCollector(Collector):
    """
    Fetches JSON from the political-ads transparency API used by transparencyreport.google.com.
    Override `endpoint` via GOOGLE_ADS_TRANSPARENCY_ENDPOINT if Google changes paths.
    """

    source_name = "google_ads_transparency"
    tier = 1
    version = "0.1.0"
    cadence_cron = "0 14 * * *"

    def __init__(self, *, search_query: str = "technology", endpoint: str | None = None) -> None:
        self.search_query = search_query
        self.endpoint = endpoint or (
            "https://transparencyreport.google.com/political-ads/api/v1/advertiser/search"
        )

    def fetch(self, since: datetime | None, run_id: str) -> Iterator[RawRecord]:
        params = {"query": self.search_query}
        r = requests.get(
            self.endpoint,
            params=params,
            timeout=60,
            headers={"User-Agent": "SignalProblemDiscovery/0.1 (research)"},
        )
        if r.status_code != 200:
            return
        try:
            payload: Any = r.json()
        except json.JSONDecodeError:
            return
        items = payload if isinstance(payload, list) else payload.get("advertisers") or payload.get("results") or []
        if isinstance(payload, dict) and not items:
            items = payload.get("data") or []
        for i, row in enumerate(items if isinstance(items, list) else []):
            if not isinstance(row, dict):
                continue
            rid = str(row.get("id") or row.get("advertiserId") or row.get("name") or f"row_{i}")
            name = str(row.get("name") or row.get("advertiserName") or rid)
            ts = datetime.now(timezone.utc)
            yield RawRecord(
                external_id=rid[:180],
                source_timestamp=ts,
                url="https://transparencyreport.google.com/political-ads/home",
                raw_payload={"platform": "google_ads_transparency", "advertiser": row, "search_query": self.search_query},
                metadata={"run_id": run_id},
            )
            if i >= 49:
                break

    def healthcheck(self) -> HealthStatus:
        return HealthStatus(ok=True)
