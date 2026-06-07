"""Postgres pool + redis client + a tiny forward-only migration runner.

T1 only wires connections and applies migrations on startup. Later tasks add the
DAO methods (orders/fills/positions/signals/...) on top of `pool`.
"""

from __future__ import annotations

import pathlib

import redis
from psycopg_pool import ConnectionPool

from .config import settings

_MIGRATIONS_DIR = pathlib.Path(__file__).resolve().parent.parent / "migrations"

pool: ConnectionPool | None = None
rds: redis.Redis | None = None


def connect() -> None:
    """Open the postgres pool and redis client. Idempotent."""
    global pool, rds
    if pool is None:
        pool = ConnectionPool(settings.database_url, min_size=1, max_size=8, open=False)
        pool.open(wait=True, timeout=10)
    if rds is None:
        rds = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    rds.ping()


def close() -> None:
    global pool, rds
    if pool is not None:
        pool.close()
        pool = None
    if rds is not None:
        rds.close()
        rds = None


def run_migrations() -> list[str]:
    """Apply un-applied migrations/*.sql in filename order, once each.

    Returns the versions applied on this call (empty when already up to date).
    """
    assert pool is not None, "call connect() first"
    with pool.connection() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " version TEXT PRIMARY KEY,"
            " applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        done = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}

    applied: list[str] = []
    for path in sorted(_MIGRATIONS_DIR.glob("*.sql")):
        if path.name in done:
            continue
        with pool.connection() as conn:  # one transaction per migration
            conn.execute(path.read_text())
            conn.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (path.name,))
        applied.append(path.name)
    return applied
