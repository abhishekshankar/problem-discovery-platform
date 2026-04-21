"""PRD §8.1 — Reddit-style target phrases (subset; expand per domain)."""

from __future__ import annotations

import re

REDDIT_PROBLEM_PHRASES = re.compile(
    r"|".join(
        re.escape(p)
        for p in (
            "is there a tool",
            "i wish",
            "i built a spreadsheet",
            "how do you all handle",
            "anyone know of",
            "looking for something that",
            "struggling with",
            "workaround",
            "no good option",
            "has anyone found",
            "recommend a",
            "alternative to",
            "switched from",
            "pain point",
            "frustrated with",
        )
    ),
    re.IGNORECASE,
)


def reddit_text_matches_phrases(text: str) -> bool:
    if not text or len(text.strip()) < 30:
        return False
    return bool(REDDIT_PROBLEM_PHRASES.search(text))
