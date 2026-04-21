from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ..schemas import RedditSignal


PUSHSHIFT_BASE_URL = "https://api.pushshift.io/reddit/search"
REDDIT_BASE_URL = "https://www.reddit.com"


class IVFRedditCollector:
    def __init__(
        self,
        *,
        subreddits: list[str],
        months_back: int = 24,
        max_records_per_subreddit: int = 100_000,
        use_pushshift: bool = True,
        use_praw: bool = False,
        praw_client_id: str | None = None,
        praw_client_secret: str | None = None,
        praw_user_agent: str | None = None,
    ) -> None:
        self.subreddits = subreddits
        self.months_back = months_back
        self.max_records_per_subreddit = max_records_per_subreddit
        self.use_pushshift = use_pushshift
        self.use_praw = use_praw
        self.praw_client_id = praw_client_id
        self.praw_client_secret = praw_client_secret
        self.praw_user_agent = praw_user_agent or "problem-discovery-ivf/1.0"

    def collect(self) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        after = now - timedelta(days=self.months_back * 30)
        after_epoch = int(after.timestamp())
        before_epoch = int(now.timestamp())
        normalized: list[RedditSignal] = []
        seen: set[str] = set()

        source_counts: dict[str, int] = {"pushshift_posts": 0, "pushshift_comments": 0, "praw_posts": 0, "praw_comments": 0}

        for subreddit in self.subreddits:
            if self.use_pushshift:
                posts = self._fetch_pushshift("submission", subreddit, after_epoch, before_epoch, self.max_records_per_subreddit)
                comments = self._fetch_pushshift("comment", subreddit, after_epoch, before_epoch, self.max_records_per_subreddit * 4)
                source_counts["pushshift_posts"] += len(posts)
                source_counts["pushshift_comments"] += len(comments)
                for item in posts:
                    signal = self._normalize_pushshift_submission(item, subreddit)
                    if signal.signal_id not in seen:
                        seen.add(signal.signal_id)
                        normalized.append(signal)
                for item in comments:
                    signal = self._normalize_pushshift_comment(item, subreddit)
                    if signal.signal_id not in seen:
                        seen.add(signal.signal_id)
                        normalized.append(signal)

            if self.use_praw:
                praw_posts, praw_comments = self._fetch_praw_recent(subreddit)
                source_counts["praw_posts"] += len(praw_posts)
                source_counts["praw_comments"] += len(praw_comments)
                for item in praw_posts:
                    signal = self._normalize_praw_submission(item, subreddit)
                    if signal.signal_id not in seen:
                        seen.add(signal.signal_id)
                        normalized.append(signal)
                for item in praw_comments:
                    signal = self._normalize_praw_comment(item, subreddit)
                    if signal.signal_id not in seen:
                        seen.add(signal.signal_id)
                        normalized.append(signal)

        return {
            "signals": [asdict(item) for item in normalized],
            "source_counts": source_counts,
            "window": {
                "after_utc": self._to_iso(after_epoch),
                "before_utc": self._to_iso(before_epoch),
            },
        }

    def _fetch_pushshift(
        self,
        kind: str,
        subreddit: str,
        after_epoch: int,
        before_epoch: int,
        max_records: int,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        cursor = after_epoch
        page_size = 200
        while len(results) < max_records:
            query = urlencode(
                {
                    "subreddit": subreddit,
                    "after": cursor,
                    "before": before_epoch,
                    "size": page_size,
                    "sort": "asc",
                    "sort_type": "created_utc",
                }
            )
            url = f"{PUSHSHIFT_BASE_URL}/{kind}/?{query}"
            payload = self._http_json(url)
            data = payload.get("data", []) if isinstance(payload, dict) else []
            if not data:
                break
            results.extend(data)
            last_created = max(int(item.get("created_utc", 0)) for item in data)
            if last_created <= cursor:
                break
            cursor = last_created + 1
            time.sleep(0.15)
        return results[:max_records]

    def _fetch_praw_recent(self, subreddit: str) -> tuple[list[Any], list[Any]]:
        try:
            import praw  # type: ignore
        except ImportError:
            return [], []
        if not (self.praw_client_id and self.praw_client_secret):
            return [], []

        reddit = praw.Reddit(
            client_id=self.praw_client_id,
            client_secret=self.praw_client_secret,
            user_agent=self.praw_user_agent,
        )
        posts: list[Any] = []
        comments: list[Any] = []
        sub = reddit.subreddit(subreddit)
        for submission in sub.new(limit=1000):
            posts.append(submission)
        for comment in sub.comments(limit=2000):
            comments.append(comment)
        return posts, comments

    def _normalize_pushshift_submission(self, item: dict[str, Any], subreddit: str) -> RedditSignal:
        sid = str(item.get("id", ""))
        title = str(item.get("title", "")).strip()
        body = str(item.get("selftext", "")).strip()
        text = " ".join(part for part in [title, body] if part).strip()
        flair = str(item.get("link_flair_text", "")).strip()
        permalink = str(item.get("permalink") or f"/r/{subreddit}/comments/{sid}")
        return RedditSignal(
            signal_id=self._signal_id(subreddit, "post", sid),
            source_subreddit=subreddit,
            signal_type="post",
            created_utc=self._to_iso(int(item.get("created_utc", 0))),
            text=text,
            thread_id=sid,
            thread_depth=0,
            score=self._as_int(item.get("score")),
            upvote_ratio=self._as_float(item.get("upvote_ratio")),
            num_comments=self._as_int(item.get("num_comments")),
            permalink=self._abs_permalink(permalink),
            ivf_stage_hint=self._detect_stage_hint(text=text, flair=flair),
            author_hash=self._author_hash(item.get("author")),
        )

    def _normalize_pushshift_comment(self, item: dict[str, Any], subreddit: str) -> RedditSignal:
        cid = str(item.get("id", ""))
        body = str(item.get("body", "")).strip()
        parent_id = str(item.get("parent_id", ""))
        link_id = str(item.get("link_id", ""))
        thread_id = link_id.replace("t3_", "") if link_id else parent_id.replace("t3_", "")
        depth = 1 if parent_id.startswith("t1_") else 0
        permalink = str(item.get("permalink") or f"/r/{subreddit}/comments/{thread_id}/_/{cid}")
        return RedditSignal(
            signal_id=self._signal_id(subreddit, "comment", cid),
            source_subreddit=subreddit,
            signal_type="comment",
            created_utc=self._to_iso(int(item.get("created_utc", 0))),
            text=body,
            thread_id=thread_id,
            thread_depth=depth,
            score=self._as_int(item.get("score")),
            upvote_ratio=None,
            num_comments=None,
            permalink=self._abs_permalink(permalink),
            ivf_stage_hint=self._detect_stage_hint(text=body, flair=""),
            author_hash=self._author_hash(item.get("author")),
        )

    def _normalize_praw_submission(self, item: Any, subreddit: str) -> RedditSignal:
        sid = str(getattr(item, "id", ""))
        title = str(getattr(item, "title", "")).strip()
        body = str(getattr(item, "selftext", "")).strip()
        text = " ".join(part for part in [title, body] if part).strip()
        flair = str(getattr(item, "link_flair_text", "") or "")
        permalink = str(getattr(item, "permalink", f"/r/{subreddit}/comments/{sid}"))
        created_epoch = int(getattr(item, "created_utc", 0))
        return RedditSignal(
            signal_id=self._signal_id(subreddit, "post", sid),
            source_subreddit=subreddit,
            signal_type="post",
            created_utc=self._to_iso(created_epoch),
            text=text,
            thread_id=sid,
            thread_depth=0,
            score=self._as_int(getattr(item, "score", None)),
            upvote_ratio=self._as_float(getattr(item, "upvote_ratio", None)),
            num_comments=self._as_int(getattr(item, "num_comments", None)),
            permalink=self._abs_permalink(permalink),
            ivf_stage_hint=self._detect_stage_hint(text=text, flair=flair),
            author_hash=self._author_hash(getattr(getattr(item, "author", None), "name", None)),
        )

    def _normalize_praw_comment(self, item: Any, subreddit: str) -> RedditSignal:
        cid = str(getattr(item, "id", ""))
        body = str(getattr(item, "body", "")).strip()
        parent_id = str(getattr(item, "parent_id", ""))
        link_id = str(getattr(item, "link_id", ""))
        thread_id = link_id.replace("t3_", "") if link_id else parent_id.replace("t3_", "")
        depth = 1 if parent_id.startswith("t1_") else 0
        permalink = str(getattr(item, "permalink", f"/r/{subreddit}/comments/{thread_id}/_/{cid}"))
        created_epoch = int(getattr(item, "created_utc", 0))
        return RedditSignal(
            signal_id=self._signal_id(subreddit, "comment", cid),
            source_subreddit=subreddit,
            signal_type="comment",
            created_utc=self._to_iso(created_epoch),
            text=body,
            thread_id=thread_id,
            thread_depth=depth,
            score=self._as_int(getattr(item, "score", None)),
            upvote_ratio=None,
            num_comments=None,
            permalink=self._abs_permalink(permalink),
            ivf_stage_hint=self._detect_stage_hint(text=body, flair=""),
            author_hash=self._author_hash(getattr(getattr(item, "author", None), "name", None)),
        )

    def _http_json(self, url: str) -> dict[str, Any]:
        request = Request(url, headers={"User-Agent": "problem-discovery-ivf/1.0"})
        with urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw)

    @staticmethod
    def _to_iso(epoch: int) -> str:
        return datetime.fromtimestamp(max(0, epoch), tz=timezone.utc).isoformat()

    @staticmethod
    def _signal_id(subreddit: str, signal_type: str, native_id: str) -> str:
        material = f"{subreddit}:{signal_type}:{native_id}"
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @staticmethod
    def _author_hash(author: Any) -> str:
        value = str(author or "[deleted]")
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _abs_permalink(permalink: str) -> str:
        if permalink.startswith("http://") or permalink.startswith("https://"):
            return permalink
        return f"{REDDIT_BASE_URL}{permalink}"

    @staticmethod
    def _as_int(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _as_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _detect_stage_hint(self, *, text: str, flair: str) -> str | None:
        haystack = f"{flair} {text}".lower()
        stage_keywords = {
            "diagnosis": ["diagnosis", "amh", "fsh", "hsg", "sa result", "workup"],
            "finance": ["insurance", "denied", "coverage", "pharmacy cost", "out of pocket", "oop"],
            "stims": ["stim", "gonal", "follistim", "menopur", "trigger shot", "injection"],
            "retrieval": ["retrieval", "egg count", "mature eggs", "anesthesia"],
            "fertilization": ["fertilized", "icsi", "blast", "embryo day", "pgta", "pgt-a"],
            "transfer": ["transfer", "frozen transfer", "fet", "lining", "progesterone"],
            "tww_beta": ["two week wait", "tww", "beta", "beta hell", "hpt"],
        }
        for stage, keywords in stage_keywords.items():
            if any(keyword in haystack for keyword in keywords):
                return stage
        return None
