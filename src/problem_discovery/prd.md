# Product Requirements Document
## Latent Demand Discovery System (working name: Signal)

**Version:** 1.0
**Date:** April 2026
**Status:** Build spec, pre-v0.1
**Owner:** [you]

---

## 1. Summary

A single-user agentic system that continuously mines public conversations, reviews, job markets, regulatory feeds, and behavioral signals across 40+ sources to surface validated latent-demand problems worth building businesses around. The system does the heavy lifting: collection, extraction, clustering, scoring, and synthesis. The human does the judgment: accepting clusters, running customer interviews, deciding what to build.

The system is not an idea generator. It is a problem-surfacing pipeline with an audit trail, designed around the reality that signal is cheap, taste is rare, and hallucination is the dominant production risk.

## 2. Problem statement

Founders hunting for product opportunities are constrained not by access to data but by the ability to process it. The public web leaks millions of signals per day about workflow friction, unmet demand, and workarounds. Existing tools (GummySearch, now shuttered; PainOnSocial; Exploding Topics; founder-targeted Reddit scrapers) capture one slice of this at a time, use LLM-heavy pipelines that hallucinate problems that weren't in the source, apply volume-based scoring that mistakes noise for signal, and produce outputs that require more manual review than they save.

A system that produces 20 "opportunities" per day that are 30% hallucinated and 50% stale is worse than no system. The goal is to produce 3-5 rigorously-grounded, triangulated problem clusters per week that the user reads, remembers, and acts on.

## 3. Non-goals

- Generating startup ideas. The system surfaces problems, not solutions.
- Simulating customer interviews. The system prepares for them; the human conducts them.
- Being a multi-user SaaS. v1 is single-user. Productization comes later, if ever.
- Beating established intent-data tools (6sense, Bombora) on coverage. We trade coverage for depth in chosen domains.
- Covering authenticated/private data sources. Public web only.
- Replacing the user's judgment with a score. No weighted rubric produces the accept/reject decision.

## 4. Target user

One person: the operator building the system. Characteristics:
- Has a specific domain wedge (fertility, BHI, health tech — the current hypothesis)
- Wants 3-5 curated problem clusters surfaced per week
- Will review briefs for ~15-30 minutes/day, 5 days/week
- Has engineering capacity to operate the system themselves
- Will expand to additional users only after the single-user version has produced at least one validated business hypothesis

## 5. Guiding principles

1. **Raw data is sacred. Everything else is derived and regeneratable.** If we lose derived data we rebuild it. If we lose raw data we're done.
2. **Evals gate every change.** Any change to extraction, clustering, or scoring must pass an evaluation against a labeled holdout set before shipping.
3. **LLMs for synthesis, classical NLP for extraction.** Tier 1 mass processing uses classical NLP for determinism, cost, and latency. LLMs are reserved for Tier 2 validation and Tier 3 synthesis.
4. **Triangulation over volume.** A signal appearing once across three independent sources beats a signal appearing fifty times in one source.
5. **Deviation from baseline, not raw volume.** Signals are statistical deviations from a 12-week rolling baseline. Volume is not signal.
6. **Verifiable grounding.** Every extracted problem must include a verbatim quote from the source. Every cluster brief must cite its member signals.
7. **No platform is load-bearing.** The system continues to produce value if any single source is shut off.
8. **Surfacing rate matches review capacity.** The ranker targets the human's actual throughput, not a theoretical maximum.

## 6. System architecture

### 6.1 High-level

Five layers, each with an explicit contract:

- **L1 — Collector fleet:** source-specific agents that pull raw data and write to immutable archive
- **L2 — Extraction pipeline:** classical NLP + versioned prompts that turn raw into structured problem records
- **L3 — Clustering & synthesis:** BERTopic + pgvector for grouping, Claude Opus for canonical statement generation
- **L4 — Evaluation & review:** SQL-based ranker, brief generation, single-user review UI
- **L5 — Meta-learning:** weekly prompt tuning, monthly source-allocation rebalancing, quarterly structural review (human-driven)

### 6.2 Storage tiers

**Tier A — Immutable raw archive**
- Cloudflare R2 or S3
- Path: `/raw/{source}/{YYYY}/{MM}/{DD}/{batch_id}.jsonl.gz`
- Every record: external_id, source, captured_at, source_timestamp, raw_payload, collector_version, scrape_run_id, payload_hash
- Write-once, append-only. Never edited, never deleted.
- Cost target: <$10/month at projected volumes

