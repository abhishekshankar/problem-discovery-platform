from __future__ import annotations

import json
from typing import Any

from .storage import Storage


class FailureDatabase:
    def __init__(self, storage: Storage) -> None:
        self.storage = storage

    def find_similar(self, niche: str, keywords: str) -> dict[str, Any] | None:
        cur = self.storage.conn.cursor()
        cur.execute("SELECT payload_json FROM failures WHERE niche = ?", (niche,))
        rows = cur.fetchall()
        for row in rows:
            payload = json.loads(row[0])
            if keywords.lower() in payload.get("problem_description", "").lower():
                return payload
        return None
