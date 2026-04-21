"""G2 reviews via Apify actor (configurable)."""

from __future__ import annotations

from typing import Any

from .apify_base import ApifyActorCollector


class G2Collector(ApifyActorCollector):
    def __init__(self, *, product_url: str, token: str | None = None, actor_id: str | None = None) -> None:
        aid = actor_id or "apify/web-scraper"
        inp: dict[str, Any] = {"startUrls": [{"url": product_url}]}
        super().__init__(actor_id=aid, run_input=inp, token=token, source_label="g2_apify")
