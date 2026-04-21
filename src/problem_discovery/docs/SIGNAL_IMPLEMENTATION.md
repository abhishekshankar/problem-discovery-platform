# Signal implementation map (PRD §19)

## Local quickstart

1. **Postgres + pgvector:** from repo root (parent of `src/`), run `docker compose up -d` using [`docker-compose.yml`](../../../docker-compose.yml) (user `signal`, password `signal`, db `signal`). Or `make db-up` from this package directory (looks for that compose file).
2. **Bootstrap:** from `src/problem_discovery/`, run `make setup` (venv + pip + copies [`.env.example`](../.env.example) → `.env` if missing), or `bash scripts/dev-local.sh` for the same plus optional Docker and `migrate`.
3. **Env:** edit `.env` with `DATABASE_URL` (defaults match Docker). You can also use repo-root `.env`; later keys override — see [`config.py`](../config.py).
4. **Migrate:** `make migrate` or `python run_signal.py migrate` (no `PYTHONPATH`; use [`run_signal.py`](../run_signal.py)).
5. **Streamlit:** `make streamlit` or `source .venv/bin/activate && streamlit run streamlit_app.py`
6. **CLI:** `python run_signal.py rank` (same entry as `python -m problem_discovery.signal` when run from `src/` with `PYTHONPATH` set).

This repo implements the Latent Demand Discovery pipeline end-to-end. After pulling changes, from `src/problem_discovery/`:

```bash
export DATABASE_URL=postgresql://...   # or rely on .env
python run_signal.py migrate
```

Apply new migrations when added (`005_gdpr.sql` — EU pseudonymization + redaction columns).

## CLI (`python -m problem_discovery.signal`)

| Command | PRD |
| --- | --- |
| `migrate` | Schema |
| `collect-reddit`, `collect-hn`, `collect-fedreg`, `collect-github`, `collect-sec`, `collect-cms` | §7.1 |
| `collect-arxiv`, `collect-fda`, `collect-stackoverflow`, `collect-youtube`, `collect-nih`, `collect-polymarket`, `collect-google-trends` | §7.1 |
| `collect-youtube-comments`, `collect-sec-filings`, `collect-meta-ads`, `collect-google-ads-transparency` | §7.1 (additional Tier 1) |
| `collect-ahrefs`, `collect-semrush`, `collect-similarweb`, `collect-sparktoro`, `collect-listennotes`, `collect-profound` | §7.2 |
| `collect-g2`, `collect-capterra`, `collect-upwork`, `collect-indeed`, `collect-appfollow`, `collect-producthunt` | §7.3 |
| `extract [--batch] [--max-wait]` | §8 |
| `cluster`, `cluster-hygiene`, `cluster-flag-silhouette`, `cluster-version-hygiene` | §9, §14.4 |
| `rank`, `surface`, `brief` | §10–11 |
| `regen-stale-briefs [--threshold] [--limit]` | §11.1 |
| `scheduler [--once]` | In-process APScheduler or idempotent once-pass |
| `redact --source NAME --external-id ID` | §17.2 |
| `eval-extractor`, `eval-clusterer`, `eval-clusterer-live`, `eval-end-to-end [--replay-from-db]` | §13 |
| `canary-promote status|eval-advance|reset` | §14.2 |
| `calibrate` | §15.2 |
| `reprocess [--report-dir DIR] [--no-cluster]` | §14.3 |
| `collector-health`, `digest`, `archive-stale-briefs` | §7.6, §12.3, §15.3 |
| `source-rebalance`, `list-throttle-proposals`, `confirm-throttle` | §16.2 |
| `propose-patterns`, `exploration-cluster` | §16 |
| `cost-check` | §21 |

## Scheduler options

