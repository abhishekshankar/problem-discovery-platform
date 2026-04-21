"""Tier 2 paid data sources — PRD §7.2 (Ahrefs *or* Semrush, Similarweb, SparkToro)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Iterator

import requests

from .protocol import Collector, HealthStatus, RawRecord


def _run_id_meta(run_id: str) -> dict[str, str]:
    return {"run_id": run_id}


class AhrefsKeywordCollector(Collector):
    """Ahrefs Site Explorer overview — requires `AHREFS_API_KEY` (Bearer)."""

    source_name = "ahrefs_keywords"
    tier = 2
    version = "0.2.0"
    cadence_cron = "0 6 * * 1"

    def __init__(self, *, api_key: str | None = None, target: str = "wikipedia.org") -> None:
        self.api_key = api_key or os.environ.get("AHREFS_API_KEY")
        self.target = target

    def fetch(self, since: datetime | None, run_id: str) -> Iterator[RawRecord]:
        _ = since
        if not self.api_key:
            return
        r = requests.get(
            "https://api.ahrefs.com/v3/site-explorer/overview",
            params={"target": self.target, "mode": "domain", "output": "json"},
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=60,
        )
        if r.status_code != 200:
            return
        data: dict[str, Any] = r.json() if r.content else {}
        metrics = data.get("metrics") or data
        yield RawRecord(
            external_id=f"ahrefs_{self.target}"[:180],
            source_timestamp=datetime.now(timezone.utc),
            url=f"https://ahrefs.com/site-explorer/overview/v2/subdomains/live?target={self.target}",
            raw_payload={"platform": "ahrefs", "target": self.target, "overview": metrics},
            metadata=_run_id_meta(run_id),
        )

    def healthcheck(self) -> HealthStatus:
        if not self.api_key:
            return HealthStatus(ok=False, message="Set AHREFS_API_KEY")
        return HealthStatus(ok=True)


class SemrushDomainCollector(Collector):
    """Semrush Analytics API — requires `SEMRUSH_API_KEY` (PRD: use Ahrefs *or* Semrush, not both)."""

    source_name = "semrush_domain"
    tier = 2
    version = "0.2.0"
    cadence_cron = "0 6 * * 1"

    def __init__(self, *, api_key: str | None = None, domain: str = "semrush.com", database: str = "us") -> None:
        self.api_key = api_key or os.environ.get("SEMRUSH_API_KEY")
        self.domain = domain
        self.database = database

    def fetch(self, since: datetime | None, run_id: str) -> Iterator[RawRecord]:
        _ = since
        if not self.api_key:
            return
        r = requests.get(
            "https://api.semrush.com/",
            params={
                "type": "domain_ranks",
                "key": self.api_key,
                "domain": self.domain,
                "database": self.database,
                "export_columns": "Db,Dn,Rk,Or,Ot,Oc,Ad,At,Ac",
            },
            timeout=60,
            headers={"User-Agent": "signal-problem-discovery/0.1"},
        )
        if r.status_code != 200:
            return
        text = r.text.strip()
        yield RawRecord(
            external_id=f"semrush_{self.domain}"[:180],
            source_timestamp=datetime.now(timezone.utc),
            url=f"https://www.semrush.com/analytics/overview/?q={self.domain}",
            raw_payload={"platform": "semrush", "domain": self.domain, "domain_ranks_csv": text[:12000]},
            metadata=_run_id_meta(run_id),
        )

    def healthcheck(self) -> HealthStatus:
        if not self.api_key:
            return HealthStatus(ok=False, message="Set SEMRUSH_API_KEY")
        return HealthStatus(ok=True)


class SimilarwebCollector(Collector):
    """Similarweb DigitalRank API — requires `SIMILARWEB_API_KEY`."""

    source_name = "similarweb"
    tier = 2
    version = "0.2.0"
    cadence_cron = "0 7 * * 1"

    def __init__(self, *, api_key: str | None = None, domain: str = "similarweb.com") -> None:
        self.api_key = api_key or os.environ.get("SIMILARWEB_API_KEY")
        self.domain = domain

    def fetch(self, since: datetime | None, run_id: str) -> Iterator[RawRecord]:
        _ = since
        if not self.api_key:
            return
        # v1 website total traffic — path may vary by account tier; adjust per vendor docs.
        r = requests.get(
            f"https://api.similarweb.com/v1/website/total-traffic/visit",
            params={"api_key": self.api_key, "domain": self.domain},
            timeout=60,
            headers={"User-Agent": "signal-problem-discovery/0.1"},
        )
        if r.status_code != 200:
            return
        try:
            payload = r.json()
        except Exception:
            payload = {"raw": r.text[:8000]}
        yield RawRecord(
            external_id=f"similarweb_{self.domain}"[:180],
            source_timestamp=datetime.now(timezone.utc),
            url=f"https://www.similarweb.com/website/{self.domain}/",
            raw_payload={"platform": "similarweb", "domain": self.domain, "traffic": payload},
            metadata=_run_id_meta(run_id),
        )

    def healthcheck(self) -> HealthStatus:
        if not self.api_key:
            return HealthStatus(ok=False, message="Set SIMILARWEB_API_KEY")
        return HealthStatus(ok=True)


class SparkToroCollector(Collector):
    """SparkToro audience API — requires `SPARKTORO_API_KEY`."""

    source_name = "sparktoro"
    tier = 2
    version = "0.2.0"
    cadence_cron = "0 8 * * 1"

    def __init__(self, *, api_key: str | None = None, query: str = "founders") -> None:
        self.api_key = api_key or os.environ.get("SPARKTORO_API_KEY")
        self.query = query

    def fetch(self, since: datetime | None, run_id: str) -> Iterator[RawRecord]:
        _ = since
        if not self.api_key:
            return
        r = requests.get(
            "https://api.sparktoro.com/v1/search/profiles",
            params={"q": self.query},
            headers={"Authorization": f"Bearer {self.api_key}", "User-Agent": "signal-problem-discovery/0.1"},
            timeout=60,
        )
        if r.status_code != 200:
            return
        try:
            data = r.json()
        except Exception:
            data = {"raw": r.text[:8000]}
        yield RawRecord(
            external_id=f"sparktoro_{abs(hash(self.query))}"[:180],
            source_timestamp=datetime.now(timezone.utc),
            url="https://sparktoro.com/",
            raw_payload={"platform": "sparktoro", "query": self.query, "result": data},
            metadata=_run_id_meta(run_id),
        )

    def healthcheck(self) -> HealthStatus:
        if not self.api_key:
            return HealthStatus(ok=False, message="Set SPARKTORO_API_KEY")
        return HealthStatus(ok=True)


class ListenNotesCollector(Collector):
    """Listen Notes podcast search API — LISTENNOTES_API_KEY."""

    source_name = "listennotes"
    tier = 2
    version = "0.1.0"
    cadence_cron = "0 9 * * *"

    def __init__(self, *, api_key: str | None = None, q: str = "startup problems", max_results: int = 20) -> None:
        self.api_key = api_key or os.environ.get("LISTENNOTES_API_KEY")
        self.q = q
        self.max_results = min(max_results, 30)

    def fetch(self, since: datetime | None, run_id: str) -> Iterator[RawRecord]:
        _ = since
        if not self.api_key:
            return
        r = requests.get(
            "https://listen-api.listennotes.com/api/v2/search",
            params={"q": self.q, "type": "episode", "len_min": 5, "len_max": 240, "offset": 0},
            headers={"X-ListenAPI-Key": self.api_key, "User-Agent": "signal-problem-discovery/0.1"},
            timeout=60,
        )
        if r.status_code != 200:
            return
        data = r.json() if r.content else {}
        for ep in (data.get("results") or [])[: self.max_results]:
            eid = str(ep.get("id") or "")
            if not eid:
                continue
            title = str(ep.get("title_original") or ep.get("title") or "")
            desc = str(ep.get("description_original") or ep.get("description") or "")[:6000]
            pub = ep.get("pub_date_ms")
            ts = datetime.now(timezone.utc)
            if pub:
                try:
                    ts = datetime.fromtimestamp(int(pub) / 1000, tz=timezone.utc)
                except Exception:
                    pass
            yield RawRecord(
                external_id=eid[:180],
                source_timestamp=ts,
                url=str(ep.get("listennotes_url") or ep.get("link") or ""),
                raw_payload={"platform": "listennotes", "episode": ep, "title": title, "description": desc},
                metadata=_run_id_meta(run_id),
            )

    def healthcheck(self) -> HealthStatus:
        if not self.api_key:
            return HealthStatus(ok=False, message="Set LISTENNOTES_API_KEY")
        return HealthStatus(ok=True)


class ProfoundCollector(Collector):
    """Generic AI-visibility / vendor adapter — PROFOUND_API_BASE_URL + PROFOUND_API_KEY."""

    source_name = "profound"
    tier = 2
    version = "0.1.0"
    cadence_cron = "0 11 * * *"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        query_payload: dict[str, Any] | None = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("PROFOUND_API_KEY")
        self.base_url = (base_url or os.environ.get("PROFOUND_API_BASE_URL") or "").rstrip("/")
        self.query_payload = query_payload or {"query": "B2B SaaS churn visibility", "market": "US"}

    def fetch(self, since: datetime | None, run_id: str) -> Iterator[RawRecord]:
        _ = since
        if not self.api_key or not self.base_url:
            return
        url = f"{self.base_url}/v1/signal"
        if not url.startswith("http"):
            return
        r = requests.post(
            url,
            json=self.query_payload,
            headers={"Authorization": f"Bearer {self.api_key}", "User-Agent": "signal-problem-discovery/0.1"},
            timeout=60,
        )
        body: Any
        try:
            body = r.json()
        except Exception:
            body = {"raw": r.text[:12000], "status_code": r.status_code}
        ext = f"profound_{abs(hash(json.dumps(self.query_payload, sort_keys=True)))}"[:180]
        yield RawRecord(
            external_id=ext,
            source_timestamp=datetime.now(timezone.utc),
            url=self.base_url,
            raw_payload={"platform": "profound", "request": self.query_payload, "response": body},
            metadata=_run_id_meta(run_id),
        )

    def healthcheck(self) -> HealthStatus:
        if not self.api_key or not self.base_url:
            return HealthStatus(ok=False, message="Set PROFOUND_API_KEY and PROFOUND_API_BASE_URL")
        return HealthStatus(ok=True)
