from __future__ import annotations

from typing import Any

from .http_client import HttpClient


class HasDataClient:
    def __init__(self, api_key: str, base_url: str, timeout: int = 20) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.http = HttpClient(timeout=timeout)

    def list_indeed_jobs(
        self,
        query: str,
        location: str,
        page: int = 1,
        country: str = "us",
        domain: str = "www.indeed.com",
        sort: str = "date",
    ) -> dict[str, Any]:
        url = f"{self.base_url}/scrape/indeed/listing"
        params = {
            "keyword": query,
            "location": location,
            "page": page,
            "country": country,
            "domain": domain,
            "sort": sort,
        }
        headers = {"x-api-key": self.api_key}
        return self.http.get(url, headers=headers, params=params)
