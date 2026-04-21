"""YouTube Data API v3 search — PRD §7.1 Tier 1 (requires YOUTUBE_DATA_API_KEY)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterator

import requests

from .protocol import Collector, HealthStatus, RawRecord


class YouTubeDataCollector(Collector):
    source_name = "youtube_data"
    tier = 1
    version = "0.1.0"
    cadence_cron = "0 8 * * *"

    def __init__(self, *, api_key: str | None, query: str = "healthcare software problems", max_items: int = 25) -> None:
        self.api_key = api_key
        self.query = query
        self.max_items = max_items

    def fetch(self, since: datetime | None, run_id: str) -> Iterator[RawRecord]:
        if not self.api_key:
            return
        url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            "part": "snippet",
            "type": "video",
            "q": self.query,
            "maxResults": self.max_items,
            "key": self.api_key,
        }
        r = requests.get(url, params=params, timeout=60, headers={"User-Agent": "signal-problem-discovery/0.1"})
        if r.status_code != 200:
            return
        data = r.json()
        for item in data.get("items") or []:
            iid = item.get("id")
            vid = str(iid.get("videoId", "")) if isinstance(iid, dict) else ""
            sn = item.get("snippet") or {}
            title = str(sn.get("title") or "")
            desc = str(sn.get("description") or "")
            ts_s = sn.get("publishedAt")
            ts: datetime | None = None
            if ts_s:
                try:
                    ts = datetime.fromisoformat(str(ts_s).replace("Z", "+00:00"))
                except Exception:
                    ts = None
            if since and ts and ts < since:
                continue
            if not vid:
                continue
            link = f"https://www.youtube.com/watch?v={vid}"
            yield RawRecord(
                external_id=vid,
                source_timestamp=ts,
                url=link,
                raw_payload={"platform": "youtube", "video_id": vid, "title": title, "description": desc[:4000]},
                metadata={"run_id": run_id},
            )

    def healthcheck(self) -> HealthStatus:
        if not self.api_key:
            return HealthStatus(ok=False, message="Set YOUTUBE_DATA_API_KEY")
        return HealthStatus(ok=True)
