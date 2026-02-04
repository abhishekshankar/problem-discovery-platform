from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .base import Agent, AgentResult
from .utils import stable_uuid, utc_now


class AgentADevvit(Agent):
    """Load Reddit signals captured by a Devvit app sidecar."""

    agent_id = "A"
    platform = "reddit_devvit"

    def __init__(self, seed: int, signal_path: Path) -> None:
        self.seed = seed
        self.signal_path = signal_path

    def _load_signals(self) -> list[dict[str, Any]]:
        if not self.signal_path.exists():
            return []
        signals = []
        with self.signal_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                signals.append(payload)
        return signals

    def run(self, context: dict[str, Any]) -> AgentResult:
        max_signals = int(context.get("max_signals", 20))
        niche = context.get("niche", "").lower()
        raw = self._load_signals()
        filtered = []
        for payload in raw:
            text = " ".join(
                [
                    str(payload.get("title", "")),
                    str(payload.get("body", "")),
                    str(payload.get("subreddit", "")),
                ]
            ).lower()
            if niche and niche not in text:
                continue
            signal_id = payload.get("signal_id") or stable_uuid(self.seed, str(payload.get("id", "")))
            filtered.append(
                {
                    "signal_id": signal_id,
                    "source_agent": self.agent_id,
                    "source_platform": self.platform,
                    "source_url": payload.get("url", ""),
                    "timestamp_found": payload.get("timestamp", utc_now()),
                    "content": {
                        "title": payload.get("title", ""),
                        "body": payload.get("body", ""),
                        "author": payload.get("author", ""),
                        "engagement": {
                            "upvotes": payload.get("upvotes", 0),
                            "comments": payload.get("comments", 0),
                        },
                    },
                    "extracted_data": {
                        "pain_point": payload.get("pain_point", ""),
                        "verbatim_quote": payload.get("quote", ""),
                        "emotion_score": payload.get("emotion_score", 5),
                        "signal_type": payload.get("signal_type", "unknown"),
                        "inferred_wtp": payload.get("inferred_wtp", "medium"),
                    },
                    "metadata": {
                        "post_date": payload.get("post_date", ""),
                        "subreddit": payload.get("subreddit", ""),
                        "flair": payload.get("flair", ""),
                    },
                }
            )
            if len(filtered) >= max_signals:
                break
        return AgentResult(agent_id=self.agent_id, payload={"signals": filtered})
