from __future__ import annotations

import json
from typing import Any

from .storage import Storage


class ExplorationMap:
    def __init__(self, storage: Storage) -> None:
        self.storage = storage

    def record(self, exploration_id: str, run_id: str, payload: dict[str, Any]) -> None:
        self.storage.conn.execute(
            "INSERT OR REPLACE INTO exploration_map (exploration_id, run_id, payload_json) VALUES (?, ?, ?)",
            (exploration_id, run_id, json.dumps(payload)),
        )
        self.storage.conn.commit()
