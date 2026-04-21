#!/usr/bin/env python3
"""Generate evals/clusterer_v1.jsonl — 300 synthetic problems with gold + predicted clusters (PRD §13.1 Set B).

Replace with real hand-grouped gold + model predictions from BERTopic for production gates.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import numpy as np
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer

OUT = Path(__file__).resolve().parent / "clusterer_v1.jsonl"

TOPICS = [
    "EHR data re-entry wastes nursing time every week",
    "prior authorization fax workflows for fertility meds",
    "patient scheduling double-booking between Athena and paper",
    "clinical trial recruitment CRM is spreadsheet hell",
    "lab result routing to wrong chart in multi-site clinics",
    "HIPAA-compliant patient messaging gaps",
    "inventory tracking for IVF medication cold chain",
    "insurance verification bots fail on rare codes",
    "telehealth no-show follow-up automation",
    "referral loop closure between PCP and specialists",
]

NOISE = [
    "The workflow is painful and manual.",
    "We tried three vendors and still patch with Excel.",
    "Leadership wants a dashboard but data is siloed.",
    "Compliance review slows every release.",
    "Nurses hate the extra clicks.",
]


def main() -> None:
    rng = random.Random(4242)
    texts: list[str] = []
    gold: list[int] = []
    for tidx, topic in enumerate(TOPICS):
        for _ in range(30):
            texts.append(f"{topic}. {rng.choice(NOISE)} [v{len(texts)}]")
            gold.append(tidx)

    vec = TfidfVectorizer(max_features=200, stop_words="english")
    X = vec.fit_transform(texts).toarray()
    n_pred = 12
    pred_labels = KMeans(n_clusters=n_pred, random_state=42, n_init=10).fit_predict(X)

    # Map predicted labels to stable ids
    pred_map = {p: i for i, p in enumerate(sorted(set(pred_labels)))}

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        for i, (text, g, p) in enumerate(zip(texts, gold, pred_labels)):
            row = {
                "problem_id": f"cp_{i:04d}",
                "text": text,
                "gold_cluster_id": str(g),
                "predicted_cluster_id": str(pred_map[p]),
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Wrote {len(texts)} rows to {OUT}")


if __name__ == "__main__":
    main()
