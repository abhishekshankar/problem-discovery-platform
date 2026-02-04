from __future__ import annotations

import random
from typing import Any

from .base import Agent, AgentResult


class AgentJ(Agent):
    agent_id = "J"

    def __init__(self, seed: int) -> None:
        self.seed = seed

    def run(self, context: dict[str, Any]) -> AgentResult:
        rng = random.Random(f"{self.seed}:{self.agent_id}")
        score = rng.randint(3, 9)
        payload = {
            "contrarian_score": score,
            "assessment": "positive" if score >= 6 else "neutral",
            "notes": ["Previous attempts failed due to timing"],
        }
        return AgentResult(agent_id=self.agent_id, payload=payload)
