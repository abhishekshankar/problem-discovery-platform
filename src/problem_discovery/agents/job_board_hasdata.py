from __future__ import annotations

from typing import Any

from .base import Agent, AgentResult
from .utils import stable_uuid, utc_now
from ..hasdata_client import HasDataClient


class AgentCHasData(Agent):
    agent_id = "C"
    platform = "indeed"

    def __init__(
        self,
        client: HasDataClient,
        seed: int,
        location: str,
        country: str = "us",
        domain: str = "www.indeed.com",
        sort: str = "date",
    ) -> None:
        self.client = client
        self.seed = seed
        self.location = location
        self.country = country
        self.domain = domain
        self.sort = sort

    def _extract_jobs(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        for key in ("data", "results", "jobs", "listings", "items"):
            if isinstance(payload.get(key), list):
                return payload[key]
        return []

    def run(self, context: dict[str, Any]) -> AgentResult:
        query = context.get("niche", "")
        max_signals = int(context.get("max_signals", 20))
        signals: list[dict[str, Any]] = []
        page = 1

        while len(signals) < max_signals and page <= 3:
            payload = self.client.list_indeed_jobs(
                query,
                self.location,
                page=page,
                country=self.country,
                domain=self.domain,
                sort=self.sort,
            )
            jobs = self._extract_jobs(payload)
            if not jobs:
                break
            for job in jobs:
                title = job.get("title") or job.get("job_title") or ""
                company = job.get("company") or job.get("company_name") or ""
                summary = job.get("summary") or job.get("description") or ""
                url = job.get("url") or job.get("job_url") or ""
                job_id = job.get("id") or job.get("job_id") or stable_uuid(self.seed, f"indeed:{page}:{len(signals)}")
                signals.append(
                    {
                        "signal_id": str(job_id),
                        "source_agent": self.agent_id,
                        "source_platform": self.platform,
                        "source_url": url,
                        "timestamp_found": utc_now(),
                        "content": {
                            "title": f"{title} @ {company}".strip(),
                            "body": summary,
                            "author": company,
                            "engagement": {"upvotes": 0, "comments": 0},
                        },
                        "extracted_data": {
                            "pain_point": f"Hiring for {title}".strip(),
                            "verbatim_quote": summary[:200],
                            "emotion_score": 5,
                            "signal_type": "job_posting",
                            "inferred_wtp": "medium",
                        },
                        "metadata": {
                            "post_date": job.get("date") or job.get("posted_at") or "",
                            "subreddit": None,
                            "flair": None,
                        },
                    }
                )
                if len(signals) >= max_signals:
                    break
            page += 1

        return AgentResult(agent_id=self.agent_id, payload={"signals": signals})
