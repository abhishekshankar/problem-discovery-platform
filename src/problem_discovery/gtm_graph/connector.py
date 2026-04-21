from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Iterable

from .schema import Edge, Node

_CHUNK_EXCERPT_LENGTH = 512


@dataclass(frozen=True)
class ChunkMetadata:
    subreddit: str
    layer: str
    score: float
    date: str
    query: str | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "ChunkMetadata":
        return cls(
            subreddit=str(payload.get("subreddit", "unknown")),
            layer=str(payload.get("layer", "unknown")),
            score=float(payload.get("score", 0) or 0),
            date=str(payload.get("date", "")),
            query=payload.get("query") or None,
        )


class ExtractionSchemaConnector:
    def __init__(self) -> None:
        self._nodes: OrderedDict[tuple[str, str], Node] = OrderedDict()
        self._edges: OrderedDict[tuple[str, str, str], Edge] = OrderedDict()

    def ingest_chunk(
        self,
        chunk_text: str,
        metadata: ChunkMetadata,
        nodes: Iterable[Node],
        edges: Iterable[Edge],
    ) -> None:
        for node in nodes:
            self._annotate_node(node, metadata, chunk_text)
            self._upsert_node(node)

        for edge in edges:
            self._annotate_edge(edge, metadata, chunk_text)
            self._upsert_edge(edge)

    def _upsert_node(self, node: Node) -> None:
        node_key = (node.label, node.id)
        if node_key in self._nodes:
            merged = self._merge_properties(self._nodes[node_key].properties, node.properties)
            self._nodes[node_key].properties = merged
        else:
            self._nodes[node_key] = node

    def _upsert_edge(self, edge: Edge) -> None:
        edge_key = (edge.source, edge.target, edge.relationship)
        if edge_key in self._edges:
            merged = self._merge_properties(self._edges[edge_key].properties, edge.properties)
            self._edges[edge_key].properties = merged
        else:
            self._edges[edge_key] = edge

    def _annotate_node(self, node: Node, metadata: ChunkMetadata, chunk_text: str) -> None:
        node.properties.setdefault("subreddit", metadata.subreddit)
        node.properties.setdefault("layer", metadata.layer)
        node.properties.setdefault("last_seen_at", metadata.date)
        if metadata.query:
            node.properties.setdefault("search_query", metadata.query)
        node.properties.setdefault("chunk_excerpt", chunk_text[:_CHUNK_EXCERPT_LENGTH])
        node.properties.setdefault("sample_score", metadata.score)
        node.properties.setdefault("source", metadata.subreddit)
        node.sanitize()

    def _annotate_edge(self, edge: Edge, metadata: ChunkMetadata, chunk_text: str) -> None:
        edge.properties.setdefault("subreddit", metadata.subreddit)
        edge.properties.setdefault("layer", metadata.layer)
        edge.properties.setdefault("chunk_excerpt", chunk_text[:_CHUNK_EXCERPT_LENGTH])
        edge.properties.setdefault("last_seen_at", metadata.date)
        edge.properties.setdefault("source", metadata.subreddit)
        edge.sanitize()

    def _merge_properties(self, existing: dict[str, object], new: dict[str, object]) -> dict[str, object]:
        merged = dict(existing)
        for key, value in new.items():
            merged[key] = value
        return merged

    def nodes(self) -> list[Node]:
        return list(self._nodes.values())

    def edges(self) -> list[Edge]:
        return list(self._edges.values())
