"""SEC EDGAR company submissions — Tier 1 (honors User-Agent policy)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Iterator

import requests

from .protocol import Collector, HealthStatus, RawRecord


class SECFilingsCollector(Collector):
    source_name = "sec_edgar_filings"
    tier = 1
    version = "0.1.0"
    cadence_cron = "0 10 * * *"

    def __init__(self, *, ciks: list[str], user_agent: str) -> None:
        self.ciks = [c.strip().lstrip("0") or c for c in ciks]
        self.user_agent = user_agent

    def fetch(self, since: datetime | None, run_id: str) -> Iterator[RawRecord]:
        headers = {"User-Agent": self.user_agent, "Accept-Encoding": "gzip, deflate"}
        for cik in self.ciks:
            cik_padded = str(cik).zfill(10)
            url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
            r = requests.get(url, headers=headers, timeout=60)
            if r.status_code != 200:
                continue
            try:
                data = r.json()
            except json.JSONDecodeError:
                continue
            name = str(data.get("name") or f"CIK{cik}")
            recent = data.get("filings", {}).get("recent") or {}
            forms = recent.get("form") or []
            dates = recent.get("filingDate") or []
            accs = recent.get("accessionNumber") or []
            for i, form in enumerate(forms[:40]):
                if i >= len(dates) or i >= len(accs):
                    break
                fd = str(dates[i])
                acc = str(accs[i]).replace("-", "")
                try:
                    fdt = datetime.strptime(fd, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                except ValueError:
                    fdt = datetime.now(timezone.utc)
                if since and fdt < since:
                    continue
                ext = f"{cik}_{accs[i]}"
                yield RawRecord(
                    external_id=ext[:180],
                    source_timestamp=fdt,
                    url=f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/{accs[i]}-index.htm",
                    raw_payload={
                        "platform": "sec_edgar",
                        "cik": cik,
                        "company": name,
                        "form": str(form),
                        "filing_date": fd,
                        "accession": str(accs[i]),
                    },
                    metadata={"run_id": run_id},
                )

    def healthcheck(self) -> HealthStatus:
        if not self.ciks:
            return HealthStatus(ok=False, message="Provide SEC CIKs")
        if "example.com" in self.user_agent or len(self.user_agent) < 10:
            return HealthStatus(ok=False, message="Set SEC_EDGAR_USER_AGENT per SEC policy")
        return HealthStatus(ok=True)
