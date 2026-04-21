# Privacy & GDPR operator runbook (PRD §17.2)

## Pseudonymization (EU-origin sources)

1. Mark sources that may contain EU personal data:
   ```sql
   UPDATE sources SET is_eu_origin = TRUE WHERE name = 'reddit';
   ```
2. Set a stable per-deployment secret (rotate only with a documented re-hash plan):
   ```bash
   export SIGNAL_PSEUDONYM_SALT="$(openssl rand -hex 32)"
   ```
3. On ingest, `run_collector` hashes `author` / `username` / `user` / `commenter` / `name` (and close variants) in `raw_payload` before archive + `raw_signals_index` write.
4. During extraction, `author_pseudonym` may be populated on `extracted_problems` for EU rows.

## Right to erasure (`signal-cli redact`)

For a given source name and external id (as stored in `raw_signals_index.external_id`):

```bash
export DATABASE_URL=postgresql://...
python -m problem_discovery.signal redact --source reddit --external-id abc123
```

Effects:

- Deletes `extracted_problems` for that raw row (cluster memberships cascade).
- Sets `raw_signals_index.raw_payload` to NULL and `redacted_at = NOW()` (row id retained for audit).
- Renames the archive object to `*.redacted` when using local archive paths or S3-compatible storage.

## Audit

- Archive blobs remain the legal record; redaction stops pipeline access to payload content.
- Cross-check `raw_signals_index.redacted_at` and storage keys ending in `.redacted` during incident review.
