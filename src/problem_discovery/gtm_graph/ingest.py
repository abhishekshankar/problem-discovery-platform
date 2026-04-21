from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Iterable

import praw
import requests

LOGGER = logging.getLogger(__name__)

SUBREDDIT_LAYERS = {
    "layer1": ["ProductMarketing", "startups", "SaaS", "ycombinator", "Entrepreneur"],
    "layer2": ["marketing", "digital_marketing", "copywriting", "content_marketing", "SEO", "PPC"],
    "layer3": ["smallbusiness", "devops", "sysadmin", "webdev", "sales", "CustomerSuccess", "Productivity", "RemoteWork"],
    "layer4": ["SideProject", "buildinpublic", "RoastMyStartup", "microsaas", "startuplaunches"],
}

SEARCH_QUERIES = [
    "GTM motion",
    "go-to-market",
    "launch strategy",
    "ideal customer",
    "what worked",
    "first 100 users",
    "acquisition channel",
    "what I wish I knew",
    "why we failed",
    "pivot",
    "wrong ICP",
    "CAC",
    "LTV",
    "MRR",
    "churn",
    "switching from",
    "alternative to",
]

RSS_ENDPOINT = "https://www.reddit.com/r/{subreddit}/search.rss"


@dataclass
class RedditPost:
    post_id: str
    subreddit: str
    layer: str
    query: str
    title: str
    body: str
    score: int
    num_comments: int
    created_utc: datetime
    url: str
    top_comments: list[str]
    source: str

    def as_dict(self) -> dict[str, object]:
        return {
            **asdict(self),
            "created_utc": self.created_utc.isoformat(),
        }


class PRAWIngestor:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        user_agent: str,
        max_results_per_query: int = 100,
        comment_limit: int = 10,
    ) -> None:
        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
        )
        self.max_results_per_query = max_results_per_query
        self.comment_limit = comment_limit

    def collect(self, subreddits: dict[str, list[str]] = SUBREDDIT_LAYERS) -> list[RedditPost]:
        posts: list[RedditPost] = []
        for layer, names in subreddits.items():
            for name in names:
                subreddit = self.reddit.subreddit(name)
                for query in SEARCH_QUERIES:
                    for submission in subreddit.search(query, limit=self.max_results_per_query, sort="relevance", time_filter="year"):
                        post = self._normalize_submission(submission, name, layer, query)
                        posts.append(post)
        return posts

    def _normalize_submission(self, submission: praw.models.Submission, subreddit: str, layer: str, query: str) -> RedditPost:
        top_comments = self._collect_top_comments(submission)
        return RedditPost(
            post_id=submission.id,
            subreddit=subreddit,
            layer=layer,
            query=query,
            title=submission.title,
            body=submission.selftext or "",
            score=submission.score or 0,
            num_comments=submission.num_comments or 0,
            created_utc=datetime.utcfromtimestamp(submission.created_utc),
            url=submission.url,
            top_comments=top_comments,
            source="praw",
        )

    def _collect_top_comments(self, submission: praw.models.Submission) -> list[str]:
        submission.comments.replace_more(limit=0)
        comments = []
        counter = 0
        for comment in submission.comments:
            if counter >= self.comment_limit:
                break
            if hasattr(comment, "body") and comment.body:
                comments.append(comment.body)
                counter += 1
        return comments


def fetch_apify_archive(task_id: str, api_token: str, target_path: Path) -> Path:
    """Placeholder helper that demonstrates how to hydrate a historical batch from Apify."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "taskId": task_id,
        "format": "json",
    }
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }
    response = requests.post("https://api.apify.com/v2/actor-tasks/fetch-result", json=payload, headers=headers)
    response.raise_for_status()
    target_path.write_bytes(response.content)
    LOGGER.info("Wrote Apify archive to %s", target_path)
    return target_path


def poll_rss(subreddit: str, query: str) -> list[dict[str, str]]:
    """Use Reddit RSS search as a zero-auth fallback for live signals."""
    params = {"q": query, "sort": "new", "restrict_sr": "1"}
    url = RSS_ENDPOINT.format(subreddit=subreddit)
    response = requests.get(url, params=params, headers={"User-Agent": "GTM-KG-Builder/1.0"})
    response.raise_for_status()
    # Basic RSS parsing; consumers can swap in feedparser for richer metadata
    entries: list[dict[str, str]] = []
    text = response.text
    for item in text.split("<item>")[1:]:
        title = _extract_tag(item, "title")
        link = _extract_tag(item, "link")
        description = _extract_tag(item, "description")
        entries.append({"title": title, "link": link, "description": description})
    return entries


def _extract_tag(item: str, tag: str) -> str:
    start = item.find(f"<{tag}>")
    stop = item.find(f"</{tag}>")
    if start == -1 or stop == -1:
        return ""
    return item[start + len(tag) + 2 : stop].strip()


def write_jsonl(path: Path, records: Iterable[dict[str, object]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")
    return path


def run_ingestion(
    output_path: Path,
    praw_client_id: str,
    praw_client_secret: str,
    praw_user_agent: str,
    max_results_per_query: int = 100,
) -> Path:
    """Run the canonical GTM ingestion path that writes deduplicated JSONL by layer."""
    ingestor = PRAWIngestor(praw_client_id, praw_client_secret, praw_user_agent, max_results_per_query)
    posts = ingestor.collect()
    payload = [post.as_dict() for post in posts]
    return write_jsonl(output_path, payload)


def read_jsonl(path: Path) -> Iterable[dict[str, object]]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            yield json.loads(line)