**Tier B — Operational database**
- Postgres 16 with pgvector extension
- All derived data: extracted_problems, clusters, cluster_briefs, decisions, extraction_runs, sources, collectors, feedback_patterns
- Every row has extractor_version / model_version columns
- Fully regeneratable from Tier A

**Tier C — Indexes and caches**
- pgvector HNSW indexes
- Materialized views for the ranker
- Ephemeral; rebuildable in minutes

### 6.3 Schema (Postgres)

```sql
CREATE TABLE sources (
  id SERIAL PRIMARY KEY,
  name VARCHAR(100) UNIQUE,
  tier INT,  -- 1 (official API) to 5 (manual)
  status VARCHAR(20),  -- active / throttled / disabled / broken
  cost_per_1k_calls NUMERIC,
  rate_limit_per_hour INT,
  last_success_at TIMESTAMP,
  breakage_count_30d INT,
  accept_rate_rolling NUMERIC,  -- fraction of derived problems that led to accepted clusters
  notes TEXT
);

CREATE TABLE collectors (
  id SERIAL PRIMARY KEY,
  source_id INT REFERENCES sources(id),
  name VARCHAR(100),
  version VARCHAR(20),
  config_json JSONB,
  cadence_cron VARCHAR(50),
  last_run_at TIMESTAMP,
  last_output_count INT,
  avg_signal_noise_ratio NUMERIC,
  status VARCHAR(20)
);

CREATE TABLE raw_signals_index (
  id BIGSERIAL PRIMARY KEY,
  external_id VARCHAR(200),
  source_id INT REFERENCES sources(id),
  archive_path TEXT,  -- pointer into R2
  captured_at TIMESTAMP,
  source_timestamp TIMESTAMP,
  url TEXT,
  UNIQUE(source_id, external_id)
);

CREATE TABLE extraction_runs (
  id UUID PRIMARY KEY,
  extractor_version VARCHAR(20),
  prompt_hash VARCHAR(64),
  model_identifier VARCHAR(50),
  started_at TIMESTAMP,
  completed_at TIMESTAMP,
  raw_records_processed INT,
  eval_scores_json JSONB,
  promoted BOOLEAN DEFAULT FALSE,
  promoted_at TIMESTAMP
);

CREATE TABLE extracted_problems (
  id BIGSERIAL PRIMARY KEY,
  raw_signal_id BIGINT REFERENCES raw_signals_index(id),
  extraction_run_id UUID REFERENCES extraction_runs(id),
  is_problem_signal BOOLEAN,
  problem_statement TEXT,
  exact_quote TEXT,  -- MUST be verbatim substring of raw_payload
  quote_verified BOOLEAN,  -- post-extraction check
  specificity_score NUMERIC,  -- 1-10
  wtp_level VARCHAR(20),  -- none / weak / strong / proven
  wtp_evidence TEXT,
  layer VARCHAR(20),  -- unformed / formed / frustrated / paying
  domain_tags TEXT[],
  buyer_hint TEXT,
  workaround_described TEXT,
  admiralty_source_reliability CHAR(1),  -- A-F
  admiralty_info_credibility INT,  -- 1-6
  embedding vector(1024),  -- E5-large-v2 or BGE-large
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE clustering_runs (
  id UUID PRIMARY KEY,
  algorithm VARCHAR(50),
  algorithm_version VARCHAR(20),
  parameters_json JSONB,
  extractor_version_filter VARCHAR(20),  -- only cluster problems from this version
  started_at TIMESTAMP,
  completed_at TIMESTAMP,
  cluster_count INT,
  noise_point_count INT,
  eval_scores_json JSONB,
  promoted BOOLEAN
);

CREATE TABLE clusters (
  id UUID PRIMARY KEY,
  clustering_run_id UUID REFERENCES clustering_runs(id),
  canonical_statement TEXT,
  c_tfidf_label TEXT,  -- BERTopic's automatic label
  first_seen_at TIMESTAMP,
  last_seen_at TIMESTAMP,
  member_count INT,
  layer_coverage VARCHAR(20)[],  -- which of the 4 layers have members
  source_diversity_count INT,  -- distinct sources represented
  growth_rate_14d NUMERIC,
  centroid_embedding vector(1024),
  status VARCHAR(20),  -- new / surfaced / accepted / rejected / snoozed / archived / watching
  deviation_from_baseline_sigma NUMERIC  -- std deviations from 12-week rolling baseline
);

CREATE TABLE cluster_members (
  cluster_id UUID REFERENCES clusters(id),
  extracted_problem_id BIGINT REFERENCES extracted_problems(id),
  similarity_score NUMERIC,
  added_at TIMESTAMP,
  PRIMARY KEY (cluster_id, extracted_problem_id)
);

CREATE TABLE cluster_briefs (
  id UUID PRIMARY KEY,
  cluster_id UUID REFERENCES clusters(id),
  generated_at TIMESTAMP,
  model_identifier VARCHAR(50),
  brief_markdown TEXT,
  interview_prompts_json JSONB,
  superseded_by UUID REFERENCES cluster_briefs(id)
);

CREATE TABLE decisions (
  id UUID PRIMARY KEY,
  cluster_id UUID REFERENCES clusters(id),
  brief_id UUID REFERENCES cluster_briefs(id),
  action VARCHAR(30),  -- accept / reject / snooze_30d / snooze_60d / snooze_90d / needs_more_signal
  reason_code VARCHAR(50),
  reason_text TEXT,
  decided_at TIMESTAMP,
  snooze_until TIMESTAMP
);

CREATE TABLE feedback_patterns (
  id UUID PRIMARY KEY,
  derived_at TIMESTAMP,
  pattern_description TEXT,
  affected_layer VARCHAR(20),  -- extractor / ranker / collector
  prompt_addendum TEXT,
  active BOOLEAN,
  human_reviewed BOOLEAN,
  created_from_decision_ids UUID[]
);

CREATE TABLE eval_sets (
  id UUID PRIMARY KEY,
  name VARCHAR(100),
  version VARCHAR(20),
  set_type VARCHAR(20),  -- extractor / clusterer / end_to_end
  created_at TIMESTAMP,
  record_count INT,
  description TEXT
);

CREATE TABLE eval_runs (
  id UUID PRIMARY KEY,
  eval_set_id UUID REFERENCES eval_sets(id),
  target_version VARCHAR(50),  -- e.g., "extractor_v2.3.1"
  run_at TIMESTAMP,
  scores_json JSONB,
  passed BOOLEAN,
  promoted_to_production BOOLEAN
);
```

