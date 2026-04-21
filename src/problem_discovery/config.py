from dataclasses import dataclass, field
from pathlib import Path
import os

from .env import load_env

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
DB_PATH = OUTPUT_DIR / "problem_discovery.sqlite"
ENV_PATH = ROOT / ".env"
# Package-local .env (src/problem_discovery/.env) as fallback; repo-root .env overrides; os.environ wins.
PACKAGE_ENV_PATH = Path(__file__).resolve().parent / ".env"

ENV = {**load_env(PACKAGE_ENV_PATH), **load_env(ENV_PATH), **os.environ}


def get_env(key: str, default: str | None = None) -> str | None:
    return ENV.get(key, default)


@dataclass(frozen=True)
class RunConfig:
    niche: str
    phase: str  # "1", "2", "3", "4", "5", or "all"
    founder_profile_path: Path | None = None
    constraints_path: Path | None = None
    max_signals: int = 100
    max_clusters: int = 25
    seed: int = 42


@dataclass(frozen=True)
class SourceConfig:
    g2_api_key: str | None = get_env("G2_API_KEY")
    g2_base_url: str = get_env("G2_BASE_URL", "https://data.g2.com") or "https://data.g2.com"
    g2_auth_scheme: str = get_env("G2_AUTH_SCHEME", "token") or "token"
    g2_mode: str = get_env("G2_MODE", "syndication") or "syndication"
    g2_product_ids: list[str] = field(
        default_factory=lambda: [
            item.strip()
            for item in (get_env("G2_PRODUCT_IDS", "") or "").split(",")
            if item.strip()
        ]
    )
    hasdata_api_key: str | None = get_env("HASDATA_API_KEY")
    hasdata_base_url: str = get_env("HASDATA_BASE_URL", "https://api.hasdata.com") or "https://api.hasdata.com"
    indeed_location: str = get_env("INDEED_LOCATION", "United States") or "United States"
    indeed_country: str = get_env("INDEED_COUNTRY", "us") or "us"
    indeed_domain: str = get_env("INDEED_DOMAIN", "www.indeed.com") or "www.indeed.com"
    indeed_sort: str = get_env("INDEED_SORT", "date") or "date"
    reddit_client_id: str | None = get_env("REDDIT_CLIENT_ID")
    reddit_client_secret: str | None = get_env("REDDIT_CLIENT_SECRET")
    reddit_user_agent: str = get_env("REDDIT_USER_AGENT", "problem-discovery-ivf/1.0") or "problem-discovery-ivf/1.0"
