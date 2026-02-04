# Problem Discovery Platform

A multi-agent system that discovers validated B2B problems by combining signal mining, clustering, adversarial review, and scoring.

## What’s in this repo
- Full multi-phase pipeline (Phases 0–5)
- Devvit sidecar for Reddit signals
- Ingest server for Devvit webhooks
- SQLite persistence and JSON/HTML report output

## Quick start
```bash
# From repo root
python3 run.py --niche "Property Management" --phase all
```

## Devvit (Reddit) ingestion
1. Start the ingest server:
```bash
PYTHONPATH=src python3 -m problem_discovery.ingest_server --signal-path data/devvit_signals.jsonl --port 8090
```
2. Set `WEBHOOK_URL` in `devvit/src/main.ts` to your public tunnel URL (ngrok).
3. Deploy your Devvit app and create a post/comment in the playtest subreddit.
4. Run the pipeline with Devvit signals:
```bash
python3 run.py --niche "Property Management" --phase all --use-devvit --devvit-signal-path data/devvit_signals.jsonl
```

## Configuration
Create a `.env` file at repo root (see `.env.example`).

## Outputs
- JSON: `output/run_<id>.json`
- HTML: `output/run_<id>.html`
- DB: `output/problem_discovery.sqlite`

## Notes
- If G2 is not configured, Agent B uses mock signals.
- If HasData is not configured, Agent C uses mock signals.

