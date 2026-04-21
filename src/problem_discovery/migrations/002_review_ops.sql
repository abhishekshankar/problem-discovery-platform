-- PRD §12 (interview notes), §15.3 (stale brief archive), §16.4 (exploration surfacing)

ALTER TABLE clusters ADD COLUMN IF NOT EXISTS interview_notes TEXT;
ALTER TABLE clusters ADD COLUMN IF NOT EXISTS is_exploration BOOLEAN DEFAULT FALSE;

ALTER TABLE cluster_briefs ADD COLUMN IF NOT EXISTS archived_at TIMESTAMP;

-- Cost monitoring baseline (PRD §21 — cost blowout alert)
CREATE TABLE IF NOT EXISTS cost_baselines (
  id SERIAL PRIMARY KEY,
  singleton_lock SMALLINT DEFAULT 1 UNIQUE CHECK (singleton_lock = 1),
  monthly_llm_usd NUMERIC DEFAULT 50,
  monthly_infra_usd NUMERIC DEFAULT 100,
  updated_at TIMESTAMP DEFAULT NOW()
);

INSERT INTO cost_baselines (singleton_lock, monthly_llm_usd, monthly_infra_usd)
SELECT 1, 50, 100
WHERE NOT EXISTS (SELECT 1 FROM cost_baselines LIMIT 1);