### 6.4 Data flow

```
[Source] → [Collector] → [R2 archive] → [raw_signals_index]
                                             ↓
                         [Pre-filter: regex + length gates]
                                             ↓
                         [Tier 1: Classical NLP extractor]
                              (Haiku for is_problem_signal yes/no)
                                             ↓
                         [Tier 2: Sonnet full extraction]
                              (survivors only, ~15% of inputs)
                                             ↓
                         [Verbatim quote verification]
                                             ↓
                         [Embedding: E5-large-v2 or BGE-large]
                                             ↓
                         [extracted_problems table]
                                             ↓
                         [Incremental clustering → existing cluster
                          OR unassigned pool]
                                             ↓
                         [Nightly BERTopic on unassigned pool]
                                             ↓
                         [Cluster hygiene jobs (weekly)]
                                             ↓
                         [Ranker: SQL filters, not ML]
                                             ↓
                         [Opus brief generation (surfaced clusters only)]
                                             ↓
                         [Review UI → decisions]
                                             ↓
                         [Feedback loop → prompt addenda, source weights]
```

## 7. Collector fleet

### 7.1 Tier 1: Official APIs (build first)

All self-built using Python. Cadence varies by rate of change.

| Source | Cadence | Tool |
|---|---|---|
| Reddit | 4h | PRAW |
| Hacker News | 4h | Algolia HN API |
| GitHub | Daily | Official API |
| YouTube comments | Daily | Data API v3 |
| Federal Register | Daily | RSS + API |
| CMS releases | Daily | RSS |
| FDA guidance | Daily | RSS |
| SEC EDGAR | Daily | Official API |
| NIH RePORTER | Weekly | Official API |
| arXiv | Daily | Official API |
| Google Trends | Weekly | pytrends |
| Meta Ad Library | Weekly | Official API |
| Google Ads Transparency | Weekly | Public endpoint |
| Polymarket | Daily | API |
| Stack Overflow | Weekly | Official API |

### 7.2 Tier 2: Paid-API sources (add after Tier 1 stable)

| Source | Provider | Cost/mo |
|---|---|---|
| Keyword intelligence | Ahrefs OR Semrush (not both) | $100-200 |
| Traffic intel | Similarweb | $150 |
| Audience | SparkToro | $40 |
| AI visibility | Profound or similar | $100 |
| Podcast signal | Listen Notes | $10 |

### 7.3 Tier 3: Scraped via service (add selectively)

Use Apify actors or ScraperAPI/ScrapFly + custom parsers.

| Source | Method | Priority |
|---|---|---|
| G2 3-star reviews | Apify actor | High |
| Capterra reviews | Apify actor | Medium |
| Upwork repeat-client gigs | Apify actor | High |
| Indeed job postings (filtered) | Apify actor | Medium |
| App Store / Play Store reviews | AppFollow API | Medium |
| Product Hunt comments | Official API | Low |

