from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from typing import Any


class HttpClient:
    def __init__(self, timeout: int = 20, retry: int = 2, backoff: float = 1.5) -> None:
        self.timeout = timeout
        self.retry = retry
        self.backoff = backoff

    def get(self, url: str, headers: dict[str, str] | None = None, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if params:
            query = urllib.parse.urlencode(params)
            url = f"{url}?{query}"
        return self._request(url, headers=headers)

    def _request(self, url: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
        attempt = 0
        headers = headers or {}
        while True:
            attempt += 1
            req = urllib.request.Request(url, headers=headers, method="GET")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    payload = response.read().decode("utf-8")
                    return json.loads(payload)
            except Exception:
                if attempt > self.retry:
                    raise
                time.sleep(self.backoff ** attempt)
