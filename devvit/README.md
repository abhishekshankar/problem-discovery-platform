# Devvit Sidecar

This folder holds a minimal Devvit app that captures subreddit content and
pushes signals into the Python pipeline via a webhook.

## How it fits
- Devvit runs inside Reddit and can read posts/comments in installed subreddits.
- It posts JSON to the ingestion endpoint in this repo.

## Ingest server
Start the receiver locally:

```bash
PYTHONPATH=src python3 -m problem_discovery.ingest_server
```

Optional custom path:

```bash
PYTHONPATH=src python3 -m problem_discovery.ingest_server --signal-path data/devvit_signals.jsonl
```

## Devvit config
Update `WEBHOOK_URL` in `src/main.ts` to point to your ingestion server.

## Payload format
```
{
  "id": "post_or_comment_id",
  "title": "post title",
  "body": "post body or comment text",
  "author": "username",
  "subreddit": "subreddit_name",
  "url": "https://reddit.com/...",
  "upvotes": 12,
  "comments": 4,
  "timestamp": "2026-02-03T18:00:00Z",
  "signal_type": "complaint"
}
```
