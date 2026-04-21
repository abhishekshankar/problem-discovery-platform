-- Signal / Latent Demand Discovery — initial schema (PRD §6.3 + extensions)
-- Run after: CREATE DATABASE ... ; connect with superuser for extension once

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE sources (
  id SERIAL PRIMARY KEY,
  name VARCHAR(100) UNIQUE NOT NULL,
  tier INT,
  status VARCHAR(20),
  cost_per_1k_calls NUMERIC,
  rate_limit_per_hour INT,
  last_success_at TIMESTAMP,
  breakage_count_30d INT,
  accept_rate_rolling NUMERIC,
  notes TEXT
);

CREATE TABLE collectors (
  id SERIAL PRIMARY KEY,
  source_id INT REFERENCES sources(id),
  name VARCHAR(100) NOT NULL,
  version VARCHAR(20),
  config_json JSONB,
  cadence_cron VARCHAR(50),
  last_run_at TIMESTAMP,
  last_output_count INT,
  avg_signal_noise_ratio NUMERIC,
  status VARCHAR(20)
);

-- PRD §7.6 — not in §6.3 schema text; required for monitoring
CREATE TABLE collector_runs (
  id BIGSERIAL PRIMARY KEY,
  collector_id INT NOT NULL REFERENCES collectors(id),
  run_id UUID NOT NULL,
  started_at TIMESTAMP NOT NULL,
  completed_at TIMESTAMP,
  record_count INT,
  status VARCHAR(20),
  error_message TEXT
);

CREATE INDEX idx_collector_runs_collector_started ON collector_runs (collector_id, started_at DESC);

-- Tier B index; raw_payload duplicated for fast quote verification (Tier A remains source of truth)
CREATE TABLE raw_signals_index (
  id BIGSERIAL PRIMARY KEY,
  external_id VARCHAR(200) NOT NULL,
  source_id INT NOT NULL REFERENCES sources(id),
  archive_path TEXT NOT NULL,
  captured_at TIMESTAMP NOT NULL,
  source_timestamp TIMESTAMP,
  url TEXT,
  raw_payload TEXT NOT NULL,
  scrape_run_id UUID,
  collector_version VARCHAR(20),
  payload_hash VARCHAR(64),
  UNIQUE (source_id, external_id)
);

CREATE INDEX idx_raw_signals_source_captured ON raw_signals_index (source_id, captured_at DESC);

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
  promoted_at TIMESTAMP,
  canary_fraction NUMERIC DEFAULT 1.0
);

