"""NIH RePORTER API — PRD §7.1 Tier 1."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterator

import requests

from .protocol import Collector, RawRecord


class NIHReporterCollector(Collector):
    source_name = "nih_reporter"
    tier = 1
    version = "0.1.0"
    cadence_cron = "0 9 * * 1"

    def __init__(self, *, text_criteria: str = "cancer therapy", page_size: int = 25) -> None:
        self.text_criteria = text_criteria
        self.page_size = page_size

    def fetch(self, since: datetime | None, run_id: str) -> Iterator[RawRecord]:
        url = "https://api.reporter.nih.gov/v2/projects/search"
        body: dict[str, Any] = {
            "criteria": {"text": self.text_criteria},
            "include_fields": ["ProjectTitle", "AbstractText", "ApplId", "PrefixedAwardId"],
            "offset": 0,
            "limit": self.page_size,
        }
        r = requests.post(url, json=body, timeout=90, headers={"User-Agent": "signal-problem-discovery/0.1"})
        r.raise_for_status()
        data = r.json()
        for row in data.get("results") or []:
            if not isinstance(row, dict):
                continue
            aid = str(
                row.get("appl_id")
                or row.get("project_num")
                or row.get("prefixed_award_id")
                or row.get("ApplId")
                or ""
            )
            title = str(row.get("project_title") or row.get("ProjectTitle") or "")
            abstract = str(row.get("abstract_text") or row.get("AbstractText") or "")
            ts: datetime | None = None
            if row.get("award_notice_date"):
                try:
                    ts = datetime.fromisoformat(str(row["award_notice_date"]).replace("Z", "+00:00"))
                except Exception:
                    ts = None
            if since and ts and ts < since:
                continue
            oid = aid or str(abs(hash(title)))
            yield RawRecord(
                external_id=oid[:180],
                source_timestamp=ts,
                url=None,
                raw_payload={"platform": "nih_reporter", "appl_id": aid, "title": title, "abstract": abstract[:8000]},
                metadata={"run_id": run_id},
            )
