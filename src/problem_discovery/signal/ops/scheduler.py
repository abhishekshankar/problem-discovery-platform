"""APScheduler daemon for collectors + ops jobs (PRD)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

from apscheduler.schedulers.background import BackgroundScheduler

from ..settings import SignalSettings, get_settings
from ..briefs.regen_stale import regen_stale_briefs
from ..clustering.hygiene import run_cluster_hygiene
from ..clustering.service import run_clustering_pipeline
from ..clustering.version_hygiene import flag_mixed_version_clusters
from ..extraction.pipeline import run_extraction_batch
from ..meta.exploration import mark_monthly_exploration_cluster
from ..meta.rebalance import run_source_accept_rebalance
from ..meta.prompt_addenda import propose_feedback_patterns
from ..ops.collector_health import run_collector_health_check
from ..ops.digest import send_daily_digest
from ..ops.stale_briefs import archive_stale_briefs
from ..ranker.calibrate import run_weekly_calibration
from ..ranker.service import update_baseline_sigma, refresh_cluster_stats


STATE_DIR = Path(os.environ.get("SIGNAL_SCHEDULER_STATE_DIR") or "/tmp/signal_scheduler_state")


def _job_lock_path(name: str) -> Path:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    return STATE_DIR / f"last_ok_{name}.ts"


def run_job_if_due(
    name: str,
    interval_sec: int,
    fn: Callable[..., Any],
    *args: Any,
    **kwargs: Any,
) -> dict[str, Any]:
    """Idempotent tick: run fn if interval_sec elapsed since last successful completion."""
    path = _job_lock_path(name)
    now = int(__import__("time").time())
    last = 0
    if path.exists():
        try:
            last = int(path.read_text(encoding="utf-8").strip() or "0")
        except ValueError:
            last = 0
    if now - last < interval_sec:
        return {"job": name, "skipped": True, "next_in_sec": interval_sec - (now - last)}
    out = fn(*args, **kwargs)
    path.write_text(str(now), encoding="utf-8")
    return {"job": name, "ran": True, "result": out}


def register_prd_jobs(sched: BackgroundScheduler, s: SignalSettings) -> None:
    """Hard-coded PRD cadences (4h / daily / weekly)."""
    # 4-hourly
    sched.add_job(lambda: run_extraction_batch(limit=100), "cron", hour="*/4", minute=5, id="extract_batch")
    sched.add_job(lambda: run_clustering_pipeline(), "cron", hour="*/4", minute=20, id="cluster")
    sched.add_job(lambda: refresh_cluster_stats(s) or update_baseline_sigma(s), "cron", hour="*/4", minute=35, id="rank_stats")

    # Daily
    sched.add_job(lambda: archive_stale_briefs(days=14, settings=s), "cron", hour=2, minute=0, id="archive_stale_briefs")
    sched.add_job(lambda: regen_stale_briefs(limit=10, settings=s), "cron", hour=3, minute=0, id="regen_stale_briefs")
    sched.add_job(lambda: send_daily_digest(), "cron", hour=8, minute=0, id="digest")
    sched.add_job(lambda: run_collector_health_check(), "cron", hour=9, minute=0, id="collector_health")
    sched.add_job(lambda: run_source_accept_rebalance(), "cron", hour=10, minute=0, id="source_rebalance")
    sched.add_job(lambda: propose_feedback_patterns(), "cron", hour=11, minute=0, id="propose_patterns")
    sched.add_job(lambda: mark_monthly_exploration_cluster(), "cron", hour=6, minute=30, id="exploration_cluster")

    # Weekly
    sched.add_job(lambda: run_cluster_hygiene(), "cron", day_of_week="sun", hour=4, minute=0, id="cluster_hygiene")
    sched.add_job(lambda: flag_mixed_version_clusters(s), "cron", day_of_week="sun", hour=5, minute=0, id="version_hygiene")
    sched.add_job(lambda: run_weekly_calibration(), "cron", day_of_week="mon", hour=5, minute=30, id="weekly_calibrate")


def register_collector_cron_from_db(sched: BackgroundScheduler, s: SignalSettings) -> None:
    """Invoke run_collector for each active collector row (module path in config_json optional)."""
    if not s.database_url:
        return
    # Placeholder: DB-driven dynamic import is operator-specific; PRD jobs above cover core pipeline.
    _ = sched


def run_scheduler_daemon(settings: SignalSettings | None = None) -> None:
    s = settings or get_settings()
    sched = BackgroundScheduler()
    register_prd_jobs(sched, s)
    register_collector_cron_from_db(sched, s)
    sched.start()
    try:
        import time

        while True:
            time.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        sched.shutdown()


def run_scheduler_once(settings: SignalSettings | None = None) -> dict[str, Any]:
    """Run tick: 4h bucket jobs if due (simple wall-clock modulo)."""
    s = settings or get_settings()
    results: dict[str, Any] = {}
    # 4h ≈ 14400 sec
    results["extract"] = run_job_if_due("extract", 14400, lambda: run_extraction_batch(limit=80))
    results["cluster"] = run_job_if_due("cluster", 14400, run_clustering_pipeline)
    results["archive_briefs"] = run_job_if_due("archive_briefs", 86400, lambda: archive_stale_briefs(settings=s))
    results["regen_briefs"] = run_job_if_due("regen_briefs", 86400, lambda: regen_stale_briefs(settings=s))
    results["version_hygiene"] = run_job_if_due("version_hygiene", 604800, lambda: flag_mixed_version_clusters(s))
    return results
