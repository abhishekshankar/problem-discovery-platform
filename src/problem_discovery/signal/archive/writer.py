"""Write immutable gzip JSONL batches to S3-compatible storage (PRD §6.2 Tier A)."""

from __future__ import annotations

import gzip
import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Iterator

from ..settings import SignalSettings, get_settings


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class RawRecordLine:
    """One line in a batch JSONL.gz matching PRD Tier A record shape."""

    external_id: str
    source: str
    captured_at: str
    source_timestamp: str | None
    raw_payload: dict[str, Any]
    collector_version: str
    scrape_run_id: str
    payload_hash: str

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "external_id": self.external_id,
            "source": self.source,
            "captured_at": self.captured_at,
            "source_timestamp": self.source_timestamp,
            "raw_payload": self.raw_payload,
            "collector_version": self.collector_version,
            "scrape_run_id": self.scrape_run_id,
            "payload_hash": self.payload_hash,
        }


def compute_payload_hash(raw_payload: dict[str, Any]) -> str:
    body = json.dumps(raw_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def archive_path_for_batch(source: str, captured_at: datetime, batch_id: str) -> str:
    """Path: /raw/{source}/{YYYY}/{MM}/{DD}/{batch_id}.jsonl.gz"""
    y = captured_at.strftime("%Y")
    m = captured_at.strftime("%m")
    d = captured_at.strftime("%d")
    safe_source = source.replace("/", "_")
    return f"raw/{safe_source}/{y}/{m}/{d}/{batch_id}.jsonl.gz"


class RawArchiveWriter:
    """Upload gzip JSONL to R2/S3."""

    def __init__(self, settings: SignalSettings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client = None

    def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            import boto3  # type: ignore[import-untyped]
            from botocore.config import Config  # type: ignore[import-untyped]
        except ImportError as e:
            raise RuntimeError("boto3 is required for archive upload. pip install boto3") from e

        if not self._settings.s3_access_key_id or not self._settings.s3_secret_access_key:
            raise RuntimeError("S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY (or AWS_*) must be set for archive writes")

        addressing = self._settings.s3_addressing_style
        config = Config(s3={"addressing_style": addressing})
        endpoint = self._settings.s3_endpoint_url
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            region_name=self._settings.s3_region,
            aws_access_key_id=self._settings.s3_access_key_id,
            aws_secret_access_key=self._settings.s3_secret_access_key,
            config=config,
        )
        return self._client

    def write_batch(
        self,
        source_name: str,
        lines: list[RawRecordLine],
        *,
        batch_id: str | None = None,
    ) -> str:
        """Compress records and upload; returns s3 key (archive_path)."""
        if not lines:
            raise ValueError("lines must not be empty")
        captured = _utc_now()
        bid = batch_id or str(uuid.uuid4())
        key = archive_path_for_batch(source_name, captured, bid)

        buf = BytesIO()
        with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as gz:
            for line in lines:
                gz.write((json.dumps(line.to_json_dict(), ensure_ascii=False) + "\n").encode("utf-8"))

        body = buf.getvalue()
        client = self._ensure_client()
        client.put_object(
            Bucket=self._settings.s3_bucket_raw,
            Key=key,
            Body=body,
            ContentType="application/gzip",
            ContentEncoding="gzip",
        )
        return key

    def write_batch_local(
        self,
        base_dir: str,
        source_name: str,
        lines: list[RawRecordLine],
        *,
        batch_id: str | None = None,
    ) -> str:
        """Dev fallback: write to local filesystem under base_dir mirroring S3 key layout."""
        from pathlib import Path

        if not lines:
            raise ValueError("lines must not be empty")
        captured = _utc_now()
        bid = batch_id or str(uuid.uuid4())
        key = archive_path_for_batch(source_name, captured, bid)
        path = Path(base_dir) / key
        path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(path, "wt", encoding="utf-8") as gz:
            for line in lines:
                gz.write(json.dumps(line.to_json_dict(), ensure_ascii=False) + "\n")
        return str(path)


def iter_lines_from_payloads(
    source: str,
    scrape_run_id: str,
    collector_version: str,
    payloads: Iterator[tuple[str, dict[str, Any], str | None, str | None]],
) -> list[RawRecordLine]:
    """Helper: (external_id, raw_payload, source_timestamp_iso, url) -> lines."""
    captured = _utc_now().isoformat()
    out: list[RawRecordLine] = []
    for external_id, raw_payload, source_ts, _url in payloads:
        ph = compute_payload_hash(raw_payload)
        out.append(
            RawRecordLine(
                external_id=external_id,
                source=source,
                captured_at=captured,
                source_timestamp=source_ts,
                raw_payload=raw_payload,
                collector_version=collector_version,
                scrape_run_id=scrape_run_id,
                payload_hash=ph,
            )
        )
    return out
