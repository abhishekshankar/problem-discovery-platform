"""Hacker News — Algolia HN API (PRD §7.1)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterator

import requests

from .protocol import Collector, RawRecord


class HackerNewsCollector(Collector):
    source_name = "hackernews"
    tier = 1
    version = "0.1.0"
    cadence_cron = "0 */4 * * *"

    def __init__(self, *, hits_per_page: int = 100, tags: str = "story") -> None:
        self.hits_per_page = hits_per_page
        self.tags = tags

    def fetch(self, since: datetime | None, run_id: str) -> Iterator[RawRecord]:
        params: dict[str, str | int] = {"tags": self.tags, "hitsPerPage": self.hits_per_page}
        r = requests.get("https://hn.algolia.com/api/v1/search", params=params, timeout=60)
        r.raise_for_status()
        data = r.json()
        for hit in data.get("hits", []) or []:
            created = int(hit.get("created_at_i") or 0)
            if not created:
                continue
            ts = datetime.fromtimestamp(created, tz=timezone.utc)
            if since and ts < since:
                continue
            oid = str(hit.get("objectID") or hit.get("story_id") or "")
            if not oid:
                continue
            title = str(hit.get("title") or "")
            url = hit.get("url") or f"https://news.ycombinator.com/item?id={oid}"
            text = title
            if hit.get("story_text"):
                text += "\n" + str(hit.get("story_text"))
            payload = {
                "platform": "hackernews",
                "id": oid,
                "created_at": ts.isoformat(),
                "title": title,
                "text": text.strip(),
                "url": url,
                "points": hit.get("points"),
                "num_comments": hit.get("num_comments"),
            }
            yield RawRecord(
                external_id=f"hn:story:{oid}",
                source_timestamp=ts,
                url=str(url) if url else None,
                raw_payload=payload,
            )