1. **APScheduler (in-process)** — `python -m problem_discovery.signal scheduler` runs PRD cadence in the foreground. Use for single VM / long-lived worker. Optional: `SIGNAL_SCHEDULER_STATE_DIR` for `--once` lock files.
2. **system cron** — Template: `scripts/crontab.txt`. Install: `bash scripts/install-cron.sh` (idempotent block between markers). Replace `REPO_PARENT` with the directory on `PYTHONPATH` that contains the `problem_discovery` package.
3. **GitHub Actions** — `.github/workflows/signal-cron.yml` matrix: 4-hourly (`extract`, `cluster`), daily (archive, regen, health, digest, rebalance, patterns, exploration, version-hygiene), weekly (`cluster-hygiene`, `calibrate`). Set repo secret `DATABASE_URL` (and LLM keys as needed).

**When to pick which:** use APScheduler when you already run a persistent app server on one host; use cron when you prefer OS-level scheduling and log files; use GitHub Actions when the repo is the source of truth and you have no always-on VM (note: cold starts + secret management).

## Eval sets

- `evals/extractor_v1.jsonl` — replace synthetic rows with **hand labels** before production gates (PRD §13.1).
- `evals/clusterer_v1.jsonl` — static `predicted_cluster_id` for `eval-clusterer`; use `eval-clusterer-live` for KMeans on embeddings.
- `evals/end_to_end_v1.jsonl` — static `decision` vs `predicted_decision`; or `eval-end-to-end --replay-from-db` for live ranker eligibility vs gold `accept`.

## Classifier training

```bash
pip install -r requirements-ml.txt
python scripts/train_distilbert_classifier.py --data evals/extractor_v1.jsonl --out models/problem_classifier
export SIGNAL_CLASSIFIER_MODEL_PATH=models/problem_classifier
```

## Environment highlights

| Variable | Purpose |
| --- | --- |
| `SIGNAL_PSEUDONYM_SALT` | HMAC salt for EU-source pseudonymization (§17.2) |
| `SEC_EDGAR_USER_AGENT` | SEC EDGAR identity string (`collect-sec-filings`) |
| `META_AD_LIBRARY_TOKEN` | Meta Marketing API token for Ad Library |
| `GOOGLE_ADS_TRANSPARENCY_ENDPOINT` | Optional override for transparency JSON base URL |
| `LISTENNOTES_API_KEY` | Listen Notes API |
| `PROFOUND_API_KEY`, `PROFOUND_API_BASE_URL` | Profound / AI-visibility vendor adapter |
| `APIFY_TOKEN`, `APIFY_ACTOR_*` | Apify actors for Tier 3 scrapers |
| `APPFOLLOW_TOKEN` | AppFollow API |
| `PRODUCTHUNT_TOKEN` | Product Hunt GraphQL |
| `SIGNAL_CLASSIFIER_MODEL_PATH` | Fine-tuned distilBERT |
| `SIGNAL_CANARY_FRACTION`, `SIGNAL_CANDIDATE_PROMPT_ID` | §14.2; DB `extractor_promotion_state` overrides rollout |
| `SIGNAL_EXTRACTION_HAIKU_GATE` | Haiku pre-check (default on) |
| `YOUTUBE_DATA_API_KEY` | YouTube search + comments collectors |
| `AHREFS_API_KEY` **or** `SEMRUSH_API_KEY` | §7.2 |
| `SIMILARWEB_API_KEY`, `SPARKTORO_API_KEY` | Tier 2 |
| `SMTP_*`, `SIGNAL_DIGEST_EMAIL_TO`, `SLACK_WEBHOOK_URL` | Ops |

See [PRIVACY.md](PRIVACY.md) for GDPR pseudonymization and `redact`.

## Human / ops (not automated)

- Run exit gates G2–G7 and record outcomes in `eval_runs` and your operator log.
- Structural review §16.3 and legal: see [LEGAL_REVIEW.md](LEGAL_REVIEW.md).

See [LEGAL_REVIEW.md](LEGAL_REVIEW.md) before scaling scrapers.
