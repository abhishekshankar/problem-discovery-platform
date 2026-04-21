-- Canary rollout (PRD §14.2) + source throttle proposals (PRD §16.2)

CREATE TABLE IF NOT EXISTS extractor_promotion_state (
  id SERIAL PRIMARY KEY,
  singleton_lock SMALLINT DEFAULT 1 UNIQUE CHECK (singleton_lock = 1),
  candidate_rollout_fraction NUMERIC DEFAULT 0 NOT NULL,
  last_eval_passed BOOLEAN,
  last_eval_run_id UUID,
  notes TEXT,
  updated_at TIMESTAMP DEFAULT NOW()
);

INSERT INTO extractor_promotion_state (singleton_lock, candidate_rollout_fraction)
SELECT 1, 0
WHERE NOT EXISTS (SELECT 1 FROM extractor_promotion_state LIMIT 1);

CREATE TABLE IF NOT EXISTS source_rebalance_proposals (
  id UUID PRIMARY KEY,
  source_id INT NOT NULL REFERENCES sources(id),
  proposed_status VARCHAR(30) NOT NULL,
  reason TEXT,
  median_accept_rate NUMERIC,
  source_accept_rate NUMERIC,
  created_at TIMESTAMP DEFAULT NOW(),
  confirmed_at TIMESTAMP,
  confirmed_by TEXT,
  rejected_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_rebalance_proposals_pending
  ON source_rebalance_proposals (source_id) WHERE confirmed_at IS NULL AND rejected_at IS NULL;
