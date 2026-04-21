"""Embeddings for extracted_problems (PRD §8.3 — E5-large-v2, 1024d)."""

from __future__ import annotations

from functools import lru_cache
from typing import Sequence

import numpy as np

from ..settings import SignalSettings, get_settings


@lru_cache(maxsize=4)
def _load_model(model_id: str, device: str):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as e:
        raise RuntimeError("sentence-transformers required for embeddings") from e

    return SentenceTransformer(model_id, device=device)


def embed_texts(texts: Sequence[str], settings: SignalSettings | None = None) -> np.ndarray:
    s = settings or get_settings()
    model = _load_model(s.embedding_model_id, s.embedding_device)
    mid = s.embedding_model_id.lower()
    prefixed: list[str] = []
    for t in texts:
        if "e5" in mid:
            prefixed.append(f"passage: {t}")
        else:
            prefixed.append(t)
    emb = model.encode(list(prefixed), normalize_embeddings=True)
    return np.asarray(emb, dtype=np.float32)


def embed_one(text: str, settings: SignalSettings | None = None) -> list[float]:
    v = embed_texts([text], settings=settings)[0]
    return v.tolist()
