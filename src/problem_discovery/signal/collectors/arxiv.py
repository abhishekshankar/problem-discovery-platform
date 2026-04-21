"""arXiv API — PRD §7.1 Tier 1."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterator
from urllib.parse import quote

import feedparser
import requests

from .protocol import Collector, RawRecord


class ArxivCollector(Collector):
    source_name = "arxiv"
    tier = 1
    version = "0.1.0"
    cadence_cron = "0 */6 * * *"

    def __init__(self, *, query: str = "all:health+OR+all:clinical", max_items: int = 40) -> None:
        self.query = query
        self.max_items = max_items

    def fetch(self, since: datetime | None, run_id: str) -> Iterator[RawRecord]:
        q = quote(self.query, safe=":+")
        url = f"http://export.arxiv.org/api/query?search_query={q}&start=0&max_results={self.max_items}&sortBy=submittedDate"
        r = requests.get(url, timeout=90, headers={"User-Agent": "signal-problem-discovery/0.1"})
        r.raise_for_status()
        feed = feedparser.parse(r.content)
        for i, entry in enumerate(feed.entries or []):
            if i >= self.max_items:
                break
            aid = str(entry.get("id", "") or entry.get("link", "") or "")
            title = str(entry.get("title", "") or "").replace("\n", " ")
            summary = str(entry.get("summary", "") or "").replace("\n", " ")
            ts: datetime | None = None
            if entry.get("published"):
                try:
                    from email.utils import parsedate_to_datetime

                    ts = parsedate_to_datetime(entry.published)
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                except Exception:
                    ts = None
            if since and ts and ts < since:
                continue
            oid = aid.split("/abs/")[-1].replace("/", "_") or str(abs(hash(aid)))
            payload = {"platform": "arxiv", "id": oid, "title": title, "summary": summary, "link": entry.get("link")}
            yield RawRecord(
                external_id=oid[:180],
                source_timestamp=ts,
                url=str(entry.get("link") or "") or None,
                raw_payload=payload,
                metadata={"run_id": run_id},
            )
