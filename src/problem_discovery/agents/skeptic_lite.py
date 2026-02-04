from __future__ import annotations

from typing import Any

from .base import Agent, AgentResult


class AgentELite(Agent):
    agent_id = "E_LITE"

    def run(self, context: dict[str, Any]) -> AgentResult:
        clusters = context.get("clusters", [])
        founder_profile = context.get("founder_profile", {})
        filtered = []
        rejects = []
        for cluster in clusters:
            name = cluster.get("cluster_name", "")
            if "enterprise" in name.lower() and founder_profile.get("sales_capability") == "low":
                rejects.append({"cluster_id": cluster.get("cluster_id"), "reason": "Founder fit mismatch"})
                continue
            filtered.append(cluster)
        return AgentResult(agent_id=self.agent_id, payload={"clusters": filtered, "rejects": rejects})
