"""Postgres connection helpers (psycopg 3)."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row

from .settings import SignalSettings, get_settings


def connect(settings: SignalSettings | None = None, *, autocommit: bool = False) -> psycopg.Connection:
    s = settings or get_settings()
    if not s.database_url:
        raise RuntimeError("DATABASE_URL is not set")
    conn = psycopg.connect(s.database_url, autocommit=autocommit)
    return conn


@contextmanager
def connection(settings: SignalSettings | None = None, *, autocommit: bool = False) -> Iterator[psycopg.Connection]:
    conn = connect(settings=settings, autocommit=autocommit)
    try:
        yield conn
    finally:
        conn.close()


def fetch_all(conn: psycopg.Connection, sql: str, params: tuple[Any, ...] | None = None) -> list[dict[str, Any]]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params or ())
        return list(cur.fetchall())


def fetch_one(conn: psycopg.Connection, sql: str, params: tuple[Any, ...] | None = None) -> dict[str, Any] | None:
    rows = fetch_all(conn, sql, params)
    return rows[0] if rows else None


def execute(conn: psycopg.Connection, sql: str, params: tuple[Any, ...] | None = None) -> None:
    with conn.cursor() as cur:
        cur.execute(sql, params or ())
