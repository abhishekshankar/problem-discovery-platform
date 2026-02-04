from __future__ import annotations

import random
from typing import Any

from .base import Agent, AgentResult
from .utils import stable_uuid, utc_now


class SignalMiner(Agent):
    agent_id = "signal_miner"
    platform = "unknown"

    def __init__(self, seed: int) -> None:
        self.seed = seed

    def _generate_signal(self, idx: int, context: dict[str, Any]) -> dict[str, Any]:
        niche = context.get("niche", "Unknown")
        rng = random.Random(f"{self.seed}:{self.agent_id}:{idx}")
        pain_points = context.get("seed_pains") or [
            f"manual {niche} data entry",
            f"reporting delays in {niche}",
            f"integration gaps for {niche}",
            f"compliance tracking in {niche}",
        ]
        signal_type = rng.choice(["workaround", "complaint", "data_entry_task", "budget_line_item"])
        pain_point = rng.choice(pain_points)
        signal_id = stable_uuid(self.seed, f"{self.agent_id}:{idx}")

        return {
            "signal_id": signal_id,
            "source_agent": self.agent_id,
            "source_platform": self.platform,
            "source_url": f"https://example.com/{self.platform}/{signal_id}",
            "timestamp_found": utc_now(),
            "content": {
                "title": f"{niche} pain point #{idx + 1}",
                "body": f"Users mention {pain_point} and need a better workflow.",
                "author": f"user_{rng.randint(100, 999)}",
                "engagement": {"upvotes": rng.randint(1, 200), "comments": rng.randint(0, 40)},
            },
            "extracted_data": {
                "pain_point": pain_point,
                "verbatim_quote": f"We are stuck with {pain_point}.",
                "emotion_score": rng.randint(4, 9),
                "signal_type": signal_type,
                "inferred_wtp": rng.choice(["low", "medium", "medium-high", "high"]),
            },
            "metadata": {
                "post_date": "2025-12-15",
                "subreddit": "r/operations" if self.platform == "reddit" else None,
                "flair": "Advice" if self.platform == "reddit" else None,
            },
        }

    def run(self, context: dict[str, Any]) -> AgentResult:
        max_signals = int(context.get("max_signals", 20))
        signals = [self._generate_signal(i, context) for i in range(max_signals)]
        return AgentResult(agent_id=self.agent_id, payload={"signals": signals})
