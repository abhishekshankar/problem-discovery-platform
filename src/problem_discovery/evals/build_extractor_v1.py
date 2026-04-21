#!/usr/bin/env python3
"""Generate evals/extractor_v1.jsonl — stratified seed set (PRD §13.1 Set A).

Replace or extend with real hand-labeled domain posts for production gates.
Target: 200 rows — 40% obvious problems, 30% borderline, 30% non-problems.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

OUT = Path(__file__).resolve().parent / "extractor_v1.jsonl"

OBVIOUS = [
    (
        "Our EHR forces us to re-enter lab values every Friday; takes 2 hours and we pay ~$1800/mo for a scribe workaround.",
        True,
        9,
        "frustrated",
        "proven",
    ),
    (
        "Is there a tool that syncs patient scheduling between Athena and our fertility clinic's legacy CRM? We lose 4h/week.",
        True,
        8,
        "formed",
        "strong",
    ),
    (
        "I wish there was something like Linear but for clinical trial recruitment tracking — spreadsheets are killing us.",
        True,
        7,
        "formed",
        "weak",
    ),
    (
        "How do you all handle prior auth fax backlog for IVF meds? We're drowning.",
        True,
        8,
        "frustrated",
        "strong",
    ),
    (
        "Looking for something that flags drug interaction risks against our supplement stack for PCOS patients.",
        True,
        7,
        "formed",
        "weak",
    ),
]

BORDERLINE = [
    (
        "Healthcare IT is broken.",
        True,
        3,
        "unformed",
        "weak",
    ),
    (
        "Another day another EHR rant.",
        False,
        2,
        "unformed",
        "none",
    ),
    (
        "Thinking about building a small app for cycle tracking integrations.",
        False,
        4,
        "unformed",
        "none",
    ),
    (
        "Anyone else annoyed by clinic portals?",
        True,
        4,
        "unformed",
        "weak",
    ),
    (
        "We might need better reporting someday.",
        False,
        3,
        "unformed",
        "none",
    ),
]

NON_PROBLEM = [
    ("Just launched our Series A for a new wellness brand!", False, 1, "unformed", "none"),
    ("Hiring: senior backend engineer, remote.", False, 1, "unformed", "none"),
    ("10 tips to boost your morning routine.", False, 2, "unformed", "none"),
    ("Buy my course on productivity.", False, 1, "unformed", "none"),
    ("Happy Friday everyone!", False, 1, "unformed", "none"),
]


def _synth_variants(base: str, i: int) -> str:
    return f"{base} [ex{i}]"


def main() -> None:
    rng = random.Random(42)
    rows: list[dict] = []
    idx = 0

    def add_pool(pool: list, label: str, n_target: int) -> None:
        nonlocal idx
        while len([r for r in rows if r["_stratum"] == label]) < n_target:
            item = rng.choice(pool)
            text, is_prob, spec, layer, wtp = item
            variant = _synth_variants(text, idx)
            rows.append(
                {
                    "id": f"seta_{idx:04d}",
                    "text": variant,
                    "source_label": "synthetic",
                    "is_problem_signal": is_prob,
                    "specificity_score": float(spec),
                    "layer": layer,
                    "wtp_level": wtp,
                    "_stratum": label,
                }
            )
            idx += 1

    n = 200
    n_obv = int(n * 0.40)
    n_brd = int(n * 0.30)
    n_non = n - n_obv - n_brd

    add_pool(OBVIOUS, "obvious", n_obv)
    add_pool(BORDERLINE, "borderline", n_brd)
    add_pool(NON_PROBLEM, "non_problem", n_non)

    for r in rows:
        r.pop("_stratum", None)

    rng.shuffle(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"Wrote {len(rows)} rows to {OUT}")


if __name__ == "__main__":
    main()
