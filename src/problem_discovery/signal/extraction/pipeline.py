"""Batch extraction: Pass 2 classifier → Haiku gate → Pass 3 LLM → verify → embed → Postgres."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from psycopg.rows import dict_row

from ..db import connection
from ..settings import SignalSettings, get_settings
from .batch_run import (
    download_batch_results_jsonl,
    parse_batch_jsonl_to_extractions,
    poll_batch_until_ended,
    submit_extraction_batch,
)
from .classifier import ProblemSignalClassifier
from .promotion import get_effective_candidate_rollout_fraction
from .embed import embed_one
from .llm_extract import (
    extract_problem_from_raw,
    haiku_problem_signal_gate,
    stub_extraction_for_dev,
)
from ..privacy import author_pseudonym_from_payload
from .verify_quote import flatten_raw_text, quote_is_verified

EXTRACTOR_VERSION = "0.1.0"


def _prompt_hash(variant: str = "default") -> str:
    return hashlib.sha256(f"signal_extractor_v0.1::{variant}".encode()).hexdigest()


def _use_canary_slice(raw_signal_id: int, fraction: float) -> bool:
    if fraction <= 0:
        return False
    h = hashlib.sha256(str(raw_signal_id).encode()).hexdigest()
    bucket = int(h[:8], 16) % 10_000
    return bucket < int(fraction * 10_000)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


_BATCH_CHUNK = 2000


def _eu_author_pseudonym(raw_payload: Any, *, is_eu_origin: bool, s: SignalSettings) -> str | None:
    if not is_eu_origin:
        return None
    salt = (s.signal_pseudonym_salt or "").strip()
    if not salt:
        return None
    return author_pseudonym_from_payload(raw_payload, salt)


def _insert_extracted_problem(
    cur: Any,
    *,
    rid: int,
    run_id: str,
    data: dict[str, Any],
    verified: bool,
    is_positive: bool,
    emb_vec: list[float] | None,
    author_pseudonym: str | None = None,
) -> None:
    """Insert one extracted_problems row; embedding NULL when no vector (audit-only rows)."""
    eq = data.get("exact_quote")
    if emb_vec is not None:
        cur.execute(
            """
            INSERT INTO extracted_problems (
              raw_signal_id, extraction_run_id, is_problem_signal, problem_statement, exact_quote,
              quote_verified, specificity_score, wtp_level, wtp_evidence, layer, domain_tags,
              buyer_hint, workaround_described, admiralty_source_reliability, admiralty_info_credibility,
              author_pseudonym, embedding
            )
            VALUES (
              %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector
            )
            """,
            (
                rid,
                run_id,
                is_positive,
                data.get("problem_statement"),
                eq,
                verified,
                data.get("specificity_score"),
                data.get("wtp_level"),
                data.get("wtp_evidence"),
                data.get("layer"),
                data.get("domain_tags") or [],
                data.get("buyer_hint"),
                data.get("workaround_described"),
                (data.get("admiralty_source_reliability") or "C")[:1],
                data.get("admiralty_info_credibility") or 3,
                author_pseudonym,
                emb_vec,
            ),
        )
    else:
        cur.execute(
            """
            INSERT INTO extracted_problems (
              raw_signal_id, extraction_run_id, is_problem_signal, problem_statement, exact_quote,
              quote_verified, specificity_score, wtp_level, wtp_evidence, layer, domain_tags,
              buyer_hint, workaround_described, admiralty_source_reliability, admiralty_info_credibility,
              author_pseudonym, embedding
            )
            VALUES (
              %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULL
            )
            """,
            (
                rid,
                run_id,
                is_positive,
                data.get("problem_statement"),
                eq,
                verified,
                data.get("specificity_score"),
                data.get("wtp_level"),
                data.get("wtp_evidence"),
                data.get("layer"),
                data.get("domain_tags") or [],
                data.get("buyer_hint"),
                data.get("workaround_described"),
                (data.get("admiralty_source_reliability") or "C")[:1],
                data.get("admiralty_info_credibility") or 3,
                author_pseudonym,
            ),
        )


def run_extraction_batch(
    *,
    limit: int = 50,
    settings: SignalSettings | None = None,
    source_label: str = "reddit",
    raw_signal_ids: list[int] | None = None,
    use_message_batch: bool = False,
    batch_max_wait_sec: float = 7200.0,
) -> dict[str, Any]:
    s = settings or get_settings()
    if not s.database_url:
        raise RuntimeError("DATABASE_URL is required")

    clf = ProblemSignalClassifier(settings=s)
    run_id = uuid.uuid4()
    processed = 0
    skipped_classifier = 0
    skipped_llm = 0
    skipped_haiku = 0
    canary_count = 0

    with connection(autocommit=False) as conn:
        try:
            from pgvector.psycopg import register_vector
        except ImportError:
            register_vector = None  # type: ignore[assignment]
        if register_vector:
            register_vector(conn)

        prompt_variant = "default"
        ph = _prompt_hash(prompt_variant)
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO extraction_runs (
                  id, extractor_version, prompt_hash, model_identifier, started_at, raw_records_processed, promoted, canary_fraction
                )
                VALUES (%s, %s, %s, %s, NOW(), 0, FALSE, %s)
                """,
                (
                    str(run_id),
                    EXTRACTOR_VERSION,
                    ph,
                    s.anthropic_model_extract if not s.extraction_use_stub else "stub",
                    s.extraction_canary_fraction,
                ),
            )

        with conn.cursor(row_factory=dict_row) as cur:
            if raw_signal_ids:
                cur.execute(
                    """
                    SELECT r.id, r.raw_payload, r.source_id, COALESCE(src.is_eu_origin, FALSE) AS is_eu_origin
                    FROM raw_signals_index r
                    JOIN sources src ON src.id = r.source_id
                    WHERE r.id = ANY(%s)
                    ORDER BY r.captured_at ASC
                    """,
                    (raw_signal_ids,),
                )
            else:
                cur.execute(
                    """
                    SELECT r.id, r.raw_payload, r.source_id, COALESCE(src.is_eu_origin, FALSE) AS is_eu_origin
                    FROM raw_signals_index r
                    JOIN sources src ON src.id = r.source_id
                    LEFT JOIN extracted_problems e ON e.raw_signal_id = r.id AND e.is_problem_signal IS TRUE
                    WHERE e.id IS NULL
                    ORDER BY r.captured_at ASC
                    LIMIT %s
                    """,
                    (limit,),
                )
            rows = cur.fetchall()

        promo_frac = get_effective_candidate_rollout_fraction(conn, s)

        # --- Message Batches path (Sonnet discount) ---
        if (
            use_message_batch
            and s.anthropic_api_key
            and not s.extraction_use_stub
        ):
            trip_meta: list[tuple[int, str, str, Any, bool]] = []
            for row in rows:
                rid = int(row["id"])
                raw_payload = row["raw_payload"]
                is_eu = bool(row.get("is_eu_origin"))
                raw_text = flatten_raw_text(raw_payload)
                if len(raw_text.strip()) < 20:
                    continue
                use_candidate = promo_frac >= (1.0 - 1e-9) or _use_canary_slice(rid, promo_frac)
                variant = (s.candidate_prompt_id or "canary") if use_candidate else "default"
                cr = clf.predict(raw_text)
                if not cr.is_problem_signal:
                    skipped_classifier += 1
                    continue
                if s.extraction_haiku_gate:
                    try:
                        if not haiku_problem_signal_gate(
                            source_label=source_label, raw_text=raw_text, settings=s
                        ):
                            skipped_haiku += 1
                            continue
                    except Exception:
                        pass
                trip_meta.append((rid, variant, raw_text, raw_payload, is_eu))
                if use_candidate:
                    canary_count += 1

            parsed_all: dict[str, dict[str, Any]] = {}
            batch_ids: list[str] = []
            if trip_meta:
                for i in range(0, len(trip_meta), _BATCH_CHUNK):
                    chunk = trip_meta[i : i + _BATCH_CHUNK]
                    trip = [(a, b, c) for a, b, c, _, _ in chunk]
                    bid = submit_extraction_batch(trip, source_label=source_label, settings=s)
                    batch_ids.append(bid)
                    meta = poll_batch_until_ended(
                        bid,
                        max_wait_sec=batch_max_wait_sec,
                        settings=s,
                    )
                    if not meta.get("results_url"):
                        raise RuntimeError(f"Batch {bid} ended without results_url")
                    lines = download_batch_results_jsonl(meta["results_url"], settings=s)
                    parsed_all.update(parse_batch_jsonl_to_extractions(lines))

            for rid, _variant, raw_text, raw_payload, is_eu in trip_meta:
                data = parsed_all.get(str(rid), {})
                ap = _eu_author_pseudonym(raw_payload, is_eu_origin=is_eu, s=s)
                if not data.get("is_problem_signal"):
                    skipped_llm += 1
                    continue
                eq = data.get("exact_quote")
                verified = quote_is_verified(eq, raw_payload)
                if not verified:
                    with conn.cursor() as cur:
                        _insert_extracted_problem(
                            cur,
                            rid=rid,
                            run_id=str(run_id),
                            data=data,
                            verified=False,
                            is_positive=False,
                            emb_vec=None,
                            author_pseudonym=ap,
                        )
                    processed += 1
                    skipped_llm += 1
                    continue
                try:
                    emb_vec = embed_one(data.get("problem_statement") or raw_text[:500], settings=s)
                except Exception:
                    emb_vec = [0.0] * 1024
                with conn.cursor() as cur:
                    _insert_extracted_problem(
                        cur,
                        rid=rid,
                        run_id=str(run_id),
                        data=data,
                        verified=True,
                        is_positive=True,
                        emb_vec=emb_vec,
                        author_pseudonym=ap,
                    )
                processed += 1

            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE extraction_runs
                    SET completed_at = NOW(), raw_records_processed = %s
                    WHERE id = %s
                    """,
                    (processed, str(run_id)),
                )
            conn.commit()
            return {
                "extraction_run_id": str(run_id),
                "extractor_version": EXTRACTOR_VERSION,
                "processed": processed,
                "skipped_classifier": skipped_classifier,
                "skipped_haiku": skipped_haiku,
                "skipped_llm_or_negative": skipped_llm,
                "canary_records": canary_count,
                "message_batches": batch_ids,
                "batch_mode": True,
            }

        for row in rows:
            rid = int(row["id"])
            raw_payload = row["raw_payload"]
            is_eu = bool(row.get("is_eu_origin"))
            ap = _eu_author_pseudonym(raw_payload, is_eu_origin=is_eu, s=s)
            raw_text = flatten_raw_text(raw_payload)
            if len(raw_text.strip()) < 20:
                continue

            use_candidate = promo_frac >= (1.0 - 1e-9) or _use_canary_slice(rid, promo_frac)
            variant = (s.candidate_prompt_id or "canary") if use_candidate else "default"
            if use_candidate:
                canary_count += 1

            cr = clf.predict(raw_text)
            if not cr.is_problem_signal:
                skipped_classifier += 1
                continue

            if s.extraction_haiku_gate and not s.extraction_use_stub and s.anthropic_api_key:
                try:
                    if not haiku_problem_signal_gate(source_label=source_label, raw_text=raw_text, settings=s):
                        skipped_haiku += 1
                        continue
                except Exception:
                    pass

            if s.extraction_use_stub or not s.anthropic_api_key:
                data = stub_extraction_for_dev(raw_text)
            else:
                try:
                    data = extract_problem_from_raw(
                        source_label=source_label,
                        raw_text=raw_text,
                        settings=s,
                        prompt_variant=variant,
                    )
                except Exception:
                    skipped_llm += 1
                    continue

            if not data.get("is_problem_signal"):
                skipped_llm += 1
                continue

            eq = data.get("exact_quote")
            verified = quote_is_verified(eq, raw_payload)
            if not verified:
                with conn.cursor() as cur:
                    _insert_extracted_problem(
                        cur,
                        rid=rid,
                        run_id=str(run_id),
                        data=data,
                        verified=False,
                        is_positive=False,
                        emb_vec=None,
                        author_pseudonym=ap,
                    )
                processed += 1
                skipped_llm += 1
                continue

            try:
                emb_vec = embed_one(data.get("problem_statement") or raw_text[:500], settings=s)
            except Exception:
                emb_vec = [0.0] * 1024

            with conn.cursor() as cur:
                _insert_extracted_problem(
                    cur,
                    rid=rid,
                    run_id=str(run_id),
                    data=data,
                    verified=True,
                    is_positive=True,
                    emb_vec=emb_vec,
                    author_pseudonym=ap,
                )
            processed += 1

        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE extraction_runs
                SET completed_at = NOW(), raw_records_processed = %s
                WHERE id = %s
                """,
                (processed, str(run_id)),
            )

        conn.commit()

    return {
        "extraction_run_id": str(run_id),
        "extractor_version": EXTRACTOR_VERSION,
        "processed": processed,
        "skipped_classifier": skipped_classifier,
        "skipped_haiku": skipped_haiku,
        "skipped_llm_or_negative": skipped_llm,
        "canary_records": canary_count,
        "batch_mode": False,
    }
