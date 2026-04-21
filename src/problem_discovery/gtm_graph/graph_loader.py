from __future__ import annotations

from typing import Iterable

from neo4j import GraphDatabase, Transaction
from sentence_transformers import SentenceTransformer

from .schema import Edge, Node

EMBEDDING_MODEL = SentenceTransformer("all-MiniLM-L6-v2")


def create_driver(uri: str, username: str, password: str):
    return GraphDatabase.driver(uri, auth=(username, password))


def resolve_entity(tx: Transaction, node: Node, score: float = 0.0) -> None:
    node.sanitize()
    embedding = EMBEDDING_MODEL.encode(node.id).tolist()
    props = {**node.properties, "score": score}
    tx.run(
        f"""
        MERGE (n:{node.label} {{name: $name}})
        ON CREATE SET n += $props, n.embedding = $embedding, n.created_at = datetime()
        ON MATCH SET n.mention_count = coalesce(n.mention_count, 0) + 1,
                     n.avg_score = (coalesce(n.avg_score, 0) + $score) / 2
        """,
        name=node.id,
        props=props,
        embedding=embedding,
        score=score,
    )


def load_edge(tx: Transaction, edge: Edge) -> None:
    edge.sanitize()
    tx.run(
        f"""
        MATCH (a {{name: $source}}), (b {{name: $target}})
        MERGE (a)-[r:{edge.relationship}]->(b)
        ON CREATE SET r += $props, r.created_at = datetime()
        ON MATCH SET r.confidence = (coalesce(r.confidence, 0) + $confidence) / 2
        """,
        source=edge.source,
        target=edge.target,
        props=edge.properties,
        confidence=edge.properties.get("confidence", 0.5),
    )


def create_vector_index(tx: Transaction) -> None:
    tx.run(
        """
        CREATE VECTOR INDEX gtm_node_embeddings IF NOT EXISTS
        FOR (n:GTMStrategy) ON (n.embedding)
        OPTIONS {indexConfig: {`vector.dimensions`: 384, `vector.similarity_function`: 'cosine'}}
        """
    )


def ingest_nodes_and_edges(
    driver,
    nodes: Iterable[Node],
    edges: Iterable[Edge],
    score_map: dict[str, float] | None = None,
) -> None:
    with driver.session() as session:
        session.write_transaction(create_vector_index)
        for node in nodes:
            node_score = score_map.get(node.id, 0.0) if score_map else 0.0
            session.write_transaction(resolve_entity, node, node_score)
        for edge in edges:
            session.write_transaction(load_edge, edge)
