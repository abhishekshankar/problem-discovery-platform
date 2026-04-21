"""Run a collector: archive (Tier A) + raw_signals_index + collector_runs (PRD §7)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from psycopg.rows import dict_row

from ..archive.writer import RawArchiveWriter, RawRecordLine, compute_payload_hash
from ...config import DATA_DIR
from ..db import connection
from ..settings import SignalSettings, get_settings
from .protocol import Collector, RawRecord


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_source(conn: Any, name: str, *, tier: int = 1) -> int:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id FROM sources WHERE name = %s", (name,))
        row = cur.fetchone()
        if row:
            return int(row["id"])
        cur.execute(
            "INSERT INTO sources (name, tier, status) VALUES (%s, %s, %s) RETURNING id",
            (name, tier, "active"),
        )
        rid = cur.fetchone()
        assert rid is not None
        return int(rid["id"])


def ensure_collector(
    conn: Any,
    *,
    source_id: int,
    name: str,
    version: str,
    cadence_cron: str,
) -> int:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id FROM collectors WHERE source_id = %s AND name = %s",
            (source_id, name),
        )
        row = cur.fetchone()
        if row:
            return int(row["id"])
        cur.execute(
            """
            INSERT INTO collectors (source_id, name, version, cadence_cron, status)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (source_id, name, version, cadence_cron, "active"),
        )
        rid = cur.fetchone()
        assert rid is not None
        return int(rid["id"])


def run_collector(
    collector: Collector,
    *,
    settings: SignalSettings | None = None,
    since: datetime | None = None,
) -> dict[str, Any]:
    """Fetch → pre_filter → archive → DB index; returns summary."""
    s = settings or get_settings()
    if not s.database_url:
        raise RuntimeError("DATABASE_URL is required")

    run_uuid = uuid.uuid4()
    scrape_run_id = str(run_uuid)
    source_name = collector.source_name
    version = collector.version
    cron = collector.cadence_cron

    records: list[RawRecord] = []
    for rec in collector.fetch(since, scrape_run_id):
        if collector.pre_filter(rec):
            records.append(rec)

    with connection(autocommit=True) as conn:
        sid_check = ensure_source(conn, source_name, tier=collector.tier)
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT COALESCE(is_eu_origin, FALSE) AS eu FROM sources WHERE id = %s",
                (sid_check,),
            )
            eu_row = cur.fetchone()
    is_eu = bool(eu_row and eu_row.get("eu"))
    if is_eu and (s.signal_pseudonym_salt or "").strip():
        from ..privacy import pseudonymize_payload

        salt = s.signal_pseudonym_salt or ""
        for rec in records:
            rec.raw_payload = pseudonymize_payload(rec.raw_payload, salt)

    if not records:
        with connection(autocommit=True) as conn:
            sid = ensure_source(conn, source_name, tier=collector.tier)
            cid = ensure_collector(conn, source_id=sid, name=f"{source_name}_default", version=version, cadence_cron=cron)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO collector_runs (collector_id, run_id, started_at, completed_at, record_count, status)
                    VALUES (%s, %s, NOW(), NOW(), %s, %s)
                    """,
                    (cid, run_uuid, 0, "ok"),
                )
        return {"scrape_run_id": scrape_run_id, "archived": 0, "indexed": 0, "skipped_duplicate": 0}

    lines: list[RawRecordLine] = []
    for rec in records:
        ph = compute_payload_hash(rec.raw_payload)
        cap = _utc_now().isoformat()
        lines.append(
            RawRecordLine(
                external_id=rec.external_id,
                source=source_name,
                captured_at=cap,
                source_timestamp=rec.source_timestamp.isoformat() if rec.source_timestamp else None,
                raw_payload=rec.raw_payload,
                collector_version=version,
                scrape_run_id=scrape_run_id,
                payload_hash=ph,
            )
        )

    writer = RawArchiveWriter(settings=s)
    local_dir = s.archive_local_dir
    if not local_dir and not (s.s3_access_key_id and s.s3_secret_access_key):
        local_dir = str(DATA_DIR / "signal_archive")
    if local_dir:
        base = Path(local_dir)
        archive_path = writer.write_batch_local(str(base), source_name, lines, batch_id=scrape_run_id)
    else:
        archive_path = writer.write_batch(source_name, lines, batch_id=scrape_run_id)

    indexed = 0
    skipped = 0
    with connection(autocommit=False) as conn:
        sid = ensure_source(conn, source_name, tier=collector.tier)
        cid = ensure_collector(conn, source_id=sid, name=f"{source_name}_default", version=version, cadence_cron=cron)

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO collector_runs (collector_id, run_id, started_at, status)
                VALUES (%s, %s, NOW(), 'running')
                """,
                (cid, run_uuid),
            )

        for rec in records:
            raw_text = json.dumps(rec.raw_payload, sort_keys=True)
            ph = compute_payload_hash(rec.raw_payload)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO raw_signals_index (
                      external_id, source_id, archive_path, captured_at, source_timestamp, url,
                      raw_payload, scrape_run_id, collector_version, payload_hash
                    )
                    VALUES (%s, %s, %s, NOW(), %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (source_id, external_id) DO NOTHING
                    """,
                    (
                        rec.external_id,
                        sid,
                        archive_path,
                        rec.source_timestamp,
                        rec.url,
                        raw_text,
                        run_uuid,
                        version,
                        ph,
                    ),
                )
                if cur.rowcount:
                    indexed += 1
                else:
                    skipped += 1

        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE collector_runs
                SET completed_at = NOW(), record_count = %s, status = %s
                WHERE collector_id = %s AND run_id = %s
                """,
                (indexed, "ok", cid, run_uuid),
            )
            cur.execute(
                "UPDATE collectors SET last_run_at = NOW(), last_output_count = %s WHERE id = %s",
                (indexed, cid),
            )

        conn.commit()

    return {
        "scrape_run_id": scrape_run_id,
        "archive_path": archive_path,
        "archived": len(records),
        "indexed": indexed,
        "skipped_duplicate": skipped,
    }
