from __future__ import annotations

from collections import defaultdict
from typing import Any

from .base import Agent, AgentResult
from .utils import stable_uuid, utc_now


class AgentD(Agent):
    agent_id = "D"

    def __init__(self, seed: int) -> None:
        self.seed = seed

    def run(self, context: dict[str, Any]) -> AgentResult:
        signals = context.get("signals", [])
        buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for signal in signals:
            pain = signal.get("extracted_data", {}).get("pain_point", "")
            key = pain.split(" ")[0].lower() if pain else "misc"
            buckets[key].append(signal)

        clusters = []
        for idx, (key, bucket) in enumerate(buckets.items()):
            cluster_id = stable_uuid(self.seed, f"cluster:{key}:{idx}")
            clusters.append({
                "cluster_id": cluster_id,
                "cluster_name": f"{key.title()} Workflow Pain",
                "description": f"Signals about {key} related workflows.",
                "created_at": utc_now(),
                "signals": bucket,
            })

        return AgentResult(agent_id=self.agent_id, payload={"clusters": clusters})
