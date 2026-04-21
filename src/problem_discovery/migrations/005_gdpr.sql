-- PRD §17.2 — GDPR-oriented columns and redaction support

ALTER TABLE sources ADD COLUMN IF NOT EXISTS is_eu_origin BOOLEAN DEFAULT FALSE;

ALTER TABLE raw_signals_index ADD COLUMN IF NOT EXISTS redacted_at TIMESTAMP;
ALTER TABLE raw_signals_index ALTER COLUMN raw_payload DROP NOT NULL;

ALTER TABLE extracted_problems ADD COLUMN IF NOT EXISTS author_pseudonym VARCHAR(64);
