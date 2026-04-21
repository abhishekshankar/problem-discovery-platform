from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from datetime import datetime
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
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS reddit_corpus (
                signal_id TEXT PRIMARY KEY,
                source_subreddit TEXT NOT NULL,
                signal_type TEXT NOT NULL,
                created_utc TEXT NOT NULL,
                text TEXT,
                thread_id TEXT,
                thread_depth INTEGER,
                score INTEGER,
                upvote_ratio REAL,
                num_comments INTEGER,
                permalink TEXT,
                ivf_stage_hint TEXT,
                specificity_score REAL,
                ssm_stage TEXT,
                has_workaround INTEGER,
                workaround_type TEXT,
                has_competitor_churn INTEGER,
                economic_equiv_value REAL,
                bdm_adjusted_wtp REAL,
                author_hash TEXT,
                payload_json TEXT
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_reddit_corpus_subreddit_created ON reddit_corpus(source_subreddit, created_utc)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_reddit_corpus_stage_ssm ON reddit_corpus(ivf_stage_hint, ssm_stage)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_reddit_corpus_workaround_score ON reddit_corpus(has_workaround, score)")
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

    def upsert_reddit_signals(self, signals: list[dict[str, Any]]) -> int:
        if not signals:
            return 0
        rows = []
        for signal in signals:
            rows.append(
                (
                    signal.get("signal_id"),
                    signal.get("source_subreddit"),
                    signal.get("signal_type"),
                    signal.get("created_utc"),
                    signal.get("text"),
                    signal.get("thread_id"),
                    signal.get("thread_depth"),
                    signal.get("score"),
                    signal.get("upvote_ratio"),
                    signal.get("num_comments"),
                    signal.get("permalink"),
                    signal.get("ivf_stage_hint"),
                    signal.get("specificity_score"),
                    signal.get("ssm_stage"),
                    self._bool_to_int(signal.get("has_workaround")),
                    signal.get("workaround_type"),
                    self._bool_to_int(signal.get("has_competitor_churn")),
                    signal.get("economic_equiv_value"),
                    signal.get("bdm_adjusted_wtp"),
                    signal.get("author_hash"),
                    json.dumps(signal),
                )
            )

        self.conn.executemany(
            """
            INSERT OR REPLACE INTO reddit_corpus (
                signal_id, source_subreddit, signal_type, created_utc, text, thread_id, thread_depth,
                score, upvote_ratio, num_comments, permalink, ivf_stage_hint,
                specificity_score, ssm_stage, has_workaround, workaround_type,
                has_competitor_churn, economic_equiv_value, bdm_adjusted_wtp, author_hash, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        self.conn.commit()
        return len(rows)

    def count_reddit_corpus_rows(self, subreddits: list[str] | None = None) -> int:
        if not subreddits:
            row = self.conn.execute("SELECT COUNT(*) AS c FROM reddit_corpus").fetchone()
            return int(row["c"]) if row else 0
        placeholders = ",".join("?" for _ in subreddits)
        row = self.conn.execute(
            f"SELECT COUNT(*) AS c FROM reddit_corpus WHERE source_subreddit IN ({placeholders})",
            tuple(subreddits),
        ).fetchone()
        return int(row["c"]) if row else 0

    def build_reddit_ingestion_qa(self, subreddits: list[str]) -> dict[str, Any]:
        qa: dict[str, Any] = {}
        qa["totals_per_subreddit"] = self._subreddit_totals(subreddits)
        qa["monthly_counts"] = self._subreddit_monthly_counts(subreddits)
        qa["stage_hint_post_rate"] = self._stage_hint_post_rate(subreddits)
        qa["comment_parent_link_rate"] = self._comment_parent_link_rate(subreddits)
        qa["null_rates"] = self._null_rates(subreddits)
        qa["coverage_gaps_gt_7d"] = self._coverage_gaps(subreddits)
        qa["dedup_summary"] = self._dedup_summary(subreddits)
        return qa

    def _subreddit_totals(self, subreddits: list[str]) -> dict[str, int]:
        out: dict[str, int] = {}
        for subreddit in subreddits:
            row = self.conn.execute(
                "SELECT COUNT(*) AS c FROM reddit_corpus WHERE source_subreddit = ?",
                (subreddit,),
            ).fetchone()
            out[subreddit] = int(row["c"]) if row else 0
        return out

    def _subreddit_monthly_counts(self, subreddits: list[str]) -> dict[str, dict[str, int]]:
        out: dict[str, dict[str, int]] = {}
        for subreddit in subreddits:
            rows = self.conn.execute(
                """
                SELECT substr(created_utc, 1, 7) AS ym, COUNT(*) AS c
                FROM reddit_corpus
                WHERE source_subreddit = ?
                GROUP BY ym
                ORDER BY ym ASC
                """,
                (subreddit,),
            ).fetchall()
            out[subreddit] = {str(row["ym"]): int(row["c"]) for row in rows}
        return out

    def _stage_hint_post_rate(self, subreddits: list[str]) -> float:
        placeholders = ",".join("?" for _ in subreddits)
        row = self.conn.execute(
            f"""
            SELECT
                SUM(CASE WHEN signal_type = 'post' THEN 1 ELSE 0 END) AS total_posts,
                SUM(CASE WHEN signal_type = 'post' AND ivf_stage_hint IS NOT NULL AND ivf_stage_hint != '' THEN 1 ELSE 0 END) AS hinted_posts
            FROM reddit_corpus
            WHERE source_subreddit IN ({placeholders})
            """,
            tuple(subreddits),
        ).fetchone()
        total_posts = int(row["total_posts"] or 0) if row else 0
        hinted_posts = int(row["hinted_posts"] or 0) if row else 0
        return round((hinted_posts / total_posts) * 100, 2) if total_posts else 0.0

    def _comment_parent_link_rate(self, subreddits: list[str]) -> float:
        placeholders = ",".join("?" for _ in subreddits)
        row = self.conn.execute(
            f"""
            SELECT
                SUM(CASE WHEN signal_type = 'comment' THEN 1 ELSE 0 END) AS total_comments,
                SUM(CASE WHEN signal_type = 'comment' AND thread_id IS NOT NULL AND thread_id != '' THEN 1 ELSE 0 END) AS linked_comments
            FROM reddit_corpus
            WHERE source_subreddit IN ({placeholders})
            """,
            tuple(subreddits),
        ).fetchone()
        total_comments = int(row["total_comments"] or 0) if row else 0
        linked_comments = int(row["linked_comments"] or 0) if row else 0
        return round((linked_comments / total_comments) * 100, 2) if total_comments else 0.0

    def _null_rates(self, subreddits: list[str]) -> dict[str, float]:
        placeholders = ",".join("?" for _ in subreddits)
        row = self.conn.execute(
            f"""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN score IS NULL THEN 1 ELSE 0 END) AS score_nulls,
                SUM(CASE WHEN text IS NULL OR text = '' THEN 1 ELSE 0 END) AS text_nulls,
                SUM(CASE WHEN created_utc IS NULL OR created_utc = '' THEN 1 ELSE 0 END) AS created_utc_nulls
            FROM reddit_corpus
            WHERE source_subreddit IN ({placeholders})
            """,
            tuple(subreddits),
        ).fetchone()
        total = int(row["total"] or 0) if row else 0
        if total == 0:
            return {"score": 0.0, "text": 0.0, "created_utc": 0.0}
        return {
            "score": round((int(row["score_nulls"] or 0) / total) * 100, 2),
            "text": round((int(row["text_nulls"] or 0) / total) * 100, 2),
            "created_utc": round((int(row["created_utc_nulls"] or 0) / total) * 100, 2),
        }

    def _coverage_gaps(self, subreddits: list[str]) -> dict[str, list[dict[str, Any]]]:
        out: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for subreddit in subreddits:
            rows = self.conn.execute(
                """
                SELECT created_utc
                FROM reddit_corpus
                WHERE source_subreddit = ?
                ORDER BY created_utc ASC
                """,
                (subreddit,),
            ).fetchall()
            if not rows:
                continue
            prev = self._parse_iso(rows[0]["created_utc"])
            for row in rows[1:]:
                curr = self._parse_iso(row["created_utc"])
                if curr is None or prev is None:
                    prev = curr
                    continue
                delta_days = (curr - prev).days
                if delta_days > 7:
                    out[subreddit].append(
                        {
                            "start_utc": prev.isoformat(),
                            "end_utc": curr.isoformat(),
                            "gap_days": delta_days,
                        }
                    )
                prev = curr
        return dict(out)

    def _dedup_summary(self, subreddits: list[str]) -> dict[str, int]:
        placeholders = ",".join("?" for _ in subreddits)
        row = self.conn.execute(
            f"""
            SELECT COUNT(*) AS total_rows, COUNT(DISTINCT signal_id) AS distinct_rows
            FROM reddit_corpus
            WHERE source_subreddit IN ({placeholders})
            """,
            tuple(subreddits),
        ).fetchone()
        total_rows = int(row["total_rows"] or 0) if row else 0
        distinct_rows = int(row["distinct_rows"] or 0) if row else 0
        return {
            "total_rows": total_rows,
            "distinct_signal_ids": distinct_rows,
            "deduplicated_records": max(0, total_rows - distinct_rows),
        }

    @staticmethod
    def _bool_to_int(value: Any) -> int | None:
        if value is None:
            return None
        return 1 if bool(value) else 0

    @staticmethod
    def _parse_iso(value: Any) -> datetime | None:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None

    def close(self) -> None:
        self.conn.close()
