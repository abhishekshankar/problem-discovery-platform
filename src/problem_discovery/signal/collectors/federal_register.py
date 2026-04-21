"""Federal Register — RSS feed (PRD §7.1)."""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Iterator

import feedparser
import requests

from .protocol import Collector, RawRecord


class FederalRegisterCollector(Collector):
    source_name = "federal_register"
    tier = 1
    version = "0.1.0"
    cadence_cron = "0 8 * * *"

    def __init__(self, *, rss_url: str | None = None, max_items: int = 100) -> None:
        self.rss_url = rss_url or "https://www.federalregister.gov/documents/search.rss"
        self.max_items = max_items

    def fetch(self, since: datetime | None, run_id: str) -> Iterator[RawRecord]:
        r = requests.get(self.rss_url, timeout=60, headers={"User-Agent": "signal-problem-discovery/0.1"})
        r.raise_for_status()
        feed = feedparser.parse(r.content)
        for i, entry in enumerate(feed.entries or []):
            if i >= self.max_items:
                break
            link = str(entry.get("link", "") or "")
            title = str(entry.get("title", "") or "")
            summary = str(entry.get("summary", "") or entry.get("description", "") or "")
            ts: datetime | None = None
            if entry.get("published_parsed"):
                try:
                    ts = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                except Exception:
                    ts = None
            if ts is None and entry.get("published"):
                try:
                    ts = parsedate_to_datetime(entry.published)
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                except Exception:
                    ts = None
            if since and ts and ts < since:
                continue
            oid = link.split("/")[-1] or str(abs(hash(link)))
            text = f"{title}\n{summary}".strip()
            payload = {
                "platform": "federal_register",
                "id": oid,
                "title": title,
                "text": text,
                "link": link,
                "published": ts.isoformat() if ts else None,
            }
            yield RawRecord(
                external_id=f"fedreg:{oid}",
                source_timestamp=ts,
                url=link or None,
                raw_payload=payload,
            )