### 7.4 Not included in v1

- LinkedIn (legal risk, account ban risk)
- Twitter/X (paid API, unreliable)
- TikTok/Instagram (no signal-to-effort justification)
- Authenticated Discord/Slack (ToS risk)
- Facebook Groups (ToS risk, poor tooling)

### 7.5 Collector contract

Every collector implements:

```python
class Collector:
    source_id: int
    cadence_cron: str
    tier: int
    version: str  # semver
    
    def fetch(self, since: datetime, run_id: str) -> Iterator[RawRecord]:
        """Pull raw records. Must be idempotent by external_id."""
        ...
    
    def pre_filter(self, record: RawRecord) -> bool:
        """Cheap regex/length gate. Returns True if worth extracting."""
        ...
    
    def healthcheck(self) -> HealthStatus:
        """Pull known-good record, verify parse. Used for breakage detection."""
        ...
```

### 7.6 Health monitoring

Every collector run writes to a `collector_runs` log. A monitoring job:
- Computes 7-day moving average of output volume per collector
- Alerts on Slack/email if current run is <20% of moving average
- Auto-disables a collector after 3 consecutive failed runs
- Requires human acknowledgment before re-enabling

## 8. Extraction pipeline

### 8.1 Two-pass design

**Pass 1 — Pre-filter (regex/length gates, zero LLM cost)**
- Each source defines its own pattern list
- For Reddit: must contain ≥1 of ~40 target phrases ("is there a tool", "I wish", "I built a spreadsheet", "how do you all handle", "anyone know of", "looking for something that", etc.)
- Eliminates 90%+ of raw volume before any LLM call

**Pass 2 — Classical NLP binary classifier (no LLM)**
- Fine-tuned distilBERT or similar, trained on the labeled eval set
- Output: `is_problem_signal: bool` with confidence
- Latency target: <50ms per record
- Cost: ~$0 marginal (self-hosted on CPU inference)

**Pass 3 — LLM structured extraction (Sonnet, batch API)**
- Only runs on Pass 2 positives
- Populates full extracted_problems record
- Uses Anthropic Batch API (50% discount) for 4-hour windows
- Verbatim quote verification post-hoc: discard records where `exact_quote` is not a substring of `raw_payload`

### 8.2 Extractor prompt structure (versioned)

```
You are extracting one problem signal from a {source} post.

Rules:
1. The "exact_quote" field MUST be a verbatim contiguous substring of the input.
   If no such quote exists that describes a problem, set is_problem_signal=false.

2. "problem_statement" must be one sentence. Specific. No solution mentioned.

3. "specificity_score" (1-10):
   1-3: vague ("EHR sucks")
   4-6: names a workflow but not cost/frequency ("patient scheduling is hard")
   7-10: names tool, workflow, AND cost/frequency/time ("our EHR forces us to 
         re-enter lab values every Friday, takes 2 hours, costs ~$1800/mo")

4. "wtp_level":
   none: pure venting, no indication of spending
   weak: mentions time cost or frustration
   strong: mentions paying for current workaround OR mentions existing tool
   proven: names dollar amounts, recurring spend, or named paid alternative

5. "layer":
   unformed: problem without a product category yet
   formed: actively searching for solutions
   frustrated: currently using a solution that partially fails
   paying: already spending money on a workaround

6. Set is_problem_signal=false for: marketing content, off-topic, product 
   announcements, pure emotional venting without workflow, hypothetical 
   scenarios.

Return strict JSON: {schema}
```

### 8.3 Embedding

- Model: E5-large-v2 (1024d) as default — flipped from original MiniLM choice based on noisy Reddit text
- Fallback: BGE-large-en-v1.5 if E5 underperforms on eval
- Compute at extraction time, store in pgvector
- HNSW index for similarity search

## 9. Clustering

### 9.1 Algorithm choice

**BERTopic** with incremental updates. Not raw HDBSCAN.

Why: BERTopic provides c-TF-IDF automatic labels, interpretable clusters, incremental update support, and an actively maintained library. Raw HDBSCAN output requires downstream labeling that is itself an unsolved problem.

### 9.2 Two-stage clustering

**Stage 1 (real-time, per-record):**
- New extracted_problem gets compared to existing cluster centroids via cosine similarity
- If similarity to nearest centroid > 0.82 → joins that cluster
- Otherwise → unassigned pool

**Stage 2 (nightly, batched):**
- Run BERTopic on unassigned pool
- New clusters form, centroids computed, unassigned pool drains
- `min_cluster_size = 3`, `min_samples = 2` (tunable)

