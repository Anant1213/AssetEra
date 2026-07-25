"""
PostgreSQL storage adapter for market OHLCV data.

Tables:
  us_prices        — US ETFs and fund constituent stocks
  us_equity_prices — US individual equities by market-cap category
                     (50 large / 50 mid / 50 small cap, NYSE/NASDAQ)

Set either POSTGRES_URL or DATABASE_URL to enable DB storage.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit, urlunsplit

import pandas as pd

try:
    import psycopg
except Exception:  # pragma: no cover - handled gracefully at runtime
    psycopg = None


logger = logging.getLogger(__name__)

_REQUIRED_COLS = ["Date", "Ticker", "Close", "Open", "High", "Low", "Adj Close", "Volume"]

# ── US prices (ETFs + fund stocks) ────────────────────────────────────
_US_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS us_prices (
    ticker TEXT NOT NULL,
    date TIMESTAMP NOT NULL,
    open DOUBLE PRECISION,
    high DOUBLE PRECISION,
    low DOUBLE PRECISION,
    close DOUBLE PRECISION,
    adj_close DOUBLE PRECISION,
    volume DOUBLE PRECISION,
    PRIMARY KEY (ticker, date)
);
"""

_US_UPSERT_SQL = """
INSERT INTO us_prices (
    ticker, date, open, high, low, close, adj_close, volume
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (ticker, date) DO UPDATE SET
    open = EXCLUDED.open,
    high = EXCLUDED.high,
    low = EXCLUDED.low,
    close = EXCLUDED.close,
    adj_close = EXCLUDED.adj_close,
    volume = EXCLUDED.volume;
"""

_US_SELECT_SQL = """
SELECT
    date AS "Date",
    ticker AS "Ticker",
    close AS "Close",
    open AS "Open",
    high AS "High",
    low AS "Low",
    adj_close AS "Adj Close",
    volume AS "Volume"
FROM us_prices
WHERE ticker = %s
ORDER BY date ASC;
"""

