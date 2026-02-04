from __future__ import annotations

from typing import Any

from .base import Agent, AgentResult


class Orchestrator(Agent):
    agent_id = "ORCHESTRATOR"

    def run(self, context: dict[str, Any]) -> AgentResult:
        niche = context.get("niche", "Unknown")
        sub_verticals = context.get("sub_verticals", [])
        keywords = [niche] + sub_verticals
        tangential = [f"{niche} spreadsheet", f"{niche} manual process", f"{niche} integration"]
        payload = {
            "search_plan": {
                "keywords": keywords,
                "tangential_keywords": tangential,
                "platforms": ["reddit", "g2", "capterra", "indeed", "upwork", "linkedin"],
            },
            "founder_fit_constraints": context.get("constraints", {}),
        }
        return AgentResult(agent_id=self.agent_id, payload=payload)