### 9.3 Cluster hygiene (weekly)

- Merge: clusters with centroid similarity >0.90 collapse into one
- Split: clusters with silhouette score <0.15 flagged for BERTopic re-run with higher min_cluster_size
- Retire: clusters with no new members in 60 days → status=archived (not deleted)

### 9.4 Baseline tracking (12-week warmup)

For each cluster, maintain rolling 12-week baseline of member acquisition rate.

Signal score for a cluster includes:
```
deviation_sigma = (members_last_14d - expected_baseline_14d) 
                  / baseline_std_dev
```

Clusters with deviation_sigma > 2.0 are "growing abnormally." This is the alt-data pattern, not volume-based trending.

**Warmup rule:** clusters that are less than 12 weeks old use global baseline (median of mature clusters) rather than their own. Flag their scores as "preliminary" in the UI.

## 10. Ranker

### 10.1 SQL, not ML

The ranker is explicitly NOT a scoring model. It's a filter cascade.

A cluster is eligible for surfacing if:

1. member_count >= 3
2. source_diversity_count >= 2
3. layer_coverage overlaps at least 3 of {unformed, formed, frustrated, paying}
4. At least one member has wtp_level IN ('strong', 'proven')
5. deviation_from_baseline_sigma > 1.5 OR is_newly_discovered_14d = true
6. status NOT IN ('rejected', 'snoozed') or snooze_until < NOW()
7. Has passing Admiralty scores (avg reliability in A-C range, avg credibility 1-3)

Among eligible, rank by:
```
ORDER BY 
  layer_coverage_count DESC,
  deviation_from_baseline_sigma DESC,
  source_diversity_count DESC,
  member_count_last_14d DESC
```

### 10.2 Surfacing rate calibration

Target: 3-5 clusters surfaced per day, auto-calibrated to user review capacity.

Weekly job adjusts thresholds based on 28-day rolling review rate (see §14).

### 10.3 What the ranker does NOT do

- No weighted composite score
- No ML-trained ranking model (at least not in v1)
- No "opportunity score" presented to the user
- No auto-promotion to "accepted" — human always decides

## 11. Cluster brief generation

### 11.1 When

A brief is generated when a cluster first meets surfacing criteria, or when it re-qualifies after a +20% membership change.

### 11.2 Who

Claude Opus (not Sonnet). This is the one place in the pipeline where model quality matters most. Cost is bounded by surfacing rate (3-5/day).

### 11.3 Brief template

```markdown
# Cluster: {canonical_statement}

## Canonical problem
{one sentence, generated by Opus from member quotes}

## Evidence
### Layer 1 (unformed): {N} signals from {source list}
> "{exact quote 1}" — {source}, {date}
> "{exact quote 2}" — {source}, {date}

### Layer 3 (frustrated): {N} signals from {source list}
> "{exact quote}" — {source}, {date}

### Layer 4 (paying): {N} signals from {source list}
> "{exact quote}" — {source}, {date}

## Who appears to be the buyer
{specific role at specific org type, synthesized from buyer_hint fields}

## Existing solutions named in signals
- {Tool}: mentioned in {N} signals — {praise | complaint | migration-away-from}
- {Tool}: ...

## Admiralty assessment
- Source reliability: {avg A-F}
- Information credibility: {avg 1-6}
- Independent platforms represented: {N}
- Distinct accounts contributing: {N}

## Growth signal
- 14-day membership change: +{N} (sigma: {deviation})
- New sources in last 14d: {list}

## Contradicting evidence (mandatory)
{Results of active search for disconfirming signals. If none found, state that.}

## Interview prompts
If you choose to validate this with customers:

1. Past behavior: "Tell me about the last time you {specific workflow}. 
   Walk me through what happened."
2. Current workaround: "How are you solving this today?"
3. Problem ranking: "Where does this sit among the top 3 things eating 
   your week?"
4. Trigger: "What would have to change for this to move up or down that list?"
5. Commitment test: "Would you be willing to {specific ask: pilot, intro, 
   time commitment}?"

## Open questions to validate
- {specific thing you'd need to confirm with 3 conversations}
- {specific thing}
- {specific thing}
```

### 11.4 Verification

After generation:
- Every quote in the brief must be present in an extracted_problems.exact_quote field
- Post-hoc check discards briefs with fabricated quotes and re-generates
- If re-generation fails verification twice, the brief is flagged for manual inspection, not surfaced

## 12. Review UI

### 12.1 Technology

Streamlit. Not Next.js, not React. Single-user, speed-of-iteration matters more than polish.

