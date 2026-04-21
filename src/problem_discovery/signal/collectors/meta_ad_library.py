"""Meta Ad Library — Tier 1 (META_AD_LIBRARY_TOKEN, Graph API ads_archive)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterator

import requests

from .protocol import Collector, HealthStatus, RawRecord


class MetaAdLibraryCollector(Collector):
    source_name = "meta_ad_library"
    tier = 1
    version = "0.1.0"
    cadence_cron = "0 12 * * *"

    def __init__(
        self,
        *,
        access_token: str | None,
        search_terms: str = "software",
        ad_reached_countries: str = "US",
        limit: int = 25,
        api_version: str = "v19.0",
    ) -> None:
        self.access_token = access_token
        self.search_terms = search_terms
        self.ad_reached_countries = ad_reached_countries
        self.limit = min(limit, 100)
        self.api_version = api_version

    def fetch(self, since: datetime | None, run_id: str) -> Iterator[RawRecord]:
        if not self.access_token:
            return
        url = f"https://graph.facebook.com/{self.api_version}/ads_archive"
        params: dict[str, Any] = {
            "access_token": self.access_token,
            "search_terms": self.search_terms,
            "ad_reached_countries": self.ad_reached_countries,
            "ad_active_status": "ALL",
            "fields": "id,ad_creation_time,ad_snapshot_url,page_name,ad_creative_bodies",
            "limit": self.limit,
        }
        r = requests.get(url, params=params, timeout=90)
        if r.status_code != 200:
            return
        data = r.json()
        for ad in data.get("data") or []:
            aid = str(ad.get("id") or "")
            if not aid:
                continue
            ts_s = ad.get("ad_creation_time")
            ts: datetime | None = None
            if ts_s:
                try:
                    ts = datetime.strptime(str(ts_s), "%Y-%m-%d").replace(tzinfo=timezone.utc)
                except ValueError:
                    ts = None
            if since and ts and ts < since:
                continue
            bodies = ad.get("ad_creative_bodies") or []
            text = " ".join(str(b) for b in bodies[:5])[:8000]
            yield RawRecord(
                external_id=aid[:180],
                source_timestamp=ts,
                url=str(ad.get("ad_snapshot_url") or f"https://www.facebook.com/ads/library/?id={aid}"),
                raw_payload={
                    "platform": "meta_ad_library",
                    "ad_id": aid,
                    "page_name": ad.get("page_name"),
                    "text": text,
                    "search_terms": self.search_terms,
                },
                metadata={"run_id": run_id},
            )

    def healthcheck(self) -> HealthStatus:
        if not self.access_token:
            return HealthStatus(ok=False, message="Set META_AD_LIBRARY_TOKEN")
        return HealthStatus(ok=True)
