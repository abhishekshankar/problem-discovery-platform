"""CLI: migrate, collect, extract, cluster, rank, brief, eval, ops (PRD)."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from pathlib import Path

from .briefs.generator import generate_brief_for_cluster
from .briefs.regen_stale import regen_stale_briefs
from .clustering.hygiene import flag_low_silhouette_clusters, run_cluster_hygiene
from .clustering.version_hygiene import flag_mixed_version_clusters
from .clustering.service import run_clustering_pipeline
from .collectors.arxiv import ArxivCollector
from .collectors.cms import CMSNewsCollector
from .collectors.fda import FDANewsCollector
from .collectors.federal_register import FederalRegisterCollector
from .collectors.github import GitHubIssuesCollector
from .collectors.google_trends import GoogleTrendsCollector
from .collectors.hackernews import HackerNewsCollector
from .collectors.nih_reporter import NIHReporterCollector
from .collectors.polymarket import PolymarketCollector
from .collectors.reddit import RedditCollector
from .collectors.sec_edgar import SECEdgarNewsCollector
from .collectors.service import run_collector
from .collectors.stackoverflow import StackOverflowCollector
from .collectors.tier2 import (
    AhrefsKeywordCollector,
    ListenNotesCollector,
    ProfoundCollector,
    SemrushDomainCollector,
    SimilarwebCollector,
    SparkToroCollector,
)
from .collectors.tier3 import (
    AppFollowCollector,
    CapterraCollector,
    G2Collector,
    IndeedCollector,
    ProductHuntCollector,
    UpworkCollector,
)
from .collectors.google_ads_transparency import GoogleAdsTransparencyCollector
from .collectors.meta_ad_library import MetaAdLibraryCollector
from .collectors.sec_filings import SECFilingsCollector
from .collectors.youtube import YouTubeDataCollector
from .collectors.youtube_comments import YouTubeCommentsCollector
from .evals.runner import (
    run_clusterer_eval,
    run_clusterer_eval_live,
    run_end_to_end_eval,
    run_end_to_end_eval_replay_from_db,
    run_extractor_eval,
    run_extractor_eval_stub,
)
from .extraction.pipeline import run_extraction_batch
from .extraction.promotion import (
    canary_promote_run_eval_and_maybe_advance,
    get_promotion_status,
    reset_rollout_to_env_only,
)
from .meta.exploration import mark_monthly_exploration_cluster
from .meta.prompt_addenda import propose_feedback_patterns
from .meta.rebalance import (
    confirm_throttle_proposal,
    list_pending_throttle_proposals,
    run_source_accept_rebalance,
)
from .migrate import apply_all
from .ops.collector_health import run_collector_health_check
from .ops.cost_alert import check_cost_baseline
from .ops.digest import send_daily_digest
from .ops.metrics import bump_review_metrics
from .ops.redact import redact_raw_signal
from .ops.scheduler import run_scheduler_daemon, run_scheduler_once
from .ops.stale_briefs import archive_stale_briefs
from .ranker.calibrate import run_weekly_calibration
from .ranker.service import select_surface_candidates
from .reprocessing import reprocess_raw_signals_from
from .settings import get_settings


def main() -> None:
    p = argparse.ArgumentParser(prog="signal-cli", description="Signal pipeline (PRD)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("migrate", help="Apply SQL migrations")

    c = sub.add_parser("collect-reddit", help="Run Reddit collector")
    c.add_argument("--subreddit", action="append", required=True, dest="subreddits")

    sub.add_parser("collect-hn", help="Run Hacker News collector")
    sub.add_parser("collect-fedreg", help="Run Federal Register RSS collector")
    g = sub.add_parser("collect-github", help="Run GitHub issue search collector")
    g.add_argument("--query", default="is:issue is:open", help="GitHub search query")
    sub.add_parser("collect-sec", help="Run SEC press RSS collector")
    sub.add_parser("collect-cms", help="Run CMS news RSS collector")

    sub.add_parser("collect-arxiv", help="Run arXiv API collector")
    sub.add_parser("collect-fda", help="Run FDA news RSS collector")
    so = sub.add_parser("collect-stackoverflow", help="Run Stack Overflow collector")
    so.add_argument("--tagged", default="python;postgresql", help="Semicolon-separated tags")
    yt = sub.add_parser("collect-youtube", help="Run YouTube Data API collector")
    yt.add_argument("--query", default="healthcare software problems")
    nih = sub.add_parser("collect-nih", help="Run NIH RePORTER collector")
    nih.add_argument("--text", default="cancer therapy", help="Text search criteria")
    sub.add_parser("collect-polymarket", help="Run Polymarket Gamma collector")
    sub.add_parser("collect-google-trends", help="Run Google Trends (requires pytrends)")

    ah = sub.add_parser("collect-ahrefs", help="Run Ahrefs Tier-2 collector (AHREFS_API_KEY)")
    ah.add_argument("--target", default="wikipedia.org")
    sm = sub.add_parser("collect-semrush", help="Run Semrush Tier-2 collector (SEMRUSH_API_KEY)")
    sm.add_argument("--domain", default="semrush.com")
    sw = sub.add_parser("collect-similarweb", help="Run Similarweb Tier-2 collector")
    sw.add_argument("--domain", default="similarweb.com")
    st = sub.add_parser("collect-sparktoro", help="Run SparkToro Tier-2 collector")
    st.add_argument("--query", default="founders")

    yc = sub.add_parser("collect-youtube-comments", help="YouTube commentThreads (YOUTUBE_DATA_API_KEY)")
    yc.add_argument("--video-id", action="append", dest="video_ids", required=True)
    yc.add_argument("--channel-id", action="append", dest="channel_ids")

    secf = sub.add_parser("collect-sec-filings", help="SEC EDGAR submissions JSON (SEC_EDGAR_USER_AGENT)")
    secf.add_argument("--cik", action="append", required=True, dest="ciks")

    meta = sub.add_parser("collect-meta-ads", help="Meta Ad Library (META_AD_LIBRARY_TOKEN)")
    meta.add_argument("--search-terms", default="software")
    meta.add_argument("--countries", default="US")

    gads = sub.add_parser("collect-google-ads-transparency", help="Google Ads Transparency JSON (no key)")
    gads.add_argument("--query", default="technology")

    ln = sub.add_parser("collect-listennotes", help="Listen Notes podcast search")
    ln.add_argument("--q", default="startup problems")

    pf = sub.add_parser("collect-profound", help="Profound vendor adapter (PROFOUND_API_* env)")

    cg2 = sub.add_parser("collect-g2", help="G2 / reviews via Apify (APIFY_TOKEN, --product-url)")
    cg2.add_argument("--product-url", required=True)
    cg2.add_argument("--actor", default=None)

    ccap = sub.add_parser("collect-capterra", help="Capterra via Apify")
    ccap.add_argument("--listing-url", required=True)
    ccap.add_argument("--actor", default=None)

    cup = sub.add_parser("collect-upwork", help="Upwork search via Apify")
    cup.add_argument("--search-url", required=True)
    cup.add_argument("--actor", default=None)

    cin = sub.add_parser("collect-indeed", help="Indeed jobs via Apify")
    cin.add_argument("--jobs-url", required=True)
    cin.add_argument("--actor", default=None)

    caf = sub.add_parser("collect-appfollow", help="AppFollow reviews (APPFOLLOW_TOKEN)")
    caf.add_argument("--store-id", default="284882215")

    cph = sub.add_parser("collect-producthunt", help="Product Hunt GraphQL (PRODUCTHUNT_TOKEN)")

    sch = sub.add_parser("scheduler", help="APScheduler foreground daemon (PRD ops cadence)")
    sch.add_argument("--once", action="store_true", help="Idempotent once-pass (for k8s CronJob)")

    rdx = sub.add_parser("redact", help="GDPR redact raw signal — delete derived rows, null payload (PRD §17.2)")
    rdx.add_argument("--source", required=True, dest="source_name")
    rdx.add_argument("--external-id", required=True, dest="external_id")

    e = sub.add_parser("extract", help="Run extraction batch (sync Sonnet, or --batch for Message Batches)")
    e.add_argument("--limit", type=int, default=50)
    e.add_argument(
        "--batch",
        action="store_true",
        help="Use Anthropic Message Batches API for Sonnet extraction (discount; may take minutes–hours)",
    )
    e.add_argument(
        "--max-wait",
        type=float,
        default=7200.0,
        help="Max seconds to poll each batch (default 7200)",
    )

    sub.add_parser("cluster", help="Run BERTopic + incremental clustering")
    sub.add_parser("cluster-hygiene", help="Merge similar clusters + archive stale")
    sub.add_parser("cluster-flag-silhouette", help="Flag large clusters for split review")
    sub.add_parser("cluster-version-hygiene", help="Mark clusters mixed vs clean extractor versions (PRD §14.4)")

    sub.add_parser("rank", help="Print surface candidates")

    surf = sub.add_parser("surface", help="Generate briefs for ranker candidates (up to cap)")
    surf.add_argument("--limit", type=int, default=5)

    b = sub.add_parser("brief", help="Generate brief for cluster UUID")
    b.add_argument("cluster_id")

    ev = sub.add_parser("eval-extractor-stub", help="Register null eval run")
    ev.add_argument("--jsonl", type=Path, default=None)

    ev2 = sub.add_parser("eval-extractor", help="Run Set A extractor eval (PRD §13)")
    ev2.add_argument("--jsonl", type=Path, default=None)
    ev2.add_argument("--target-version", default="extractor")
    ev2.add_argument("--week2-gate", action="store_true", help="Use F1 >= 0.70 threshold")

    ev3 = sub.add_parser("eval-clusterer", help="Run Set B clusterer ARI eval (static JSONL predictions)")
    ev3.add_argument("--jsonl", type=Path, default=None)
    ev3.add_argument("--week4-gate", action="store_true", help="Use ARI >= 0.55")

    ev3l = sub.add_parser(
        "eval-clusterer-live",
        help="Set B with KMeans on sentence-transformer embeddings (honest predicted labels)",
    )
    ev3l.add_argument("--jsonl", type=Path, default=None)
    ev3l.add_argument("--week4-gate", action="store_true", help="Use ARI >= 0.55")
    ev3l.add_argument("--random-state", type=int, default=42)

    ev4 = sub.add_parser(
        "eval-end-to-end",
        help="Set C: static JSONL gold vs predicted_decision (default), or --replay-from-db",
    )
    ev4.add_argument("--jsonl", type=Path, default=None)
    ev4.add_argument(
        "--replay-from-db",
        action="store_true",
        help="Predict ranker surface eligibility from live DB vs gold accept/reject-ish labels",
    )

    sub.add_parser("calibrate", help="Weekly throughput calibration (PRD §15.2)")

    rp = sub.add_parser("reprocess", help="Reprocess raw signals from date (PRD §14.3)")
    rp.add_argument("--from-date", required=True, help="ISO date YYYY-MM-DD")
    rp.add_argument("--limit", type=int, default=5000)
    rp.add_argument("--source-label", default="reddit")
    rp.add_argument(
        "--no-cluster",
        action="store_true",
        help="Skip run_clustering_pipeline after re-extraction",
    )
    rp.add_argument(
        "--report-dir",
        type=Path,
        default=None,
        help="Write reprocess_cluster_diff.json and .md under this directory",
    )

    sub.add_parser("collector-health", help="Collector volume + failure check (PRD §7.6)")
    sub.add_parser("digest", help="Send daily digest email (PRD §12.3)")
    ar = sub.add_parser("archive-stale-briefs", help="Archive unreviewed briefs (PRD §15.3)")
    ar.add_argument("--days", type=int, default=14)
    rsb = sub.add_parser(
        "regen-stale-briefs",
        help="Regenerate briefs when membership grew ≥20% since last brief (PRD §11.1)",
    )
    rsb.add_argument("--threshold", type=float, default=0.20, help="Fraction growth vs members-at-brief (default 0.2)")
    rsb.add_argument("--limit", type=int, default=20, help="Max clusters to process")

    sub.add_parser("source-rebalance", help="Update accept_rate_rolling + propose throttles (PRD §16.2)")
    tp = sub.add_parser("list-throttle-proposals", help="Pending source throttle proposals")
    ct = sub.add_parser("confirm-throttle", help="Confirm or reject a throttle proposal (audit in DB)")
    ct.add_argument("--proposal-id", required=True, help="UUID from list-throttle-proposals")
    ct.add_argument(
        "--action",
        required=True,
        choices=("throttle", "disable", "reject"),
        help="Apply to sources.status or reject proposal",
    )
    ct.add_argument("--by", default="cli", help="Operator id for audit (confirmed_by)")
    sub.add_parser("propose-patterns", help="Draft feedback_patterns from rejections (PRD §16.1)")
    sub.add_parser("exploration-cluster", help="Mark one exploration cluster (PRD §16.4)")

    cc = sub.add_parser("cost-check", help="Alert if LLM spend over baseline (PRD §21)")
    cc.add_argument("--llm-usd", type=float, required=True, help="Current month LLM spend")

    cp = sub.add_parser("canary-promote", help="Extractor canary rollout (PRD §14.2)")
    cp_sub = cp.add_subparsers(dest="canary_cmd", required=True)
    cp_sub.add_parser("status", help="Show DB rollout fraction and last eval")
    cpe = cp_sub.add_parser("eval-advance", help="Run Set A eval; on pass advance 10%→50%→100%")
    cpe.add_argument("--jsonl", type=Path, default=None)
    cpe.add_argument("--week2-gate", action="store_true", help="Use F1 >= 0.70")
    cp_sub.add_parser("reset", help="Set DB rollout to 0 (use env SIGNAL_CANARY_FRACTION only)")

    args = p.parse_args()

    if args.cmd == "migrate":
        apply_all()
        return

    if args.cmd == "collect-reddit":
        s = get_settings()
        col = RedditCollector(
            subreddits=args.subreddits,
            praw_client_id=s.reddit_client_id,
            praw_client_secret=s.reddit_client_secret,
            praw_user_agent=s.reddit_user_agent,
        )
        print(run_collector(col, settings=s))
        return

    if args.cmd == "collect-hn":
        print(run_collector(HackerNewsCollector(), settings=get_settings()))
        return

    if args.cmd == "collect-fedreg":
        print(run_collector(FederalRegisterCollector(), settings=get_settings()))
        return

    if args.cmd == "collect-github":
        s = get_settings()
        token = __import__("os").environ.get("GITHUB_TOKEN")
        print(run_collector(GitHubIssuesCollector(query=args.query, token=token), settings=s))
        return

    if args.cmd == "collect-sec":
        print(run_collector(SECEdgarNewsCollector(), settings=get_settings()))
        return

    if args.cmd == "collect-cms":
        print(run_collector(CMSNewsCollector(), settings=get_settings()))
        return

    if args.cmd == "collect-arxiv":
        print(run_collector(ArxivCollector(), settings=get_settings()))
        return

    if args.cmd == "collect-fda":
        print(run_collector(FDANewsCollector(), settings=get_settings()))
        return

    if args.cmd == "collect-stackoverflow":
        print(run_collector(StackOverflowCollector(tagged=args.tagged), settings=get_settings()))
        return

    if args.cmd == "collect-youtube":
        s = get_settings()
        print(run_collector(YouTubeDataCollector(api_key=s.youtube_data_api_key, query=args.query), settings=s))
        return

    if args.cmd == "collect-nih":
        print(run_collector(NIHReporterCollector(text_criteria=args.text), settings=get_settings()))
        return

    if args.cmd == "collect-polymarket":
        print(run_collector(PolymarketCollector(), settings=get_settings()))
        return

    if args.cmd == "collect-google-trends":
        print(run_collector(GoogleTrendsCollector(), settings=get_settings()))
        return

    if args.cmd == "collect-ahrefs":
        print(run_collector(AhrefsKeywordCollector(target=args.target), settings=get_settings()))
        return

    if args.cmd == "collect-semrush":
        print(run_collector(SemrushDomainCollector(domain=args.domain), settings=get_settings()))
        return

    if args.cmd == "collect-similarweb":
        print(run_collector(SimilarwebCollector(domain=args.domain), settings=get_settings()))
        return

    if args.cmd == "collect-sparktoro":
        print(run_collector(SparkToroCollector(query=args.query), settings=get_settings()))
        return

    if args.cmd == "collect-youtube-comments":
        s = get_settings()
        print(
            run_collector(
                YouTubeCommentsCollector(
                    api_key=s.youtube_data_api_key,
                    video_ids=list(args.video_ids or []),
                    channel_ids=list(getattr(args, "channel_ids", None) or []),
                ),
                settings=s,
            )
        )
        return

    if args.cmd == "collect-sec-filings":
        s = get_settings()
        print(
            run_collector(
                SECFilingsCollector(ciks=list(args.ciks or []), user_agent=s.sec_edgar_user_agent),
                settings=s,
            )
        )
        return

    if args.cmd == "collect-meta-ads":
        s = get_settings()
        print(
            run_collector(
                MetaAdLibraryCollector(
                    access_token=s.meta_ad_library_token,
                    search_terms=args.search_terms,
                    ad_reached_countries=args.countries,
                ),
                settings=s,
            )
        )
        return

    if args.cmd == "collect-google-ads-transparency":
        s = get_settings()
        print(
            run_collector(
                GoogleAdsTransparencyCollector(
                    search_query=args.query,
                    endpoint=s.google_ads_transparency_endpoint,
                ),
                settings=s,
            )
        )
        return

    if args.cmd == "collect-listennotes":
        s = get_settings()
        print(run_collector(ListenNotesCollector(api_key=s.listennotes_api_key, q=args.q), settings=s))
        return

    if args.cmd == "collect-profound":
        s = get_settings()
        print(
            run_collector(
                ProfoundCollector(api_key=s.profound_api_key, base_url=s.profound_api_base_url),
                settings=s,
            )
        )
        return

    if args.cmd == "collect-g2":
        s = get_settings()
        print(
            run_collector(
                G2Collector(product_url=args.product_url, token=s.apify_token, actor_id=args.actor),
                settings=s,
            )
        )
        return

    if args.cmd == "collect-capterra":
        s = get_settings()
        print(
            run_collector(
                CapterraCollector(listing_url=args.listing_url, token=s.apify_token, actor_id=args.actor),
                settings=s,
            )
        )
        return

    if args.cmd == "collect-upwork":
        s = get_settings()
        print(
            run_collector(
                UpworkCollector(search_url=args.search_url, token=s.apify_token, actor_id=args.actor),
                settings=s,
            )
        )
        return

    if args.cmd == "collect-indeed":
        s = get_settings()
        print(
            run_collector(
                IndeedCollector(jobs_url=args.jobs_url, token=s.apify_token, actor_id=args.actor),
                settings=s,
            )
        )
        return

    if args.cmd == "collect-appfollow":
        s = get_settings()
        print(
            run_collector(AppFollowCollector(token=s.appfollow_token, ext_store_id=args.store_id), settings=s)
        )
        return

    if args.cmd == "collect-producthunt":
        s = get_settings()
        print(run_collector(ProductHuntCollector(token=s.producthunt_token), settings=s))
        return

    if args.cmd == "scheduler":
        if args.once:
            print(run_scheduler_once(settings=get_settings()))
        else:
            run_scheduler_daemon(settings=get_settings())
        return

    if args.cmd == "redact":
        print(
            redact_raw_signal(
                source_name=args.source_name,
                external_id=args.external_id,
                settings=get_settings(),
            )
        )
        return

    if args.cmd == "extract":
        print(
            run_extraction_batch(
                limit=args.limit,
                use_message_batch=bool(getattr(args, "batch", False)),
                batch_max_wait_sec=float(getattr(args, "max_wait", 7200.0)),
            )
        )
        return

    if args.cmd == "cluster":
        print(run_clustering_pipeline())
        return

    if args.cmd == "cluster-hygiene":
        print(run_cluster_hygiene())
        return

    if args.cmd == "cluster-flag-silhouette":
        print(flag_low_silhouette_clusters())
        return

    if args.cmd == "cluster-version-hygiene":
        print(flag_mixed_version_clusters())
        return

    if args.cmd == "rank":
        print(select_surface_candidates(limit=10))
        return

    if args.cmd == "surface":
        lim = getattr(args, "limit", 5)
        out = []
        for row in select_surface_candidates(limit=lim):
            cid = str(row["id"])
            out.append(generate_brief_for_cluster(cid))
        bump_review_metrics(briefs_surfaced=len(out))
        print({"surfaced": len(out), "briefs": out})
        return

    if args.cmd == "brief":
        print(generate_brief_for_cluster(args.cluster_id))
        return

    if args.cmd == "eval-extractor-stub":
        print(run_extractor_eval_stub(args.jsonl))
        return

    if args.cmd == "eval-extractor":
        print(
            run_extractor_eval(
                args.jsonl,
                target_version=args.target_version,
                week2_gate=args.week2_gate,
            )
        )
        return

    if args.cmd == "eval-clusterer":
        print(run_clusterer_eval(args.jsonl, week4_gate=args.week4_gate))
        return

    if args.cmd == "eval-clusterer-live":
        print(
            run_clusterer_eval_live(
                args.jsonl,
                week4_gate=args.week4_gate,
                random_state=args.random_state,
            )
        )
        return

    if args.cmd == "eval-end-to-end":
        if getattr(args, "replay_from_db", False):
            print(run_end_to_end_eval_replay_from_db(args.jsonl))
        else:
            print(run_end_to_end_eval(args.jsonl))
        return

    if args.cmd == "calibrate":
        print(run_weekly_calibration())
        return

    if args.cmd == "reprocess":
        d = date.fromisoformat(args.from_date)
        print(
            reprocess_raw_signals_from(
                datetime(d.year, d.month, d.day, tzinfo=timezone.utc),
                extract_limit=args.limit,
                source_label=args.source_label,
                run_clustering_after=not getattr(args, "no_cluster", False),
                report_dir=getattr(args, "report_dir", None),
            )
        )
        return

    if args.cmd == "collector-health":
        print(run_collector_health_check())
        return

    if args.cmd == "digest":
        print(send_daily_digest())
        return

    if args.cmd == "archive-stale-briefs":
        print({"archived": archive_stale_briefs(days=args.days)})
        return

    if args.cmd == "regen-stale-briefs":
        print(
            regen_stale_briefs(
                growth_threshold=args.threshold,
                limit=args.limit,
                settings=get_settings(),
            )
        )
        return

    if args.cmd == "source-rebalance":
        print(run_source_accept_rebalance())
        return

    if args.cmd == "list-throttle-proposals":
        print({"pending": list_pending_throttle_proposals()})
        return

    if args.cmd == "confirm-throttle":
        print(
            confirm_throttle_proposal(
                proposal_id=args.proposal_id,
                action=args.action,
                confirmed_by=args.by,
            )
        )
        return

    if args.cmd == "propose-patterns":
        print(propose_feedback_patterns())
        return

    if args.cmd == "exploration-cluster":
        print(mark_monthly_exploration_cluster())
        return

    if args.cmd == "cost-check":
        print(check_cost_baseline(current_month_llm_usd=args.llm_usd))
        return

    if args.cmd == "canary-promote":
        if args.canary_cmd == "status":
            print(get_promotion_status())
            return
        if args.canary_cmd == "reset":
            reset_rollout_to_env_only()
            print({"reset": True})
            return
        if args.canary_cmd == "eval-advance":
            print(
                canary_promote_run_eval_and_maybe_advance(
                    jsonl_path=args.jsonl,
                    week2_gate=args.week2_gate,
                )
            )
            return

    p.error("unknown command")


if __name__ == "__main__":
    main()
