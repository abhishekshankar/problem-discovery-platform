from __future__ import annotations

import argparse
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .connector import ChunkMetadata, ExtractionSchemaConnector
from .extractor import LLMExtractor
from .graph_loader import create_driver, ingest_nodes_and_edges
from .ingest import read_jsonl, run_ingestion, write_jsonl
from .preprocess import CHUNK_OVERLAP, CHUNK_SIZE, chunk_text, deduplicate, preprocess_post
from .schema import Edge, Node

LOGGER = logging.getLogger(__name__)
DEFAULT_OUTPUT_DIR = Path("output/gtm_graph")


def _serialize_node(node: Node) -> dict[str, object]:
    return {"id": node.id, "label": node.label, "properties": node.properties}


def _serialize_edge(edge: Edge) -> dict[str, object]:
    return {
        "source": edge.source,
        "target": edge.target,
        "relationship": edge.relationship,
        "properties": edge.properties,
    }


def _load_posts(path: Path) -> list[dict[str, object]]:
    return list(read_jsonl(path))


def _prepare_chunks(
    posts: Iterable[dict[str, object]],
    max_chunks: int | None = None,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> list[tuple[str, dict[str, object]]]:
    chunks: list[tuple[str, dict[str, object]]] = []
    for post in posts:
        clean_text = post.get("clean_text")
        if not clean_text:
            continue
        for chunk in chunk_text(clean_text, chunk_size, chunk_overlap):
            metadata = {
                "subreddit": post.get("subreddit", ""),
                "layer": post.get("layer", ""),
                "score": post.get("score", 0),
                "date": post.get("created_utc", str(datetime.utcnow().isoformat())),
                "query": post.get("query"),
            }
            chunks.append((chunk.text, metadata))
            if max_chunks and len(chunks) >= max_chunks:
                return chunks
    return chunks


def _run_extraction(
    extractor: LLMExtractor,
    chunks: list[tuple[str, dict[str, object]]],
) -> tuple[list[Node], list[Edge]]:
    connector = ExtractionSchemaConnector()
    for chunk_text, metadata in chunks:
        chunk_meta = ChunkMetadata.from_dict(metadata)
        nodes, edges = extractor.extract(chunk_text, metadata)
        connector.ingest_chunk(chunk_text, chunk_meta, nodes, edges)
    return connector.nodes(), connector.edges()


def run_pipeline(args: argparse.Namespace) -> None:
    run_id = args.run_id or datetime.utcnow().strftime("%Y%m%d%H%M%S")
    output_dir = Path(args.output_dir or DEFAULT_OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_path = output_dir / f"reddit_raw_{run_id}.jsonl"
    nodes_path = output_dir / f"gtm_nodes_{run_id}.jsonl"
    edges_path = output_dir / f"gtm_edges_{run_id}.jsonl"

    if not args.praw_client_id or not args.praw_client_secret:
        raise RuntimeError(
            "PRAW credentials are required; set GTM_PRAW_CLIENT_ID and GTM_PRAW_CLIENT_SECRET in "
            "your environment or pass --praw-client-id/--praw-client-secret explicitly."
        )

    run_ingestion(
        raw_path,
        args.praw_client_id,
        args.praw_client_secret,
        args.praw_user_agent,
        max_results_per_query=args.max_results_per_query,
    )

    posts = [preprocess_post(post) for post in _load_posts(raw_path)]
    deduped = deduplicate(posts)
    chunks = _prepare_chunks(deduped, max_chunks=args.max_chunks)

    extractor = LLMExtractor(model=args.llm_model, temperature=args.llm_temperature, dry_run=args.dry_run)
    nodes, edges = _run_extraction(extractor, chunks)

    write_jsonl(nodes_path, [_serialize_node(node) for node in nodes])
    write_jsonl(edges_path, [_serialize_edge(edge) for edge in edges])

    LOGGER.info("Wrote %d nodes to %s", len(nodes), nodes_path)
    LOGGER.info("Wrote %d edges to %s", len(edges), edges_path)

    if args.neo4j_uri:
        if not (args.neo4j_username and args.neo4j_password):
            raise RuntimeError("--neo4j-username and --neo4j-password are required when --neo4j-uri is provided")
        driver = create_driver(args.neo4j_uri, args.neo4j_username, args.neo4j_password)
        ingest_nodes_and_edges(driver, nodes, edges)
        LOGGER.info("Ingested nodes/edges into Neo4j at %s", args.neo4j_uri)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Pipeline for GTM knowledge graph extraction")
    parser.add_argument("--praw-client-id", default=os.getenv("GTM_PRAW_CLIENT_ID"))
    parser.add_argument("--praw-client-secret", default=os.getenv("GTM_PRAW_CLIENT_SECRET"))
    parser.add_argument(
        "--praw-user-agent",
        default=os.getenv("GTM_PRAW_USER_AGENT", "GTM-KG-Builder/1.0"),
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--run-id", help="Optional run identifier for files")
    parser.add_argument("--max-results-per-query", type=int, default=100)
    parser.add_argument("--max-chunks", type=int, default=50)
    parser.add_argument("--llm-model", default="gpt-4o")
    parser.add_argument("--llm-temperature", type=float, default=0.1)
    parser.add_argument("--dry-run", action="store_true", help="Skip OpenAI calls (useful for testing)")
    parser.add_argument("--neo4j-uri", default=os.getenv("GTM_NEO4J_URI"), help="Optional bolt URI to auto-ingest results")
    parser.add_argument("--neo4j-username", default=os.getenv("GTM_NEO4J_USERNAME"))
    parser.add_argument("--neo4j-password", default=os.getenv("GTM_NEO4J_PASSWORD"))
    return parser


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = _build_parser()
    args = parser.parse_args()
    run_pipeline(args)


if __name__ == "__main__":
    main()
