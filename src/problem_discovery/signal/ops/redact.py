"""Right-to-delete / redact a raw signal (PRD §17.2)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from psycopg.rows import dict_row

from ..db import connection
from ..settings import SignalSettings, get_settings


def redact_raw_signal(
    *,
    source_name: str,
    external_id: str,
    settings: SignalSettings | None = None,
) -> dict[str, Any]:
    """
    Delete derived rows for (source, external_id), null raw_payload, set redacted_at,
    and rename archive object to `.redacted` when path is accessible.
    """
    s = settings or get_settings()
    if not s.database_url:
        raise RuntimeError("DATABASE_URL is required")
    with connection(autocommit=False) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT r.id, r.archive_path
                FROM raw_signals_index r
                JOIN sources src ON src.id = r.source_id
                WHERE src.name = %s AND r.external_id = %s
                LIMIT 1
                """,
                (source_name, external_id),
            )
            row = cur.fetchone()
        if not row:
            conn.rollback()
            return {"ok": False, "error": "raw signal not found"}
        rid = int(row["id"])
        apath = row.get("archive_path") or ""
        with conn.cursor() as cur:
            cur.execute("DELETE FROM extracted_problems WHERE raw_signal_id = %s", (rid,))
            deleted_ep = cur.rowcount or 0
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE raw_signals_index
                SET raw_payload = NULL, redacted_at = NOW()
                WHERE id = %s
                """,
                (rid,),
            )
        conn.commit()

    archive_note = _rename_archive_mark_redacted(str(apath), settings=s)
    return {
        "ok": True,
        "raw_signal_id": rid,
        "extracted_problems_deleted": deleted_ep,
        "archive": archive_note,
    }


def _rename_archive_mark_redacted(archive_path: str, *, settings: SignalSettings) -> dict[str, Any]:
    if not archive_path:
        return {"skipped": True, "reason": "no archive_path"}
    p = Path(archive_path)
    if p.is_file():
        dest = p.with_name(p.name + ".redacted")
        try:
            p.rename(dest)
            return {"local_renamed_to": str(dest)}
        except OSError as e:
            return {"error": str(e)}
    if settings.s3_access_key_id and settings.s3_secret_access_key:
        try:
            import boto3  # type: ignore[import-untyped]
            from botocore.config import Config  # type: ignore[import-untyped]

            cfg = Config(s3={"addressing_style": settings.s3_addressing_style or "path"})
            client = boto3.client(
                "s3",
                endpoint_url=settings.s3_endpoint_url,
                region_name=settings.s3_region,
                aws_access_key_id=settings.s3_access_key_id,
                aws_secret_access_key=settings.s3_secret_access_key,
                config=cfg,
            )
            bucket = settings.s3_bucket_raw
            key = archive_path
            new_key = f"{key}.redacted"
            client.copy_object(Bucket=bucket, CopySource={"Bucket": bucket, "Key": key}, Key=new_key)
            client.delete_object(Bucket=bucket, Key=key)
            return {"s3_copied_to": new_key}
        except Exception as e:
            return {"s3_error": str(e)}
    return {"skipped": True, "reason": "not a local file and S3 not configured"}
