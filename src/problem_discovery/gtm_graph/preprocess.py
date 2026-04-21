from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

CHUNK_SIZE = 512
CHUNK_OVERLAP = 64

MODEL = SentenceTransformer("all-MiniLM-L6-v2")


def preprocess_post(raw: dict[str, object]) -> dict[str, object]:
    raw_title = raw.get("title", "")
    raw_body = raw.get("body", "")
    comments = raw.get("top_comments", []) or []
    full_text = f"{raw_title}\n\n{raw_body}\n\n" + "\n".join(comments)
    cleaned = _clean_markdown(full_text)
    doc_hash = hashlib.md5(cleaned.encode("utf-8")).hexdigest()
    return {**raw, "clean_text": cleaned, "doc_hash": doc_hash}


def _clean_markdown(text: str) -> str:
    text = re.sub(r"http\S+", "", text)
    text = re.sub(r"\*+|#{1,6}|`{1,3}|\[.*?\]\(.*?\)", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


@dataclass
class Chunk:
    text: str
    start_offset: int
    end_offset: int


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[Chunk]:
    if not text:
        return []
    step = chunk_size - overlap
    chunks: list[Chunk] = []
    cursor = 0
    length = len(text)
    while cursor < length:
        end = min(cursor + chunk_size, length)
        chunk_text = text[cursor:end]
        chunks.append(Chunk(chunk_text, cursor, end))
        cursor += step
    return chunks


def deduplicate(posts: Sequence[dict[str, object]], threshold: float = 0.92) -> list[dict[str, object]]:
    if not posts:
        return []
    texts = [post["clean_text"] for post in posts]
    embeddings = MODEL.encode(texts, batch_size=64, show_progress_bar=False)
    unique_docs: list[dict[str, object]] = []
    seen: list[np.ndarray] = []
    for idx, post in enumerate(posts):
        vector = embeddings[idx]
        if seen:
            sims = cosine_similarity([vector], seen)[0]
            if any(sim > threshold for sim in sims):
                continue
        unique_docs.append(post)
        seen.append(vector)
    return unique_docs
