from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

NODE_LABELS = [
    "GTMStrategy",
    "ICPProfile",
    "Channel",
    "Tactic",
    "FailurePattern",
    "Metric",
    "BuyerSignal",
    "CompetitorEdge",
    "FounderLearning",
]

EDGE_TYPES = [
    "RESPONDS_TO",
    "TRIGGERED_BY",
    "USES",
    "TARGETS",
    "LEADS_TO",
    "CAUSED_BY",
    "LED_TO_PIVOT",
    "PART_OF",
    "INFORMS",
    "REVEALS",
]


@dataclass
class Node:
    id: str
    label: str
    properties: dict[str, Any] = field(default_factory=dict)

    def sanitize(self) -> None:
        if self.label not in NODE_LABELS:
            raise ValueError(f"Unsupported node label {self.label}")


@dataclass
class Edge:
    source: str
    target: str
    relationship: str
    properties: dict[str, Any] = field(default_factory=dict)

    def sanitize(self) -> None:
        if self.relationship not in EDGE_TYPES:
            raise ValueError(f"Unsupported relationship {self.relationship}")
