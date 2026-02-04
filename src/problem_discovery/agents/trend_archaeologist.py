from __future__ import annotations

import random
from typing import Any

from .base import Agent, AgentResult


class AgentF(Agent):
    agent_id = "F"

    def __init__(self, seed: int) -> None:
        self.seed = seed

    def run(self, context: dict[str, Any]) -> AgentResult:
        rng = random.Random(f"{self.seed}:{self.agent_id}")
        trend_score = rng.randint(4, 9)
        payload = {
            "trend_score": trend_score,
            "assessment": "rising" if trend_score >= 7 else "stable",
            "catalyst_events": ["New API availability", "Regulatory change"],
        }
        return AgentResult(agent_id=self.agent_id, payload=payload)
