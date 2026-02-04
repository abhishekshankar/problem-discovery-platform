from __future__ import annotations

import json
from typing import Any

from .storage import Storage


class PatternLibrary:
    def __init__(self, storage: Storage) -> None:
        self.storage = storage

    def find_relevant(self, niche: str) -> list[dict[str, Any]]:
        cur = self.storage.conn.cursor()
        cur.execute("SELECT payload_json FROM patterns WHERE niche = ?", (niche,))
        rows = cur.fetchall()
        return [json.loads(row[0]) for row in rows]