### 12.2 Views

**Daily queue** (default view)
- Ranked list of 3-5 briefs surfaced today
- Each expandable to full brief
- Four action buttons per brief: Accept / Reject / Snooze / Needs More Signal
- Reject requires dropdown: too-crowded / wrong-buyer / not-my-domain / signal-too-weak / already-tried / incumbent-will-own / other (with text field)

**Watchlist** (clusters in "watching" or "needs-more-signal" state)

**Accepted** (clusters moved to validation state, with space for interview notes)

**Source health** (table of collectors, last run, output volume, breakage alerts)

**Eval status** (latest eval scores for extractor, clusterer, end-to-end)

### 12.3 Explicit NOT in the UI

- No "opportunity score" number
- No "AI recommendation"
- No automation of the accept/reject decision
- No notification spam — one daily digest email, nothing else

## 13. Evaluation harness

### 13.1 Three eval sets

**Set A — Extractor eval (built in week 1, before any production extraction)**
- 200 hand-labeled posts from target domain
- Fields: is_problem_signal, specificity_score, layer, wtp_level
- Stratification: 40% obvious problems, 30% borderline, 30% non-problems
- Version-controlled in git as `evals/extractor_v{N}.jsonl`
- Refreshed monthly: add 20-30 new examples, retire stale ones

**Set B — Clusterer eval (built in week 4)**
- 300 extracted problems manually grouped into gold clusters
- Metric: Adjusted Rand Index vs. gold groupings

**Set C — End-to-end eval (built ongoing)**
- 20 historical cluster briefs with recorded accept/reject decisions
- New system must reproduce decisions at ≥75% agreement

### 13.2 Eval gates

No change ships to production without eval pass:

| Change type | Must pass |
|---|---|
| Extractor prompt change | Set A |
| Extraction model change | Set A |
| Embedding model change | Set B |
| Clustering algorithm change | Set B |
| Ranker filter change | Set C |
| Brief prompt change | Manual review of 5 regenerated briefs |

### 13.3 Eval thresholds (starting, to be calibrated)

**Set A (extractor):**
- is_problem_signal F1 ≥ 0.75
- specificity_score MAE ≤ 1.5
- layer accuracy ≥ 0.65
- wtp_level accuracy ≥ 0.70

**Set B (clusterer):**
- ARI ≥ 0.60 against gold groupings

**Set C (end-to-end):**
- Decision agreement ≥ 0.75

## 14. Versioning and reprocessing

### 14.1 Versioning scheme

Every derived record carries:
- `extraction_run_id` → points to the specific run that created it
- Runs carry: extractor_version, prompt_hash, model_identifier, eval_scores_json

### 14.2 Canary deployment

New extractor versions:
1. Ship to 10% canary slice of incoming signals
2. Run Set A eval on canary output
3. If pass → promote to 50%
4. If second eval passes → promote to 100% for new signals only
5. Old signals stay on old version until explicit reprocessing run

### 14.3 Reprocessing runs

Explicit operational events, not background jobs:
1. Human initiates: "reprocess raw signals from date X onward with extractor_version Y"
2. System produces diff report: clusters that changed membership, new clusters, merged clusters
3. Human reviews diff
4. Human promotes or rolls back

### 14.4 Cluster version hygiene

- Clusters with all members from same extractor_version → status=clean
- Clusters with mixed versions → status=mixed, shown with warning in UI
- After a reprocessing run, also re-cluster

## 15. Human throughput calibration

### 15.1 Measured, not assumed

Weeks 1-2 of operation: run with NO ranking threshold. Surface everything passing filters.

Measure:
- Briefs opened per day
- Decisions made per day
- Median decision time

### 15.2 Calibration formula

Weekly job adjusts ranker threshold:

```python
def adjust_threshold(current_threshold, metrics_28d):
    review_rate = metrics_28d.reviewed / max(metrics_28d.surfaced, 1)
    decision_rate = metrics_28d.decided / max(metrics_28d.reviewed, 1)
    
    if review_rate < 0.70:
        return current_threshold * 1.10  # surfacing too much, raise bar
    if review_rate > 0.95 and decision_rate > 0.80:
        return current_threshold * 0.95  # surfacing too little, lower bar
    return current_threshold
```

### 15.3 Backlog hygiene

- Briefs unreviewed after 14 days → auto-archived (not deleted)
- Archived briefs can be reactivated if cluster grows significantly
- Explicit "low capacity week" mode: only surface briefs with deviation_sigma ≥ 3.0

### 15.4 Throughput metric