# ── US equity prices (individual stocks by market-cap category) ────────
_EQUITY_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS us_equity_prices (
    ticker TEXT NOT NULL,
    date TIMESTAMP NOT NULL,
    open DOUBLE PRECISION,
    high DOUBLE PRECISION,
    low DOUBLE PRECISION,
    close DOUBLE PRECISION,
    adj_close DOUBLE PRECISION,
    volume DOUBLE PRECISION,
    cap_category TEXT,
    PRIMARY KEY (ticker, date)
);
"""

_EQUITY_UPSERT_SQL = """
INSERT INTO us_equity_prices (
    ticker, date, open, high, low, close, adj_close, volume, cap_category
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (ticker, date) DO UPDATE SET
    open = EXCLUDED.open,
    high = EXCLUDED.high,
    low = EXCLUDED.low,
    close = EXCLUDED.close,
    adj_close = EXCLUDED.adj_close,
    volume = EXCLUDED.volume,
    cap_category = EXCLUDED.cap_category;
"""

_EQUITY_SELECT_SQL = """
SELECT
    date AS "Date",
    ticker AS "Ticker",
    close AS "Close",
    open AS "Open",
    high AS "High",
    low AS "Low",
    adj_close AS "Adj Close",
    volume AS "Volume",
    cap_category AS "CapCategory"
FROM us_equity_prices
WHERE ticker = %s
ORDER BY date ASC;
"""

_EQUITY_SELECT_ALL_SQL = """
SELECT
    date AS "Date",
    ticker AS "Ticker",
    close AS "Close",
    open AS "Open",
    high AS "High",
    low AS "Low",
    adj_close AS "Adj Close",
    volume AS "Volume",
    cap_category AS "CapCategory"
FROM us_equity_prices
{where_clause}
ORDER BY ticker, date ASC;
"""

_schema_ready = False
_equity_schema_ready = False


def postgres_url() -> str:
    return os.getenv("POSTGRES_URL", "").strip() or os.getenv("DATABASE_URL", "").strip()


def redacted_postgres_url() -> str:
    """Return a log-safe PostgreSQL URL with credentials removed."""
    url = postgres_url()
    if not url:
        return ""
    try:
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        port = f":{parsed.port}" if parsed.port else ""
        netloc = f"{host}{port}"
        return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))
    except Exception:
        return "<configured>"


def is_enabled() -> bool:
    return bool(postgres_url())


def _connect():
    if psycopg is None:
        raise RuntimeError("psycopg is not installed. Add psycopg[binary] to requirements.")

    url = postgres_url()
    if not url:
        raise RuntimeError("POSTGRES_URL or DATABASE_URL is not set")

    # Supabase shared pooler/pgBouncer transaction mode is incompatible with
    # server-side prepared statements. Disable psycopg auto-prepare.
    return psycopg.connect(url, prepare_threshold=None)


def get_connection():
    """Return a live, raw psycopg3 connection.

    The caller owns the connection lifecycle (commit/close). Unlike the
    ``with _connect() as conn`` pattern used internally by this module, this
    returns an open connection that is *not* auto-closed, so callers that
    manage their own cursors/transactions (e.g. portfolio_store) can use it.
    """
    return _connect()


def _ensure_schema() -> bool:
    """Ensure us_prices table exists."""
    global _schema_ready

    if _schema_ready:
        return True

    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(_US_SCHEMA_SQL)
            conn.commit()
        _schema_ready = True
        return True
    except Exception as e:
        logger.warning("PostgreSQL us_prices schema init failed: %s", e)
        return False


def _ensure_equity_schema() -> bool:
    """Ensure us_equity_prices table exists."""
    global _equity_schema_ready

    if _equity_schema_ready:
        return True

    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(_EQUITY_SCHEMA_SQL)
            conn.commit()
        _equity_schema_ready = True
        return True
    except Exception as e:
        logger.warning("PostgreSQL us_equity_prices schema init failed: %s", e)
        return False


def _normalise_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    for c in _REQUIRED_COLS:
        if c not in out.columns:
            out[c] = out["Close"] if c == "Adj Close" and "Close" in out.columns else None

    out = out[_REQUIRED_COLS]
    out["Date"] = pd.to_datetime(out["Date"], errors="coerce", utc=True).dt.tz_convert(None)
    out["Ticker"] = out["Ticker"].fillna("").astype(str).str.upper()

    numeric_cols = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
    for c in numeric_cols:
        out[c] = pd.to_numeric(out[c], errors="coerce")

    out = out.dropna(subset=["Date", "Ticker", "Close"])
    out = out[out["Ticker"] != ""]
    out = out.drop_duplicates(subset=["Date", "Ticker"]).sort_values(["Ticker", "Date"])
    return out.reset_index(drop=True)


# ── US prices API ─────────────────────────────────────────────────────

def read_ticker_prices(ticker: str) -> Optional[pd.DataFrame]:
    if not is_enabled() or not _ensure_schema():
        return None

    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(_US_SELECT_SQL, (ticker.upper(),))
                rows = cur.fetchall()

        if not rows:
            return None

        df = pd.DataFrame(rows, columns=_REQUIRED_COLS)
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce", utc=True).dt.tz_convert(None)
        return df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)
    except Exception as e:
        logger.warning("PostgreSQL read failed for %s: %s", ticker, e)
        return None


def upsert_prices(df: pd.DataFrame) -> bool:
    if df is None or df.empty:
        return False
    if not is_enabled() or not _ensure_schema():
        return False

    try:
        norm = _normalise_df(df)
        if norm.empty:
            return False

        records = [
            (
                r["Ticker"],
                r["Date"].to_pydatetime(),
                None if pd.isna(r["Open"]) else float(r["Open"]),
                None if pd.isna(r["High"]) else float(r["High"]),
                None if pd.isna(r["Low"]) else float(r["Low"]),
                None if pd.isna(r["Close"]) else float(r["Close"]),
                None if pd.isna(r["Adj Close"]) else float(r["Adj Close"]),
                None if pd.isna(r["Volume"]) else float(r["Volume"]),
            )
            for _, r in norm.iterrows()
        ]

        with _connect() as conn:
            with conn.cursor() as cur:
                cur.executemany(_US_UPSERT_SQL, records)
            conn.commit()

        return True
    except Exception as e:
        logger.warning("PostgreSQL upsert failed: %s", e)
        return False


def reset_us_prices() -> bool:
    if not is_enabled() or not _ensure_schema():
        return False

    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE us_prices;")
            conn.commit()
        return True
    except Exception as e:
        logger.warning("PostgreSQL truncate failed: %s", e)
        return False


def load_csv_file(path: Path) -> tuple[bool, int]:
    """Load a single CSV file into us_prices. Returns (success, row_count)."""
    try:
        df = pd.read_csv(path, parse_dates=["Date"])
        ticker = path.name.split("_")[0].upper()
        if "Ticker" not in df.columns:
            df["Ticker"] = ticker
        else:
            df["Ticker"] = df["Ticker"].fillna(ticker)

        norm = _normalise_df(df)
        ok = upsert_prices(norm)
        return ok, len(norm)
    except Exception as e:
        logger.warning("Failed loading CSV %s: %s", path, e)
        return False, 0


# ── US equity prices API ──────────────────────────────────────────────

def upsert_equity_prices(df: pd.DataFrame, cap_category: str) -> bool:
    """Insert/update US equity OHLCV rows into us_equity_prices."""
    if df is None or df.empty:
        return False
    if not is_enabled() or not _ensure_equity_schema():
        return False

    try:
        norm = _normalise_df(df)
        if norm.empty:
            return False

        records = [
            (
                r["Ticker"],
                r["Date"].to_pydatetime(),
                None if pd.isna(r["Open"]) else float(r["Open"]),
                None if pd.isna(r["High"]) else float(r["High"]),
                None if pd.isna(r["Low"]) else float(r["Low"]),
                None if pd.isna(r["Close"]) else float(r["Close"]),
                None if pd.isna(r["Adj Close"]) else float(r["Adj Close"]),
                None if pd.isna(r["Volume"]) else float(r["Volume"]),
                cap_category.upper(),
            )
            for _, r in norm.iterrows()
        ]

        with _connect() as conn:
            with conn.cursor() as cur:
                cur.executemany(_EQUITY_UPSERT_SQL, records)
            conn.commit()

        return True
    except Exception as e:
        logger.warning("PostgreSQL equity upsert failed: %s", e)
        return False


def read_equity_ticker(ticker: str) -> Optional[pd.DataFrame]:
    """Read all rows for a single US equity ticker."""
    if not is_enabled() or not _ensure_equity_schema():
        return None

    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(_EQUITY_SELECT_SQL, (ticker.upper(),))
                rows = cur.fetchall()

        if not rows:
            return None

        cols = _REQUIRED_COLS + ["CapCategory"]
        df = pd.DataFrame(rows, columns=cols)
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce", utc=True).dt.tz_convert(None)
        return df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)
    except Exception as e:
        logger.warning("PostgreSQL equity read failed for %s: %s", ticker, e)
        return None


def read_equity_prices(tickers: list[str] | None = None, cap_category: str | None = None) -> Optional[pd.DataFrame]:
    """
    Read US equity prices for a list of tickers or an entire cap category.
    Returns DataFrame with Date, Ticker, OHLCV, CapCategory columns.
    """
    if not is_enabled() or not _ensure_equity_schema():
        return None

    try:
        conditions = []
        params = []

        if tickers:
            placeholders = ",".join(["%s"] * len(tickers))
            conditions.append(f"ticker IN ({placeholders})")
            params.extend([t.upper() for t in tickers])

        if cap_category:
            conditions.append("cap_category = %s")
            params.append(cap_category.upper())

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = _EQUITY_SELECT_ALL_SQL.format(where_clause=where)

        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()

        if not rows:
            return None

        cols = _REQUIRED_COLS + ["CapCategory"]
        df = pd.DataFrame(rows, columns=cols)
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce", utc=True).dt.tz_convert(None)
        return df.dropna(subset=["Date"]).sort_values(["Ticker", "Date"]).reset_index(drop=True)
    except Exception as e:
        logger.warning("PostgreSQL equity bulk read failed: %s", e)
        return None


def reset_equity_prices() -> bool:
    if not is_enabled() or not _ensure_equity_schema():
        return False

    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE us_equity_prices;")
            conn.commit()
        return True
    except Exception as e:
        logger.warning("PostgreSQL equity truncate failed: %s", e)
        return False


# ── Backwards compatibility aliases ───────────────────────────────────
reset_market_prices = reset_us_prices
# Legacy NSE names — point to equity equivalents
upsert_nse_prices  = upsert_equity_prices
read_nse_ticker    = read_equity_ticker
read_nse_prices    = read_equity_prices
reset_nse_prices   = reset_equity_prices
