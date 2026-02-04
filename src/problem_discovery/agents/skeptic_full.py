from __future__ import annotations

import random
from typing import Any

from .base import Agent, AgentResult


class AgentEFull(Agent):
    agent_id = "E_FULL"

    def __init__(self, seed: int) -> None:
        self.seed = seed

    def run(self, context: dict[str, Any]) -> AgentResult:
        rng = random.Random(f"{self.seed}:{self.agent_id}")
        kill_reasons = [
            "Switching cost too high",
            "Incumbent can copy quickly",
            "Buyer inertia is strong",
            "Budget is tied to existing vendor",
        ]
        chosen = rng.sample(kill_reasons, k=min(2, len(kill_reasons)))
        payload = {
            "kill_reasons": chosen,
            "survival_verdict": rng.choice(["PROCEED", "PROCEED_WITH_CAUTION", "REJECT"]),
        }
        return AgentResult(agent_id=self.agent_id, payload=payload)
