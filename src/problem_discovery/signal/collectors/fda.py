"""FDA news releases RSS — PRD §7.1 Tier 1."""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Iterator

import feedparser
import requests

from .protocol import Collector, RawRecord


class FDANewsCollector(Collector):
    source_name = "fda_news"
    tier = 1
    version = "0.1.0"
    cadence_cron = "0 10 * * *"

    def __init__(
        self,
        *,
        rss_url: str | None = None,
        max_items: int = 60,
    ) -> None:
        self.rss_url = rss_url or "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/fda-news-releases.xml"
        self.max_items = max_items

    def fetch(self, since: datetime | None, run_id: str) -> Iterator[RawRecord]:
        r = requests.get(
            self.rss_url,
            timeout=60,
            headers={"User-Agent": "signal-problem-discovery/0.1"},
        )
        r.raise_for_status()
        feed = feedparser.parse(r.content)
        for i, entry in enumerate(feed.entries or []):
            if i >= self.max_items:
                break
            link = str(entry.get("link", "") or "")
            title = str(entry.get("title", "") or "")
            summary = str(entry.get("summary", "") or "")
            ts: datetime | None = None
            if entry.get("published"):
                try:
                    ts = parsedate_to_datetime(entry.published)
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                except Exception:
                    ts = None
            if since and ts and ts < since:
                continue
            oid = link.split("/")[-1] or str(abs(hash(link)))
            yield RawRecord(
                external_id=oid[:180],
                source_timestamp=ts,
                url=link or None,
                raw_payload={
                    "platform": "fda",
                    "id": oid,
                    "title": title,
                    "summary": summary,
                },
                metadata={"run_id": run_id},
            )
