"""Reddit collector via PRAW (PRD §7.1 Tier 1)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterator

from .prefilter_phrases import reddit_text_matches_phrases
from .protocol import Collector, RawRecord


class RedditCollector(Collector):
    source_name = "reddit"
    tier = 1
    version = "0.1.0"
    cadence_cron = "0 */4 * * *"

    def __init__(
        self,
        *,
        subreddits: list[str],
        praw_client_id: str | None,
        praw_client_secret: str | None,
        praw_user_agent: str,
        post_limit: int = 100,
        comment_limit: int = 200,
    ) -> None:
        self.subreddits = subreddits
        self.praw_client_id = praw_client_id
        self.praw_client_secret = praw_client_secret
        self.praw_user_agent = praw_user_agent
        self.post_limit = post_limit
        self.comment_limit = comment_limit

    def fetch(self, since: datetime | None, run_id: str) -> Iterator[RawRecord]:
        try:
            import praw  # type: ignore[import-untyped]
        except ImportError as e:
            raise RuntimeError("praw is required for RedditCollector") from e

        if not (self.praw_client_id and self.praw_client_secret):
            raise RuntimeError("REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET must be set for RedditCollector")

        reddit = praw.Reddit(
            client_id=self.praw_client_id,
            client_secret=self.praw_client_secret,
            user_agent=self.praw_user_agent,
        )

        for sub in self.subreddits:
            sr = reddit.subreddit(sub)
            for submission in sr.new(limit=self.post_limit):
                created = datetime.fromtimestamp(int(submission.created_utc), tz=timezone.utc)
                if since and created < since:
                    continue
                text = " ".join(
                    p for p in (submission.title, getattr(submission, "selftext", "") or "") if p
                ).strip()
                payload = {
                    "platform": "reddit",
                    "subreddit": sub,
                    "kind": "post",
                    "id": submission.id,
                    "created_utc": created.isoformat(),
                    "text": text,
                    "permalink": f"https://www.reddit.com{submission.permalink}",
                    "score": getattr(submission, "score", None),
                }
                ext = f"{sub}:post:{submission.id}"
                yield RawRecord(
                    external_id=ext,
                    source_timestamp=created,
                    url=payload["permalink"],
                    raw_payload=payload,
                    metadata={"subreddit": sub},
                )

            for comment in sr.comments(limit=self.comment_limit):
                created = datetime.fromtimestamp(int(comment.created_utc), tz=timezone.utc)
                if since and created < since:
                    continue
                body = str(getattr(comment, "body", "") or "").strip()
                if not body or body == "[deleted]":
                    continue
                permalink = f"https://www.reddit.com{comment.permalink}"
                payload = {
                    "platform": "reddit",
                    "subreddit": sub,
                    "kind": "comment",
                    "id": comment.id,
                    "created_utc": created.isoformat(),
                    "text": body,
                    "permalink": permalink,
                    "score": getattr(comment, "score", None),
                }
                ext = f"{sub}:comment:{comment.id}"
                yield RawRecord(
                    external_id=ext,
                    source_timestamp=created,
                    url=permalink,
                    raw_payload=payload,
                    metadata={"subreddit": sub},
                )

    def pre_filter(self, record: RawRecord) -> bool:
        if not super().pre_filter(record):
            return False
        text = str(record.raw_payload.get("text", ""))
        return reddit_text_matches_phrases(text)
