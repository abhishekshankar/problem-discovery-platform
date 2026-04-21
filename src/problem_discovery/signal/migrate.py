"""Apply SQL migrations from migrations/ (run with DATABASE_URL set)."""

from __future__ import annotations

import sys
from pathlib import Path

from .db import connection
from .settings import get_settings


def apply_all() -> None:
    s = get_settings()
    if not s.database_url:
        print("DATABASE_URL is not set", file=sys.stderr)
        sys.exit(1)
    root = Path(__file__).resolve().parents[1]
    migrations_dir = root / "migrations"
    files = sorted(migrations_dir.glob("*.sql"))
    if not files:
        print("No migrations found", file=sys.stderr)
        sys.exit(1)
    sql_blob = "\n\n".join(f.read_text(encoding="utf-8") for f in files)
    with connection(autocommit=True) as conn:
        # psycopg3 Connection.execute runs multiple statements in one transaction
        conn.execute(sql_blob)
    print(f"Applied {len(files)} migration file(s).")


if __name__ == "__main__":
    apply_all()
