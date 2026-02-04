from __future__ import annotations

import random
from typing import Any

from .base import Agent, AgentResult


class AgentG(Agent):
    agent_id = "G"

    def __init__(self, seed: int) -> None:
        self.seed = seed

    def run(self, context: dict[str, Any]) -> AgentResult:
        rng = random.Random(f"{self.seed}:{self.agent_id}")
        competitor_count = rng.randint(2, 12)
        entrenchment = rng.randint(3, 8)
        payload = {
            "competitor_count": competitor_count,
            "entrenchment_score": entrenchment,
            "assessment": "gap exists" if competitor_count <= 5 else "crowded",
        }
        return AgentResult(agent_id=self.agent_id, payload=payload)
