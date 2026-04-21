from __future__ import annotations

import json
import logging
from typing import Any, Iterable

from openai import OpenAI
from openai.error import OpenAIError

from .schema import Edge, Node

LOGGER = logging.getLogger(__name__)

GTM_EXTRACTION_PROMPT = """
You are a GTM knowledge graph extractor. Given Reddit post text about
go-to-market strategy, extract structured entities and relationships.

Return valid JSON matching this schema EXACTLY:
{
  "nodes": [
    {"id": "unique_slug", "label": "NodeLabel", "properties": {}}
  ],
  "edges": [
    {"source": "node_id", "target": "node_id", "relationship": "EDGE_TYPE",\
     "properties": {"confidence": 0.0-1.0, "evidence": "quote from text"}}
  ]
}

Valid node labels: GTMStrategy, ICPProfile, Channel, Tactic, FailurePattern,
                   Metric, BuyerSignal, CompetitorEdge, FounderLearning

Valid edge types: RESPONDS_TO, TRIGGERED_BY, USES, TARGETS, LEADS_TO,
                  CAUSED_BY, LED_TO_PIVOT, PART_OF, INFORMS, REVEALS

Context metadata:
- Subreddit: {subreddit}
- Layer: {layer}
- Post score: {score} (higher = more validated by community)
- Post date: {date}

Text to extract from:
{text}

Rules:
- Only extract what's explicitly stated, not inferred
- Include 'evidence' quote for each edge (used for GraphRAG retrieval)
- Assign confidence based on specificity (vague=0.3, specific=0.8, cited=1.0)
- For ICP nodes, extract EXACT language patterns used (these are gold)
"""


class LLMExtractor:
    def __init__(
        self,
        model: str = "gpt-4o",
        temperature: float = 0.1,
        dry_run: bool = False,
        client: OpenAI | None = None,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.client = client or OpenAI()
        self.dry_run = dry_run

    def extract(self, text: str, metadata: dict[str, Any]) -> tuple[list[Node], list[Edge]]:
        if self.dry_run:
            LOGGER.warning("Dry run enabled: skipping OpenAI call")
            return [], []

        context = {
            "subreddit": metadata.get("subreddit", "unknown"),
            "layer": metadata.get("layer", "unknown"),
            "score": metadata.get("score", 0),
            "date": metadata.get("date", ""),
            "text": text,
        }
        prompt = GTM_EXTRACTION_PROMPT.format(**context)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                response_format={"type": "json_object"},
            )
        except OpenAIError as err:
            LOGGER.error("LLM extraction failed: %s", err)
            return [], []

        content = response.choices[0].message.content
        payload = json.loads(content)
        nodes = self._build_nodes(payload.get("nodes", []))
        edges = self._build_edges(payload.get("edges", []))
        return nodes, edges

    def _build_nodes(self, entries: Iterable[dict[str, Any]]) -> list[Node]:
        nodes: list[Node] = []
        for entry in entries:
            node_id = entry.get("id")
            label = entry.get("label")
            if not node_id or not label:
                continue
            properties = entry.get("properties", {}) or {}
            nodes.append(Node(id=node_id, label=label, properties=properties))
        return nodes

    def _build_edges(self, entries: Iterable[dict[str, Any]]) -> list[Edge]:
        edges: list[Edge] = []
        for entry in entries:
            source = entry.get("source")
            target = entry.get("target")
            relationship = entry.get("relationship")
            if not source or not target or not relationship:
                continue
            properties = entry.get("properties", {}) or {}
            edges.append(Edge(source=source, target=target, relationship=relationship, properties=properties))
        return edges