CREATE TABLE extracted_problems (
  id BIGSERIAL PRIMARY KEY,
  raw_signal_id BIGINT NOT NULL REFERENCES raw_signals_index(id),
  extraction_run_id UUID REFERENCES extraction_runs(id),
  is_problem_signal BOOLEAN,
  problem_statement TEXT,
  exact_quote TEXT,
  quote_verified BOOLEAN,
  specificity_score NUMERIC,
  wtp_level VARCHAR(20),
  wtp_evidence TEXT,
  layer VARCHAR(20),
  domain_tags TEXT[],
  buyer_hint TEXT,
  workaround_described TEXT,
  admiralty_source_reliability CHAR(1),
  admiralty_info_credibility INT,
  embedding vector(1024),
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_extracted_problems_run ON extracted_problems (extraction_run_id);
CREATE INDEX idx_extracted_problems_created ON extracted_problems (created_at DESC);

-- PRD Tier C — HNSW for similarity search (cosine)
CREATE INDEX idx_extracted_problems_embedding_hnsw
  ON extracted_problems USING hnsw (embedding vector_cosine_ops);

CREATE TABLE clustering_runs (
  id UUID PRIMARY KEY,
  algorithm VARCHAR(50),
  algorithm_version VARCHAR(20),
  parameters_json JSONB,
  extractor_version_filter VARCHAR(20),
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
  c_tfidf_label TEXT,
  first_seen_at TIMESTAMP,
  last_seen_at TIMESTAMP,
  member_count INT,
  layer_coverage VARCHAR(20)[],
  source_diversity_count INT,
  growth_rate_14d NUMERIC,
  centroid_embedding vector(1024),
  status VARCHAR(20),
  deviation_from_baseline_sigma NUMERIC,
  is_newly_discovered_14d BOOLEAN DEFAULT FALSE,
  member_count_last_14d INT DEFAULT 0,
  version_status VARCHAR(20) DEFAULT 'clean',
  surfaced_at TIMESTAMP
);

CREATE INDEX idx_clusters_status_surfaced ON clusters (status, surfaced_at DESC);

CREATE INDEX idx_clusters_centroid_hnsw
  ON clusters USING hnsw (centroid_embedding vector_cosine_ops);

CREATE TABLE cluster_members (
  cluster_id UUID NOT NULL REFERENCES clusters(id) ON DELETE CASCADE,
  extracted_problem_id BIGINT NOT NULL REFERENCES extracted_problems(id) ON DELETE CASCADE,
  similarity_score NUMERIC,
  added_at TIMESTAMP,
  PRIMARY KEY (cluster_id, extracted_problem_id)
);

CREATE INDEX idx_cluster_members_problem ON cluster_members (extracted_problem_id);

CREATE TABLE cluster_briefs (
  id UUID PRIMARY KEY,
  cluster_id UUID NOT NULL REFERENCES clusters(id) ON DELETE CASCADE,
  generated_at TIMESTAMP,
  model_identifier VARCHAR(50),
  brief_markdown TEXT,
  interview_prompts_json JSONB,
  superseded_by UUID REFERENCES cluster_briefs(id),
  verification_attempts INT DEFAULT 0,
  verification_failed BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_cluster_briefs_cluster ON cluster_briefs (cluster_id, generated_at DESC);

CREATE TABLE decisions (
  id UUID PRIMARY KEY,
  cluster_id UUID NOT NULL REFERENCES clusters(id) ON DELETE CASCADE,
  brief_id UUID REFERENCES cluster_briefs(id),
  action VARCHAR(30) NOT NULL,
  reason_code VARCHAR(50),
  reason_text TEXT,
  decided_at TIMESTAMP,
  snooze_until TIMESTAMP
);

CREATE INDEX idx_decisions_cluster ON decisions (cluster_id, decided_at DESC);

CREATE TABLE feedback_patterns (
  id UUID PRIMARY KEY,
  derived_at TIMESTAMP,
  pattern_description TEXT,
  affected_layer VARCHAR(20),
  prompt_addendum TEXT,
  active BOOLEAN,
  human_reviewed BOOLEAN,
  created_from_decision_ids UUID[]
);

CREATE TABLE eval_sets (
  id UUID PRIMARY KEY,
  name VARCHAR(100),
  version VARCHAR(20),
  set_type VARCHAR(20),
  created_at TIMESTAMP,
  record_count INT,
  description TEXT
);

CREATE TABLE eval_runs (
  id UUID PRIMARY KEY,
  eval_set_id UUID REFERENCES eval_sets(id),
  target_version VARCHAR(50),
  run_at TIMESTAMP,
  scores_json JSONB,
  passed BOOLEAN,
  promoted_to_production BOOLEAN
);

-- Throughput calibration / ranker tunables (PRD §10.2, §15)
CREATE TABLE ranker_settings (
  id SERIAL PRIMARY KEY,
  singleton_lock SMALLINT DEFAULT 1 UNIQUE CHECK (singleton_lock = 1),
  deviation_sigma_threshold NUMERIC DEFAULT 1.5,
  surfacing_cap_per_day INT DEFAULT 5,
  updated_at TIMESTAMP DEFAULT NOW()
);

INSERT INTO ranker_settings (singleton_lock, deviation_sigma_threshold, surfacing_cap_per_day)
SELECT 1, 1.5, 5
WHERE NOT EXISTS (SELECT 1 FROM ranker_settings LIMIT 1);

-- Review metrics for §15 calibration (optional aggregate store)
CREATE TABLE review_metrics_daily (
  day DATE PRIMARY KEY,
  briefs_surfaced INT DEFAULT 0,
  briefs_opened INT DEFAULT 0,
  decisions_made INT DEFAULT 0
);
