"""CMS — newsroom RSS (PRD §7.1)."""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Iterator

import feedparser
import requests

from .protocol import Collector, RawRecord


class CMSNewsCollector(Collector):
    source_name = "cms"
    tier = 1
    version = "0.1.0"
    cadence_cron = "0 11 * * *"

    def __init__(self, *, rss_url: str | None = None, max_items: int = 80) -> None:
        self.rss_url = rss_url or "https://www.cms.gov/newsroom/rss-releases.rss"
        self._fallback = "https://www.cms.gov/newsroom/rss"
        self.max_items = max_items

    def fetch(self, since: datetime | None, run_id: str) -> Iterator[RawRecord]:
        for url in (self.rss_url, self._fallback):
            try:
                r = requests.get(
                    url,
                    timeout=60,
                    headers={"User-Agent": "signal-problem-discovery/0.1"},
                )
                if r.status_code != 200:
                    continue
                feed = feedparser.parse(r.content)
                if not feed.entries:
                    continue
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
                    text = f"{title}\n{summary}".strip()
                    payload = {
                        "platform": "cms",
                        "id": oid,
                        "title": title,
                        "text": text,
                        "link": link,
                    }
                    yield RawRecord(
                        external_id=f"cms:{oid}",
                        source_timestamp=ts,
                        url=link or None,
                        raw_payload=payload,
                    )
                return
            except Exception:
                continue
        raise RuntimeError("CMS RSS fetch failed for all URLs")
