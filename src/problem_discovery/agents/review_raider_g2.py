from __future__ import annotations

from typing import Any

from .base import Agent, AgentResult
from .utils import stable_uuid, utc_now
from ..g2_client import G2Client


class AgentBG2(Agent):
    agent_id = "B"
    platform = "g2"

    def __init__(self, client: G2Client, seed: int) -> None:
        self.client = client
        self.seed = seed

    def _extract_reviews(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        data = payload.get("data")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return [data]
        return []

    def run(self, context: dict[str, Any]) -> AgentResult:
        product_ids = context.get("g2_product_ids", [])
        max_signals = int(context.get("max_signals", 20))
        signals: list[dict[str, Any]] = []

        for product_id in product_ids:
            page = 1
            while len(signals) < max_signals:
                payload = self.client.list_reviews(product_id, page_size=25, page_number=page)
                reviews = self._extract_reviews(payload)
                if not reviews:
                    break
                for review in reviews:
                    attributes = review.get("attributes", {})
                    review_id = review.get("id") or stable_uuid(self.seed, f"g2:{product_id}:{page}:{len(signals)}")
                    title = attributes.get("review_title") or attributes.get("title") or "G2 review"
                    body = attributes.get("review") or attributes.get("review_text") or ""
                    signals.append(
                        {
                            "signal_id": str(review_id),
                            "source_agent": self.agent_id,
                            "source_platform": self.platform,
                            "source_url": attributes.get("review_url", ""),
                            "timestamp_found": attributes.get("submitted_at") or utc_now(),
                            "content": {
                                "title": title,
                                "body": body,
                                "author": attributes.get("reviewer") or attributes.get("reviewer_name", ""),
                                "engagement": {
                                    "upvotes": attributes.get("upvotes", 0),
                                    "comments": 0,
                                },
                            },
                            "extracted_data": {
                                "pain_point": attributes.get("cons") or attributes.get("review") or title,
                                "verbatim_quote": attributes.get("cons") or "",
                                "emotion_score": 6,
                                "signal_type": "review",
                                "inferred_wtp": "medium",
                            },
                            "metadata": {
                                "post_date": attributes.get("submitted_at", ""),
                                "subreddit": None,
                                "flair": None,
                            },
                        }
                    )
                    if len(signals) >= max_signals:
                        break
                page += 1

        return AgentResult(agent_id=self.agent_id, payload={"signals": signals})
