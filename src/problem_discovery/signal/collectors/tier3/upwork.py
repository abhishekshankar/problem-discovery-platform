"""Upwork search via Apify actor."""

from __future__ import annotations

from typing import Any

from .apify_base import ApifyActorCollector


class UpworkCollector(ApifyActorCollector):
    def __init__(self, *, search_url: str, token: str | None = None, actor_id: str | None = None) -> None:
        aid = actor_id or "apify/web-scraper"
        inp: dict[str, Any] = {"startUrls": [{"url": search_url}]}
        super().__init__(actor_id=aid, run_input=inp, token=token, source_label="upwork_apify")
