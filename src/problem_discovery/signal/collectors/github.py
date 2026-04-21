"""GitHub — issue search API (PRD §7.1)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterator

import requests

from .protocol import Collector, RawRecord


class GitHubIssuesCollector(Collector):
    source_name = "github"
    tier = 1
    version = "0.1.0"
    cadence_cron = "0 9 * * *"

    def __init__(
        self,
        *,
        query: str = "is:issue is:open",
        token: str | None = None,
        per_page: int = 50,
    ) -> None:
        self.query = query
        self.token = token
        self.per_page = per_page

    def fetch(self, since: datetime | None, run_id: str) -> Iterator[RawRecord]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "signal-problem-discovery/0.1",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        params = {"q": self.query, "per_page": self.per_page, "sort": "updated", "order": "desc"}
        r = requests.get(
            "https://api.github.com/search/issues",
            headers=headers,
            params=params,
            timeout=60,
        )
        if r.status_code == 403:
            raise RuntimeError("GitHub API rate limit or forbidden — set GITHUB_TOKEN")
        r.raise_for_status()
        data = r.json()
        for item in data.get("items", []) or []:
            num = item.get("number")
            repo = item.get("repository") or {}
            repo_full = str(repo.get("full_name") or "unknown/unknown")
            oid = f"{repo_full}#{num}"
            title = str(item.get("title", "") or "")
            body = str(item.get("body", "") or "")
            created = item.get("created_at")
            ts: datetime | None = None
            if created:
                try:
                    ts = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
                except Exception:
                    ts = None
            if since and ts and ts < since:
                continue
            text = f"{title}\n{body}".strip()
            url = str(item.get("html_url", "") or "")
            payload = {
                "platform": "github",
                "repo": repo_full,
                "number": num,
                "title": title,
                "text": text,
                "url": url,
                "created_at": created,
            }
            yield RawRecord(
                external_id=f"github:{repo_full}:{num}",
                source_timestamp=ts,
                url=url or None,
                raw_payload=payload,
            )
