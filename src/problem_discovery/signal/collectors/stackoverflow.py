"""Stack Overflow — Stack Exchange API (PRD §7.1 Tier 1)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterator

import requests

from .protocol import Collector, RawRecord


class StackOverflowCollector(Collector):
    source_name = "stackoverflow"
    tier = 1
    version = "0.1.0"
    cadence_cron = "0 */4 * * *"

    def __init__(self, *, tagged: str = "python;postgresql", pagesize: int = 30) -> None:
        self.tagged = tagged
        self.pagesize = pagesize

    def fetch(self, since: datetime | None, run_id: str) -> Iterator[RawRecord]:
        url = "https://api.stackexchange.com/2.3/questions"
        params: dict[str, str | int] = {
            "order": "desc",
            "sort": "activity",
            "tagged": self.tagged,
            "site": "stackoverflow",
            "pagesize": self.pagesize,
            "filter": "default",
        }
        r = requests.get(url, params=params, timeout=60, headers={"User-Agent": "signal-problem-discovery/0.1"})
        r.raise_for_status()
        data = r.json()
        for item in data.get("items") or []:
            qid = int(item.get("question_id") or 0)
            title = str(item.get("title") or "")
            link = str(item.get("link") or "")
            ts: datetime | None = None
            if item.get("creation_date"):
                ts = datetime.fromtimestamp(int(item["creation_date"]), tz=timezone.utc)
            if since and ts and ts < since:
                continue
            payload = {
                "platform": "stackoverflow",
                "id": qid,
                "title": title,
                "link": link,
                "score": item.get("score"),
            }
            yield RawRecord(
                external_id=str(qid),
                source_timestamp=ts,
                url=link or None,
                raw_payload=payload,
                metadata={"run_id": run_id},
            )
