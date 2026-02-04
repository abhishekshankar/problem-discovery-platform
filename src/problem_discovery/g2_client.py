from __future__ import annotations

from typing import Any

from .http_client import HttpClient


class G2Client:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        auth_scheme: str = "token",
        mode: str = "syndication",
        timeout: int = 20,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.auth_scheme = auth_scheme.lower()
        self.mode = mode
        self.http = HttpClient(timeout=timeout)

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/vnd.api+json",
        }
        if self.auth_scheme == "bearer":
            headers["Authorization"] = f"Bearer {self.api_key}"
        elif self.auth_scheme == "token":
            headers["Authorization"] = f"Token token={self.api_key}"
        return headers

    def list_reviews(self, product_id: str, page_size: int = 25, page_number: int = 1) -> dict[str, Any]:
        if self.mode == "syndication":
            url = f"{self.base_url}/api/2018-01-01/syndication/reviews"
            params = {
                "filter[product_id]": product_id,
                "page[size]": page_size,
                "page[number]": page_number,
            }
            if self.auth_scheme == "query":
                params["api_token"] = self.api_key
                return self.http.get(url, params=params)
            return self.http.get(url, headers=self._headers(), params=params)

        # Default: data API survey responses
        base = self.base_url
        if not base.endswith("/api/v1"):
            base = f"{base}/api/v1"
        url = f"{base}/products/{product_id}/survey-responses"
        params = {
            "page[size]": page_size,
            "page[number]": page_number,
        }
        if self.auth_scheme == "query":
            params["api_token"] = self.api_key
            return self.http.get(url, params=params)
        return self.http.get(url, headers=self._headers(), params=params)
