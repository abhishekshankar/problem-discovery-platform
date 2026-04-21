"""YouTube commentThreads — Tier 1 (YOUTUBE_DATA_API_KEY); distinct from video search collector."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterator

import requests

from .protocol import Collector, HealthStatus, RawRecord


class YouTubeCommentsCollector(Collector):
    source_name = "youtube_comments"
    tier = 1
    version = "0.1.0"
    cadence_cron = "0 */6 * * *"

    def __init__(
        self,
        *,
        api_key: str | None,
        channel_ids: list[str] | None = None,
        video_ids: list[str] | None = None,
        max_comments_per_video: int = 50,
    ) -> None:
        self.api_key = api_key
        self.channel_ids = channel_ids or []
        self.video_ids = video_ids or []
        self.max_comments_per_video = max_comments_per_video

    def fetch(self, since: datetime | None, run_id: str) -> Iterator[RawRecord]:
        if not self.api_key or not self.video_ids:
            return
        base = "https://www.googleapis.com/youtube/v3/commentThreads"
        for vid in self.video_ids:
            params = {
                "part": "snippet",
                "videoId": vid,
                "maxResults": min(self.max_comments_per_video, 100),
                "order": "relevance",
                "textFormat": "plainText",
                "key": self.api_key,
            }
            r = requests.get(base, params=params, timeout=60, headers={"User-Agent": "signal-problem-discovery/0.1"})
            if r.status_code != 200:
                continue
            data = r.json()
            for item in data.get("items") or []:
                sn = (item.get("snippet") or {}).get("topLevelComment", {}).get("snippet") or {}
                cid = str(item.get("id") or "")
                text = str(sn.get("textDisplay") or sn.get("textOriginal") or "")
                author = str(sn.get("authorDisplayName") or "")
                ts_s = sn.get("publishedAt")
                ts: datetime | None = None
                if ts_s:
                    try:
                        ts = datetime.fromisoformat(str(ts_s).replace("Z", "+00:00"))
                    except Exception:
                        ts = None
                if since and ts and ts < since:
                    continue
                if not cid or not text.strip():
                    continue
                yield RawRecord(
                    external_id=f"{vid}_{cid}"[:180],
                    source_timestamp=ts,
                    url=f"https://www.youtube.com/watch?v={vid}&lc={cid}",
                    raw_payload={
                        "platform": "youtube_comment",
                        "video_id": vid,
                        "comment_id": cid,
                        "text": text[:8000],
                        "author": author,
                        "channel_ids_config": self.channel_ids,
                    },
                    metadata={"run_id": run_id},
                )

    def healthcheck(self) -> HealthStatus:
        if not self.api_key:
            return HealthStatus(ok=False, message="Set YOUTUBE_DATA_API_KEY")
        if not self.video_ids:
            return HealthStatus(ok=False, message="Provide video_ids")
        return HealthStatus(ok=True)
