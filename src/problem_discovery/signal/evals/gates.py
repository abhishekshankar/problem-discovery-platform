"""Eval gate matrix (PRD §13.2) — used by CI / pre-merge hooks."""

from __future__ import annotations

# change_type -> required eval set types that must pass before promote
EVAL_GATES: dict[str, tuple[str, ...]] = {
    "extractor_prompt": ("extractor",),
    "extraction_model": ("extractor",),
    "embedding_model": ("clusterer",),
    "clustering_algorithm": ("clusterer",),
    "ranker_filter": ("end_to_end",),
    "brief_prompt": ("manual_review_briefs",),
}


def required_evals_for_change(change_type: str) -> tuple[str, ...]:
    return EVAL_GATES.get(change_type, ("extractor", "clusterer", "end_to_end"))
