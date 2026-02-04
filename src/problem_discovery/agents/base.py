from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class AgentResult:
    agent_id: str
    payload: dict[str, Any]


class Agent:
    agent_id = "base"

    def run(self, context: dict[str, Any]) -> AgentResult:
        raise NotImplementedError


class StaticAgent(Agent):
    """Simple agent that returns a precomputed payload (useful for mocks)."""

    def __init__(self, agent_id: str, payload: dict[str, Any]) -> None:
        self.agent_id = agent_id
        self._payload = payload

    def run(self, context: dict[str, Any]) -> AgentResult:
        return AgentResult(agent_id=self.agent_id, payload=self._payload)
