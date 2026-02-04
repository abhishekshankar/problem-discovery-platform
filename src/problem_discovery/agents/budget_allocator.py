from __future__ import annotations

import random
from typing import Any

from .base import Agent, AgentResult


class AgentL(Agent):
    agent_id = "L"

    def __init__(self, seed: int) -> None:
        self.seed = seed

    def run(self, context: dict[str, Any]) -> AgentResult:
        rng = random.Random(f"{self.seed}:{self.agent_id}")
        signals = context.get("signals", [])
        base = 30000 + 1000 * min(len(signals), 40)
        mid = int(base * rng.uniform(1.2, 1.7))
        high = int(mid * rng.uniform(1.3, 1.6))
        payload = {
            "budget_analysis": {
                "source_type": rng.choice([
                    "replaces_headcount",
                    "overtime_reduction",
                    "compliance_risk",
                ]),
                "estimated_range": {"low": base, "mid": mid, "high": high},
                "budget_holder": rng.choice(["Operations", "Controller", "Product", "Finance"]),
            }
        }
        return AgentResult(agent_id=self.agent_id, payload=payload)
