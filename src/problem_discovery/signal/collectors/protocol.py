"""Collector contract (PRD §7.5)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterator


@dataclass
class RawRecord:
    """Normalized unit written to Tier A archive and raw_signals_index."""

    external_id: str
    source_timestamp: datetime | None
    url: str | None
    raw_payload: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthStatus:
    ok: bool
    message: str = ""


class Collector(ABC):
    """PRD §7.5 — source-specific pull + cheap gates."""

    source_name: str = "unknown"
    source_id: int = 0
    cadence_cron: str = "0 */4 * * *"
    tier: int = 1
    version: str = "0.1.0"

    @abstractmethod
    def fetch(self, since: datetime | None, run_id: str) -> Iterator[RawRecord]:
        """Pull raw records; idempotent by external_id."""

    def pre_filter(self, record: RawRecord) -> bool:
        """Cheap regex/length gate. Override per source."""
        text = _flatten_text(record.raw_payload)
        if len(text.strip()) < 20:
            return False
        return True

    def healthcheck(self) -> HealthStatus:
        return HealthStatus(ok=True)


def _flatten_text(raw: dict[str, Any]) -> str:
    parts: list[str] = []
    for v in raw.values():
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, dict):
            parts.append(_flatten_text(v))
    return " ".join(parts)
