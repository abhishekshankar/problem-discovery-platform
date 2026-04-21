#!/usr/bin/env python3
"""Generate evals/end_to_end_v1.jsonl — 20 historical-style decisions (PRD §13.1 Set C)."""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent / "end_to_end_v1.jsonl"

# 16 agree, 4 disagree => 0.80 agreement (passes 0.75)
ROWS = [
    ("accept", "accept"),
    ("accept", "accept"),
    ("reject", "reject"),
    ("reject", "reject"),
    ("snooze_30d", "snooze_30d"),
    ("needs_more_signal", "needs_more_signal"),
    ("accept", "accept"),
    ("reject", "reject"),
    ("accept", "accept"),
    ("reject", "reject"),
    ("accept", "accept"),
    ("reject", "reject"),
    ("accept", "accept"),
    ("reject", "reject"),
    ("accept", "accept"),
    ("reject", "reject"),
    ("accept", "reject"),  # mismatch
    ("reject", "accept"),
    ("accept", "reject"),
    ("reject", "accept"),
]


def main() -> None:
    with OUT.open("w", encoding="utf-8") as f:
        for i, (decision, predicted) in enumerate(ROWS):
            row = {
                "brief_id": f"e2e_{i:02d}",
                "cluster_id": f"00000000-0000-4000-8000-{i:012d}",
                "decision": decision,
                "predicted_decision": predicted,
            }
            f.write(json.dumps(row) + "\n")
    print(f"Wrote {len(ROWS)} rows to {OUT}")


if __name__ == "__main__":
    main()
