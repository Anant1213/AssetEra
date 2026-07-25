"""
backend.db.duckdb_store
────────────────────
DuckDB connection factory with S3/httpfs pre-configured.

This module is the query engine for all analytics reads when the S3
backend is active.  Each OS thread gets its own DuckDB connection
(DuckDB connections are not thread-safe to share).

Usage:
    from backend.db.duckdb_store import query_df, parquet_uri

    df = query_df(
        "SELECT * FROM read_parquet(?) WHERE ticker = ?",
        [parquet_uri("market/us_prices.parquet"), "SPY"],
    )
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any, Sequence

import pandas as pd

from backend.db.s3_store import BUCKET, REGION, s3_uri

logger = logging.getLogger(__name__)

_local = threading.local()
_install_done = False
_install_lock = threading.Lock()


# ── Connection factory ────────────────────────────────────────────────

def _configure(conn) -> None:
    """Install httpfs and apply S3 credentials to a fresh DuckDB connection.

    httpfs is only needed to read from S3. When S3 is not enabled (local-only
    mode) we skip the INSTALL/LOAD entirely — that network-backed extension
    install is pure cold-start latency for queries that only touch local
    parquet files.
    """
    try:
        from backend.db.s3_store import is_enabled as _s3_on
        s3_active = _s3_on()
    except Exception:
        s3_active = False

    if not s3_active:
        return

    global _install_done
    # Install httpfs extension once per process (it's cached on disk after first install)
    with _install_lock:
        if not _install_done:
            try:
                conn.execute("INSTALL httpfs;")
            except Exception:
                pass  # already installed
            _install_done = True

    conn.execute("LOAD httpfs;")

    region = REGION or os.getenv("AWS_REGION", "us-east-1")
    conn.execute(f"SET s3_region = '{region}';")

    key_id = os.getenv("AWS_ACCESS_KEY_ID", "")
    secret = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    token  = os.getenv("AWS_SESSION_TOKEN", "")

    if key_id:
        conn.execute(f"SET s3_access_key_id = '{key_id}';")
        conn.execute(f"SET s3_secret_access_key = '{secret}';")
    if token:
        conn.execute(f"SET s3_session_token = '{token}';")


def get_conn():
    """
    Return a per-thread DuckDB connection pre-configured for S3 access.
    The connection is created lazily on first call per thread.
    """
    if getattr(_local, "conn", None) is None:
        import duckdb
        conn = duckdb.connect()
        _configure(conn)
        _local.conn = conn
    return _local.conn


def reset_conn() -> None:
    """Close and drop the current thread's connection (useful after credential rotation)."""
    conn = getattr(_local, "conn", None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
        _local.conn = None


# ── Query helpers ─────────────────────────────────────────────────────

def query_df(sql: str, params: Sequence[Any] | None = None) -> pd.DataFrame:
    """
    Execute a DuckDB SQL query and return results as a DataFrame.
    Params are passed positionally via ?  placeholders.
    """
    try:
        conn = get_conn()
        if params:
            result = conn.execute(sql, list(params))
        else:
            result = conn.execute(sql)
        return result.df()
    except Exception as e:
        logger.error("DuckDB query failed: %s | SQL: %.300s", e, sql)
        return pd.DataFrame()


def parquet_uri(key: str) -> str:
    """Return the s3:// URI for a given key (used in read_parquet() calls)."""
    return s3_uri(key)


# ── Typed read helpers ────────────────────────────────────────────────

def read_market_parquet(key: str, where: str = "", params: Sequence[Any] | None = None) -> pd.DataFrame:
    """
    Read a market data parquet file with an optional WHERE clause.

    Example:
        df = read_market_parquet("market/us_prices.parquet", "WHERE ticker = ?", ["SPY"])
    """
    uri = parquet_uri(key)
    sql = f"SELECT * FROM read_parquet('{uri}') {where}"
    return query_df(sql, params)


def read_analytics_parquet(
    module: str,
    market: str,
    where: str = "",
    params: Sequence[Any] | None = None,
) -> pd.DataFrame:
    """
    Read an analytics module parquet file.
    module: 'returns' | 'risk' | 'momentum' | 'zscore' | 'technical'
    market: 'US' | 'US_EQ'
    """
    from backend.db.s3_store import analytics_key
    key = analytics_key(module, market)
    uri = parquet_uri(key)
    sql = f"SELECT * FROM read_parquet('{uri}') {where}"
    return query_df(sql, params)


def max_date_in_parquet(key: str, market: str | None = None) -> "pd.Timestamp | None":
    """Return the MAX(date) in a parquet file, optionally filtered by market."""
    uri = parquet_uri(key)
    where = f"WHERE market = '{market}'" if market else ""
    sql = f"SELECT MAX(date) AS max_date FROM read_parquet('{uri}') {where}"
    df = query_df(sql)
    if df.empty or df["max_date"].iloc[0] is None:
        return None
    return pd.Timestamp(df["max_date"].iloc[0])
