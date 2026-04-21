"""Google Trends via pytrends (optional dependency) — PRD §7.1 Tier 1."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterator

from .protocol import Collector, HealthStatus, RawRecord


class GoogleTrendsCollector(Collector):
    source_name = "google_trends"
    tier = 1
    version = "0.1.0"
    cadence_cron = "0 12 * * *"

    def __init__(self, *, keywords: list[str] | None = None) -> None:
        self.keywords = keywords or ["telehealth", "ehr interoperability", "prior authorization"]

    def fetch(self, since: datetime | None, run_id: str) -> Iterator[RawRecord]:
        try:
            from pytrends.request import TrendReq
        except ImportError:
            return

        pyt = TrendReq(hl="en-US", tz=300)
        pyt.build_payload(self.keywords[:5], timeframe="now 7-d")
        data = pyt.interest_over_time()
        if data is None or data.empty:
            return
        now = datetime.now(timezone.utc)
        # One record per keyword with last-week interest as payload
        for kw in self.keywords[:5]:
            if kw not in data.columns:
                continue
            val = float(data[kw].iloc[-1]) if len(data[kw]) else 0.0
            yield RawRecord(
                external_id=f"{kw.replace(' ', '_')}_{data.index[-1]!s}"[:180],
                source_timestamp=now,
                url=None,
                raw_payload={
                    "platform": "google_trends",
                    "keyword": kw,
                    "interest_last_bucket": val,
                    "note": "pytrends — subject to Google rate limits; not for high-frequency scraping",
                },
                metadata={"run_id": run_id},
            )

    def healthcheck(self) -> HealthStatus:
        try:
            import pytrends  # noqa: F401
        except ImportError:
            return HealthStatus(ok=False, message="pip install pytrends")
        return HealthStatus(ok=True)