Monthly dashboard shows: "% of surfaced briefs acted on within 7 days." Target ≥ 80%. Below 60% → reduce surfacing rate.

## 16. Meta-learning

### 16.1 Weekly: prompt-level learning

Job reads last 30 rejection decisions and their reason codes. Generates candidate prompt addenda. Human reviews and approves before activation. Active addenda prepended to extractor and ranker prompts. Can be deactivated if they hurt eval scores.

### 16.2 Monthly: source accept rate rebalancing

Per-source metric: fraction of clusters this source contributed to that were accepted.

- Sources with accept rate > 1.5× median → increase cadence / budget
- Sources with accept rate < 0.3× median → throttle or disable
- Requires human confirmation before disabling

### 16.3 Quarterly: structural review (human-driven)

Human sits down with last quarter's accepted clusters. Asks:
- What categories of problems am I systematically missing?
- What sources are not in my fleet that might catch those?
- Have my accept criteria drifted?

Output: deliberate additions to source fleet, or deliberate relaxation of filters. System cannot do this alone — it doesn't know what's outside its own sampling frame.

### 16.4 Anti-calcification

Once per month, the system deliberately surfaces 1 cluster that violates a learned rejection pattern. Labeled as "exploration — known to not match your preferences, surfaced to prevent filter calcification." Prevents the feedback loop from collapsing onto past preferences.

## 17. Legal and safety

### 17.1 Hard NOs

- No scraping behind login walls
- No circumventing CAPTCHAs or IP blocks
- No verbatim reproduction of copyrighted content in briefs (exact quotes under fair use quantities; paraphrase in synthesis)
- No storing identifiable EU users without GDPR compliance
- No scraping of authenticated private sources (Discord servers without permission, private Slack, Facebook Groups)

### 17.2 Data retention

- Raw archive: indefinite, encrypted at rest
- Extracted problems: indefinite
- Attributable usernames: pseudonymize at extraction time if source is EU-origin
- Right-to-delete: supported via external_id lookup and redaction in derived tables (raw kept but flagged)

### 17.3 Pre-launch legal review

Before the system operates against scraped (non-API) sources, one paid hour with a lawyer specialized in internet law. Topics:
- ToS posture for each Tier 3 source
- GDPR applicability given user base
- Copyright posture for stored quotes
- Recent case law (Meta v. Bright Data, NYT v. OpenAI)

Budget: $500-1000.

## 18. Cost model

### 18.1 Fixed monthly

| Item | Cost |
|---|---|
| Postgres hosting (managed, 8GB) | $50 |
| R2 archive (projected 50GB/yr) | $5 |
| Compute (single VPS or small k8s) | $40 |
| Ahrefs OR Semrush (not both) | $100-200 |
| Similarweb | $150 |
| SparkToro | $40 |
| AI visibility tool | $100 |
| Apify credits | $200-400 |
| ScraperAPI / ScrapFly | $100 |
| **Fixed total** | **$785-1085** |

### 18.2 Variable monthly (LLM)

| Item | Volume assumption | Cost |
|---|---|---|
| Tier 1 classifier (self-hosted) | 100K records | ~$0 |
| Haiku pre-check (batch) | 10K records | $5 |
| Sonnet extraction (batch) | 2K records | $15 |
| Embeddings (Voyage or OpenAI small) | 2K/day | $10 |
| Opus brief generation | 100 briefs/mo | $20 |
| **LLM total** | | **$50** |

### 18.3 Total

**~$850-1150/month** at steady state, single domain.

Halve by dropping Ahrefs/Similarweb/SparkToro. Third-party data is the dominant cost.

## 19. Build plan

### Week 1 — Foundation
- Day 1-2: R2 archive setup, Postgres schema, pgvector extension
- Day 3-4: Label 200 posts for extractor eval Set A
- Day 5: Write eval harness. First null run against empty extractor.

### Week 2 — Tier 1 extraction
- Day 1-2: Reddit collector (PRAW) with pre-filter
- Day 3-4: Classical NLP classifier (distilBERT fine-tuned on Set A)
- Day 5: Haiku is_problem_signal classifier + Sonnet extractor + verbatim check
- Eval gate: Set A F1 ≥ 0.70 before proceeding

### Week 3 — Versioning and second source
- Day 1-2: Extraction runs, canary deployment, reprocessing pipeline
- Day 3-4: Hacker News collector + Federal Register collector
- Day 5: Build Set B clusterer eval

### Week 4 — Clustering
- Day 1-3: BERTopic integration, two-stage clustering, baseline tracking
- Day 4-5: Cluster hygiene jobs, eval against Set B
- Eval gate: ARI ≥ 0.55 before proceeding

