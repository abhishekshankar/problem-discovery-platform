from __future__ import annotations

import random
from typing import Any

from .base import Agent, AgentResult


class AgentH(Agent):
    agent_id = "H"

    def __init__(self, seed: int) -> None:
        self.seed = seed

    def run(self, context: dict[str, Any]) -> AgentResult:
        rng = random.Random(f"{self.seed}:{self.agent_id}")
        accessibility = rng.randint(4, 9)
        network_score = rng.randint(3, 8)
        payload = {
            "accessibility_score": accessibility,
            "network_effect_score": network_score,
            "watering_holes": ["LinkedIn groups", "Industry forums", "Slack communities"],
        }
        return AgentResult(agent_id=self.agent_id, payload=payload)
