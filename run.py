#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from problem_discovery.config import OUTPUT_DIR, DB_PATH
from problem_discovery.pipeline import Pipeline
from problem_discovery.report import write_json, write_html


def main() -> None:
    parser = argparse.ArgumentParser(description="Problem Discovery MAS")
    parser.add_argument("--niche", default=None)
    parser.add_argument("--phase", default="all")
    parser.add_argument("--founder-profile", dest="founder_profile", default=None)
    parser.add_argument("--use-devvit", action="store_true")
    parser.add_argument("--devvit-signal-path", dest="devvit_signal_path", default=None)
    parser.add_argument("--ivf-phase1", action="store_true")
    parser.add_argument("--ivf-subreddits", default="IVF,infertility,TryingForABaby")
    parser.add_argument("--ivf-months-back", type=int, default=24)
    parser.add_argument("--ivf-max-records-per-subreddit", type=int, default=100000)
    parser.add_argument("--ivf-use-praw", action="store_true")
    parser.add_argument("--ivf-no-pushshift", action="store_true")
    args = parser.parse_args()
    if not args.ivf_phase1 and not args.niche:
        parser.error("--niche is required unless --ivf-phase1 is used")

    founder_path = Path(args.founder_profile) if args.founder_profile else None

    pipeline = Pipeline(DB_PATH)
    try:
        if args.ivf_phase1:
            subreddits = [item.strip() for item in args.ivf_subreddits.split(",") if item.strip()]
            payload = pipeline.run_ivf_phase1(
                subreddits=subreddits,
                months_back=args.ivf_months_back,
                max_records_per_subreddit=args.ivf_max_records_per_subreddit,
                use_pushshift=not args.ivf_no_pushshift,
                use_praw=args.ivf_use_praw,
            )
        else:
            devvit_path = Path(args.devvit_signal_path) if args.devvit_signal_path else None
            payload = pipeline.run(
                niche=args.niche,
                phase=args.phase,
                founder_profile_path=founder_path,
                use_devvit=args.use_devvit,
                devvit_signal_path=devvit_path,
            )
    finally:
        pipeline.close()

    json_path = write_json(OUTPUT_DIR, payload["run_id"], payload)
    html_path = write_html(OUTPUT_DIR, payload["run_id"], payload)

    print(f"Wrote {json_path}")
    print(f"Wrote {html_path}")


if __name__ == "__main__":
    main()
