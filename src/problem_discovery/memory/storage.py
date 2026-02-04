from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class Storage:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                niche TEXT,
                created_at TEXT,
                summary_json TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS signals (
                signal_id TEXT PRIMARY KEY,
                run_id TEXT,
                agent_id TEXT,
                payload_json TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS clusters (
                cluster_id TEXT PRIMARY KEY,
                run_id TEXT,
                payload_json TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS failures (
                failure_id TEXT PRIMARY KEY,
                niche TEXT,
                payload_json TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS patterns (
                pattern_id TEXT PRIMARY KEY,
                niche TEXT,
                payload_json TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS exploration_map (
                exploration_id TEXT PRIMARY KEY,
                run_id TEXT,
                payload_json TEXT
            )
            """
        )
        self.conn.commit()

    def insert_run(self, run_id: str, niche: str, created_at: str, summary: dict[str, Any]) -> None:
        self.conn.execute(
            "INSERT INTO runs (run_id, niche, created_at, summary_json) VALUES (?, ?, ?, ?)",
            (run_id, niche, created_at, json.dumps(summary)),
        )
        self.conn.commit()

    def insert_signal(self, signal_id: str, run_id: str, agent_id: str, payload: dict[str, Any]) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO signals (signal_id, run_id, agent_id, payload_json) VALUES (?, ?, ?, ?)",
            (signal_id, run_id, agent_id, json.dumps(payload)),
        )
        self.conn.commit()

    def insert_cluster(self, cluster_id: str, run_id: str, payload: dict[str, Any]) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO clusters (cluster_id, run_id, payload_json) VALUES (?, ?, ?)",
            (cluster_id, run_id, json.dumps(payload)),
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

