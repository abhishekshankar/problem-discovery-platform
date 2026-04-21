"""Environment-driven settings for Postgres, object storage (R2/S3), and LLM APIs."""

from __future__ import annotations

from dataclasses import dataclass

from ..config import ENV

_ENV = ENV


def _get(key: str, default: str | None = None) -> str | None:
    return _ENV.get(key, default)


@dataclass(frozen=True)
class SignalSettings:
    database_url: str | None = _get("DATABASE_URL")
    # S3-compatible (Cloudflare R2, AWS S3, MinIO)
    s3_endpoint_url: str | None = _get("S3_ENDPOINT_URL")  # e.g. https://<account>.r2.cloudflarestorage.com
    s3_region: str = _get("AWS_REGION") or _get("S3_REGION") or "auto"
    s3_access_key_id: str | None = _get("AWS_ACCESS_KEY_ID") or _get("S3_ACCESS_KEY_ID")
    s3_secret_access_key: str | None = _get("AWS_SECRET_ACCESS_KEY") or _get("S3_SECRET_ACCESS_KEY")
    s3_bucket_raw: str = _get("S3_BUCKET_RAW") or "signal-raw-archive"
    s3_addressing_style: str = _get("S3_ADDRESSING_STYLE") or "path"  # path | virtual
    # If set, write gzip JSONL here instead of S3 (dev)
    archive_local_dir: str | None = _get("ARCHIVE_LOCAL_DIR")
    # Anthropic
    anthropic_api_key: str | None = _get("ANTHROPIC_API_KEY")
    anthropic_model_extract: str = _get("ANTHROPIC_MODEL_EXTRACT") or "claude-sonnet-4-20250514"
    anthropic_model_brief: str = _get("ANTHROPIC_MODEL_BRIEF") or "claude-opus-4-20250514"
    anthropic_model_haiku: str = _get("ANTHROPIC_MODEL_HAIKU") or "claude-3-5-haiku-20241022"
    # Haiku fast gate before Sonnet full extraction (PRD week 2)
    extraction_haiku_gate: bool = (_get("SIGNAL_EXTRACTION_HAIKU_GATE") or "1").lower() in ("1", "true", "yes")
    # Anthropic Message Batches (async discount) — submit via CLI `signal-cli extract-batch`
    anthropic_use_batch_api: bool = (_get("SIGNAL_ANTHROPIC_BATCH") or "").lower() in ("1", "true", "yes")
    # Fine-tuned Pass-2 classifier dir (distilBERT). Empty → keyword heuristic.
    classifier_model_path: str | None = _get("SIGNAL_CLASSIFIER_MODEL_PATH")
    # Canary slice 0..1 for candidate prompt/version (PRD §14.2)
    extraction_canary_fraction: float = float(_get("SIGNAL_CANARY_FRACTION") or "0")
    candidate_prompt_id: str | None = _get("SIGNAL_CANDIDATE_PROMPT_ID")
    # Dev: skip LLM and use stub extraction
    extraction_use_stub: bool = (_get("SIGNAL_EXTRACTION_STUB") or "").lower() in ("1", "true", "yes")
    # Embeddings (sentence-transformers local by default)
    embedding_model_id: str = _get("EMBEDDING_MODEL_ID") or "intfloat/e5-large-v2"
    embedding_device: str = _get("EMBEDDING_DEVICE") or "cpu"
    # Reddit / collectors
    reddit_client_id: str | None = _get("REDDIT_CLIENT_ID")
    reddit_client_secret: str | None = _get("REDDIT_CLIENT_SECRET")
    reddit_user_agent: str = _get("REDDIT_USER_AGENT") or "signal-problem-discovery/0.1"
    # Alerts (optional)
    slack_webhook_url: str | None = _get("SLACK_WEBHOOK_URL")
    alert_email_from: str | None = _get("SIGNAL_ALERT_EMAIL_FROM")
    alert_email_to: str | None = _get("SIGNAL_ALERT_EMAIL_TO")
    smtp_host: str | None = _get("SMTP_HOST")
    smtp_port: int = int(_get("SMTP_PORT") or "587")
    smtp_user: str | None = _get("SMTP_USER")
    smtp_password: str | None = _get("SMTP_PASSWORD")
    # Daily digest (PRD §12.3)
    digest_email_to: str | None = _get("SIGNAL_DIGEST_EMAIL_TO")
    # Tier 1 / optional APIs
    youtube_data_api_key: str | None = _get("YOUTUBE_DATA_API_KEY")
    meta_ad_library_token: str | None = _get("META_AD_LIBRARY_TOKEN")
    google_ads_transparency_endpoint: str | None = _get("GOOGLE_ADS_TRANSPARENCY_ENDPOINT")
    sec_edgar_user_agent: str = _get("SEC_EDGAR_USER_AGENT") or "SignalProblemDiscovery contact@example.com"
    # Tier 2+
    listennotes_api_key: str | None = _get("LISTENNOTES_API_KEY")
    profound_api_key: str | None = _get("PROFOUND_API_KEY")
    profound_api_base_url: str | None = _get("PROFOUND_API_BASE_URL")
    apify_token: str | None = _get("APIFY_TOKEN")
    apify_actor_g2: str | None = _get("APIFY_ACTOR_G2")
    apify_actor_capterra: str | None = _get("APIFY_ACTOR_CAPTERRA")
    apify_actor_upwork: str | None = _get("APIFY_ACTOR_UPWORK")
    apify_actor_indeed: str | None = _get("APIFY_ACTOR_INDEED")
    appfollow_token: str | None = _get("APPFOLLOW_TOKEN")
    producthunt_token: str | None = _get("PRODUCTHUNT_TOKEN")
    # GDPR pseudonymization (PRD §17.2)
    signal_pseudonym_salt: str | None = _get("SIGNAL_PSEUDONYM_SALT")


def get_settings() -> SignalSettings:
    return SignalSettings()