### Week 5 — Brief generation and UI
- Day 1-2: Opus brief generator with verification
- Day 3-5: Streamlit review UI (daily queue, accepted, source health)

### Week 6 — Run open-loop
- System surfaces everything passing filters
- Measure personal throughput
- No threshold calibration yet
- Keep labeling 10 posts/day into Set A expansion

### Week 7 — Calibrate and add sources
- Apply throughput calibration to ranker
- Add GitHub, SEC EDGAR, CMS collectors
- Build Set C end-to-end eval

### Week 8 — First review and reallocation
- Review all decisions made so far
- Kill underperforming sources
- Add Tier 2 paid sources if budget allows
- Structural review #1

## 20. Success metrics

### 20.1 Leading indicators (month 1-3)

- Eval Set A F1 > 0.75 sustained over 4 weeks
- Surfacing rate within 20% of target (3-5/day)
- Human review rate > 80% of surfaced briefs within 7 days
- Zero silent scraper breakages longer than 48 hours
- Zero hallucinated quotes surfaced to UI (verified by audit)

### 20.2 Lagging indicators (month 3-6)

- At least 3 accepted clusters validated via real customer interviews
- At least 1 accepted cluster reaches "we should build this" conviction
- At least 1 source identified as carrying its weight + 1 identified as dead weight

### 20.3 Ultimate success (month 6-12)

- One validated problem that leads to an actual product decision
- System continues to operate with <4 hours/week of maintenance
- Eval scores have improved, not regressed, over 6 months
- At least one source has been swapped without breaking the pipeline (proving platform-independence)

## 21. Failure modes and mitigations

| Failure mode | Mitigation |
|---|---|
| Scraper rot (Tier 3) | Health monitoring, 3-strike auto-disable, human re-enable |
| LLM hallucination of quotes | Verbatim substring verification, eval gating |
| Platform shutdown (e.g., Reddit API change) | No source is load-bearing; ranker requires 2+ source diversity |
| Cluster drift (semantic) | Weekly hygiene jobs, centroid merge/split |
| Eval set becomes stale | Monthly refresh, retire old examples |
| Self-referential tuning / filter calcification | Quarterly structural review + monthly exploration surfacing |
| User burnout from backlog | 14-day auto-archive, low-capacity mode, surfacing rate calibration |
| Cost blowout | Batch API, self-hosted classifier, monthly cost alert at 150% of baseline |
| Legal challenge | Pre-launch legal review, hard NOs, pseudonymization |
| Citation/fact hallucinations in briefs | Post-gen verification, flag for manual review if re-gen fails twice |

## 22. Open questions / deferred to v2

- Multi-domain support (currently single-domain: health tech)
- Multi-user / team version
- MCP server exposure (design as-if, implement later)
- Advanced: Thompson sampling on source budget allocation
- Advanced: contradiction search using adversarial prompting
- Whether to publish the tool as a Claude Code skill (follows `last30days` model)

## 23. Explicit non-decisions

Things deliberately not specified, to be decided based on operational data:

- Exact Admiralty Scale thresholds for Tier 2 promotion
- Exact deviation_sigma threshold for surfacing (starts at 1.5, calibrates)
- Whether to add prediction markets (Polymarket) as Tier 1 or Tier 2
- Whether to run a nightly "weak signal" digest in addition to daily queue
- Embedding model final choice (E5 vs. BGE vs. nomic — decided by Set B eval)

---

## Appendix A: Reference implementations

- `mvanhorn/last30days-skill` — architectural reference for parallel source fanout
- `Mohamedsaleh14/Reddit_Scrapper` — Reddit-specific pipeline reference
- BERTopic — clustering reference
- Teresa Torres, *Continuous Discovery Habits* — taxonomy reference
- Bellingcat OSINT Handbook — verification methodology
- *The Mom Test* by Rob Fitzpatrick — interview protocol reference

## Appendix B: What this PRD is not

- Not a product pitch. It's an internal spec.
- Not a complete technical design doc. Major components (collector code, prompt files, UI wireframes) are implementation-level and belong in follow-up specs.
- Not immutable. Every decision here should be revisited at the week-8 structural review and quarterly thereafter.
- Not a promise of success. It's a well-reasoned bet. The system might surface 50 clusters over 6 months and none of them turn into a business. That's possible. The architecture is designed to fail gracefully and teach you something either way.

---

**One line that should survive if everything else changes:**
*The system's job is to keep a ranked queue of 3-5 real, triangulated, grounded problems in front of a human who has taste. The system does not decide what to build. The human does. Everything else is plumbing.*