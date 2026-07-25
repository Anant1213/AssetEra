"""
Market data layer — S3-first data layer with fallback to yfinance.

Reads OHLCV data from S3 curated zone (created by datalayer ingest workers).
Falls back to yfinance if S3 is not configured.
"""

import time
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from datetime import date, timedelta

import pandas as pd
import numpy as np
import yfinance as yf

# ── Config ────────────────────────────────────────────────────────────
DEFAULT_PERIOD   = "2y"
DEFAULT_INTERVAL = "1d"

CACHE_TTL_SEC          = 300   # in-memory TTL: 5 minutes
MAX_TICKERS_PER_REQUEST = 24

ROOT_DIR       = Path(__file__).resolve().parent.parent
DISK_CACHE_DIR = ROOT_DIR / "data_cache"
DISK_CACHE_DIR.mkdir(parents=True, exist_ok=True)

DENYLIST     = {"VIX", "VIXY", "VIXM"}
DENY_PREFIXES = {"^"}

# Import all tickers from datalayer universe for custom portfolio builder
try:
    from datalayer.schemas import (
        EQUITIES_LARGE, EQUITIES_MID, EQUITIES_SMALL,
        ETF_TICKERS, FIXED_INCOME_TICKERS
    )
    _UNIVERSE_TICKERS = set(
        list(EQUITIES_LARGE) + list(EQUITIES_MID) + list(EQUITIES_SMALL) +
        list(ETF_TICKERS) + list(FIXED_INCOME_TICKERS)
    )
    # Direct symbol → asset-class map so S3 reads hit ONE key instead of probing
    # equities, etf and fixed_income in sequence (three remote round-trips, two
    # of them guaranteed misses) for every ticker.
    try:
        from datalayer.schemas import ASSET_EQUITIES, ASSET_ETF, ASSET_FIXED_INCOME
        _SYMBOL_ASSET_CLASS: Dict[str, str] = {}
        for _t in list(EQUITIES_LARGE) + list(EQUITIES_MID) + list(EQUITIES_SMALL):
            _SYMBOL_ASSET_CLASS[_t.upper()] = ASSET_EQUITIES
        for _t in ETF_TICKERS:
            _SYMBOL_ASSET_CLASS[_t.upper()] = ASSET_ETF
        for _t in FIXED_INCOME_TICKERS:
            _SYMBOL_ASSET_CLASS[_t.upper()] = ASSET_FIXED_INCOME
    except Exception:
        _SYMBOL_ASSET_CLASS = {}
except Exception:
    _UNIVERSE_TICKERS = set()
    _SYMBOL_ASSET_CLASS = {}

# Original ALLOWLIST for backward compatibility
ALLOWLIST = {
    # Market ETFs (Market Watch)
    "SPY", "QQQ", "DIA", "IWM", "RSP",
    "XLK", "XLF", "XLE",
    "AGG", "HYG", "UUP", "GLD", "USO",
    # Fund constituents (Fund Backtester)
    "LQD", "IEF", "VEA", "VWO",
    "NVDA", "AVGO", "MSFT", "KLAC", "CDNS",
    "ETN", "PH", "HEI", "EME", "PWR", "FAST", "BWXT",
    "IDCC", "RDNT", "DY", "GPI", "ACLS", "TTMI", "AGM",
    "APH", "GWW", "BSX",
} | _UNIVERSE_TICKERS

# Small curated list for the decorative animated ticker tape shown at the top
# of pages. Keep this tiny: the tape is cosmetic and must NEVER trigger a fetch
# of the full ALLOWLIST (~200 symbols), which was the primary cause of slow
# page loads (a serial per-ticker cache/staleness/yfinance loop on every load).
TAPE_TICKERS = [
    "SPY", "QQQ", "DIA", "IWM", "AGG",
    "NVDA", "MSFT", "AVGO", "LQD", "VEA",
]

PERIODS   = ["6mo", "1y", "2y", "5y", "max"]
INTERVALS = ["1d", "1wk", "1mo"]

# Optional lightweight timing instrumentation. Enable by setting env
# ASSETERA_PERF_LOG=1. Logs durations only — never ticker payloads or secrets.
import os as _os
_PERF_LOG = _os.getenv("ASSETERA_PERF_LOG", "").strip().lower() in ("1", "true", "yes")


def _perf(label: str, start: float) -> None:
    if _PERF_LOG:
        logger.info("perf %s: %.3fs", label, time.time() - start)

# ── Logging ───────────────────────────────────────────────────────────
for _n in ("yfinance", "urllib3", "requests", "peewee"):
    logging.getLogger(_n).setLevel(logging.CRITICAL)

logger = logging.getLogger(__name__)

def _s3_enabled() -> bool:
    try:
        from datalayer.s3 import is_configured
        return is_configured()
    except Exception:
        return False

_USE_S3 = _s3_enabled()
if _USE_S3:
    logger.info("Market store: S3 mode enabled")

# ── In-memory cache ───────────────────────────────────────────────────
_mem_cache: Dict[Tuple, Tuple[float, pd.DataFrame, Dict]] = {}


# ── Helpers ───────────────────────────────────────────────────────────
def _is_denied(sym: str) -> bool:
    s = (sym or "").strip().upper()
    return s in DENYLIST or any(s.startswith(p) for p in DENY_PREFIXES)


def _safe_name(t: str) -> str:
    return t.replace("^", "_").replace("/", "_").replace(":", "_")


def _cache_path(ticker: str, interval: str) -> Path:
    return DISK_CACHE_DIR / f"{_safe_name(ticker)}_{interval}.csv"


def _period_to_days(period: str) -> Optional[int]:
    return {"6mo": 182, "1y": 365, "2y": 730, "5y": 1825}.get(period.lower())


def _coerce_naive_utc_inplace(df: pd.DataFrame) -> None:
    if "Date" not in df.columns:
        return
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce", utc=True).dt.tz_convert(None)


def _trim_period(df: pd.DataFrame, period: str) -> pd.DataFrame:
    if df.empty or "Date" not in df.columns:
        return df
    days = _period_to_days(period)
    if days is None:
        return df
    cutoff = df["Date"].max() - pd.Timedelta(days=days)
    return df[df["Date"] >= cutoff]


def _last_business_day() -> date:
    """Return the most recent completed business day (Mon-Fri)."""
    d = date.today()
    # If today is before 4pm ET we consider yesterday's close as latest
    # Simple heuristic: roll back from today until we hit Mon-Fri
    while d.weekday() >= 5:  # 5=Sat, 6=Sun
        d -= timedelta(days=1)
    # If today itself is a weekday, yesterday's close is the last complete day
    if d == date.today() and d.weekday() < 5:
        d -= timedelta(days=1)
        while d.weekday() >= 5:
            d -= timedelta(days=1)
    return d


# ── Disk I/O ──────────────────────────────────────────────────────────
_REQUIRED_COLS = ["Date", "Ticker", "Close", "Open", "High", "Low", "Adj Close", "Volume"]


def _read_disk(ticker: str) -> Optional[pd.DataFrame]:
    path = _cache_path(ticker, "1d")
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path, parse_dates=["Date"])
        _coerce_naive_utc_inplace(df)
        for c in _REQUIRED_COLS:
            if c not in df.columns:
                df[c] = df["Close"] if c == "Adj Close" else (ticker if c == "Ticker" else np.nan)
        return df[_REQUIRED_COLS].sort_values("Date").reset_index(drop=True)
    except Exception as e:
        logger.warning("Failed reading %s: %s", path, e)
        return None


def _persist_cache(ticker: str, df: pd.DataFrame) -> None:
    """Persist canonical daily data to CSV cache."""
    if df is None or df.empty:
        return
    _coerce_naive_utc_inplace(df)
    path = _cache_path(ticker, "1d")
    df.to_csv(path, index=False)


def _read_from_s3(ticker: str) -> Optional[pd.DataFrame]:
    """Read OHLCV from S3 curated zone (tries equities, etf, fixed_income)."""
    if not _USE_S3:
        return None
    try:
        from datalayer.s3 import read_parquet, curated_key
        from datalayer.schemas import ASSET_EQUITIES, ASSET_ETF, ASSET_FIXED_INCOME

        # Prefer a direct, single-key lookup using the symbol→asset-class map.
        # Only fall back to probing all classes for symbols we can't classify.
        mapped = _SYMBOL_ASSET_CLASS.get(ticker.upper())
        asset_classes = [mapped] if mapped else [ASSET_EQUITIES, ASSET_ETF, ASSET_FIXED_INCOME]

        for asset_class in asset_classes:
            try:
                key = curated_key(asset_class, "yfinance", ticker)
                df = read_parquet(key)
                if df is not None and not df.empty:
                    # Rename from snake_case to PascalCase
                    df = df.rename(columns={
                        "trade_date": "Date",
                        "symbol": "Ticker",
                        "open": "Open",
                        "high": "High",
                        "low": "Low",
                        "close": "Close",
                        "adj_close": "Adj Close",
                        "volume": "Volume",
                    })
                    df["Date"] = pd.to_datetime(df["Date"])
                    return df[_REQUIRED_COLS].sort_values("Date").reset_index(drop=True)
            except Exception:
                continue
        return None
    except Exception as e:
        logger.warning("Failed reading %s from S3: %s", ticker, e)
        return None


def _read_base_cache(ticker: str) -> Optional[pd.DataFrame]:
    """
    Read base daily data.
    First try S3 (if configured), then PostgreSQL, then local CSV cache.
    """
    if _USE_S3:
        data = _read_from_s3(ticker)
        if data is not None:
            return data

    try:
        from backend.db.postgres_store import (
            is_enabled as postgres_enabled,
            read_ticker_prices as read_postgres_ticker,
        )
        if postgres_enabled():
            return read_postgres_ticker(ticker)
    except Exception:
        pass

    return _read_disk(ticker)


def _append_and_save(ticker: str, existing: pd.DataFrame, new_rows: pd.DataFrame) -> pd.DataFrame:
    """Merge new rows into existing df, dedup, and persist to configured store."""
    combined = pd.concat([existing, new_rows], ignore_index=True)
    _coerce_naive_utc_inplace(combined)
    combined = (
        combined
        .drop_duplicates(subset=["Date", "Ticker"])
        .sort_values("Date")
        .reset_index(drop=True)
    )
    _persist_cache(ticker, combined)
    return combined


# ── yfinance incremental fetch ────────────────────────────────────────
def _fetch_yfinance(ticker: str, start: date, end: date) -> Optional[pd.DataFrame]:
    """
    Download OHLCV from yfinance for the given date range.
    Returns a DataFrame with _REQUIRED_COLS or None on failure.
    """
    try:
        raw = yf.download(
            ticker,
            start=start.isoformat(),
            end=(end + timedelta(days=1)).isoformat(),
            interval="1d",
            progress=False,
            auto_adjust=True,
        )
        if raw is None or raw.empty:
            return None

        # yfinance 1.x returns MultiIndex columns when auto_adjust=True
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)

        raw = raw.reset_index()
        raw = raw.rename(columns={"index": "Date", "Datetime": "Date"})
        raw["Date"] = pd.to_datetime(raw["Date"], utc=True).dt.tz_convert(None)
        raw["Ticker"] = ticker

        # Map yfinance column names
        col_map = {"Open": "Open", "High": "High", "Low": "Low",
                   "Close": "Close", "Volume": "Volume"}
        for c in col_map:
            if c not in raw.columns:
                raw[c] = np.nan
        raw["Adj Close"] = raw["Close"]

        return raw[_REQUIRED_COLS]
    except Exception as e:
        logger.warning("yfinance fetch failed for %s: %s", ticker, e)
        return None


# ── Smart cache update ────────────────────────────────────────────────
def _ensure_fresh(ticker: str) -> Optional[pd.DataFrame]:
    """
    Load cached data, check staleness, fetch missing days if needed.
    Always returns the best available data.
    """
    existing = _read_base_cache(ticker)
    if existing is None or existing.empty:
        # No S3 or cache at all — try full fetch from yfinance
        logger.info("No S3 or cached data for %s — fetching full history", ticker)
        new_data = _fetch_yfinance(ticker, date(2005, 1, 1), date.today())
        if new_data is not None and not new_data.empty:
            new_data["Ticker"] = ticker
            _persist_cache(ticker, new_data)
            return new_data
        return None

    last_date = existing["Date"].max().date()
    target    = _last_business_day()

    if last_date >= target:
        return existing  # Already up to date

    # Fetch only the missing range
    fetch_start = last_date + timedelta(days=1)
    logger.info("Updating %s: %s → %s", ticker, fetch_start, target)
    new_rows = _fetch_yfinance(ticker, fetch_start, target)

    if new_rows is not None and not new_rows.empty:
        existing = _append_and_save(ticker, existing, new_rows)

    return existing  # Return best available even if fetch failed


# ── Local resample (1d → 1wk / 1mo) ──────────────────────────────────
def _resample_from_daily(df: pd.DataFrame, interval: str) -> pd.DataFrame:
    if interval == "1d" or df.empty:
        return df.copy()
    rule = "W-FRI" if interval == "1wk" else "ME"
    g = df.set_index("Date").sort_index()
    out = pd.DataFrame({
        "Open":      g["Open"].resample(rule).first(),
        "High":      g["High"].resample(rule).max(),
        "Low":       g["Low"].resample(rule).min(),
        "Close":     g["Close"].resample(rule).last(),
        "Adj Close": g["Adj Close"].resample(rule).last(),
        "Volume":    g["Volume"].resample(rule).sum(),
    }).dropna(how="all")
    out["Ticker"] = df["Ticker"].iloc[0]
    out = out.reset_index()[_REQUIRED_COLS]
    _coerce_naive_utc_inplace(out)
    return out


# ── Public API ────────────────────────────────────────────────────────
def sanitize_tickers(arg: str) -> Tuple[List[str], List[str]]:
    raw = [t.strip() for t in (arg or "").split(",") if t.strip()]
    kept, dropped = [], []
    for t in raw:
        up = t.upper()
        if (up in ALLOWLIST) and not _is_denied(up):
            kept.append(up)
        else:
            dropped.append(t)
    return kept, dropped


def fetch_prices(
    tickers: List[str],
    period: str = "2y",
    interval: str = "1d",
) -> Tuple[pd.DataFrame, Dict[str, str]]:
    """
    Return OHLCV DataFrame for the requested tickers/period/interval.
    Transparently updates disk cache with any missing dates via yfinance.
    """
    errors: Dict[str, str] = {}
    cols = _REQUIRED_COLS

    # Filter to allowed tickers
    tickers = [t.upper() for t in tickers if t.upper() in ALLOWLIST and not _is_denied(t)]
    if not tickers:
        return pd.DataFrame(columns=cols), errors

    now = time.time()
    _t0 = now
    out_frames = []

    for t in tickers:
        key = (t, period, interval)
        if key in _mem_cache and now - _mem_cache[key][0] < CACHE_TTL_SEC:
            out_frames.append(_mem_cache[key][1])
            continue

        daily = _ensure_fresh(t)
        if daily is None or daily.empty:
            errors[t] = "no_data"
            continue

        df = _resample_from_daily(daily, interval)
        df = _trim_period(df, period)

        if df.empty:
            errors[t] = "empty_after_trim"
            continue

        _mem_cache[key] = (now, df, {})
        out_frames.append(df)

    if not out_frames:
        _perf(f"fetch_prices({len(tickers)} tickers)", _t0)
        return pd.DataFrame(columns=cols), errors

    result = pd.concat(out_frames, ignore_index=True)
    _coerce_naive_utc_inplace(result)
    _perf(f"fetch_prices({len(tickers)} tickers)", _t0)
    return result.sort_values(["Ticker", "Date"]).reset_index(drop=True), errors


def compute_metrics(prices: pd.DataFrame) -> pd.DataFrame:
    """Per-ticker summary metrics."""
    if prices.empty:
        return pd.DataFrame()
    _coerce_naive_utc_inplace(prices)
    prices = prices.dropna(subset=["Close"]).sort_values(["Ticker", "Date"])
    rows = []
    for tkr, g in prices.groupby("Ticker"):
        g = g.set_index("Date").sort_index()
        if g["Close"].empty:
            continue

        def pct(days):
            if len(g) <= days:
                return np.nan
            return (g["Close"].iloc[-1] / g["Close"].iloc[-(days + 1)] - 1.0) * 100.0

        latest = g["Close"].iloc[-1]
        prev   = g["Close"].iloc[-2] if len(g) > 1 else np.nan
        chg1d  = (latest / prev - 1.0) * 100.0 if pd.notna(prev) else np.nan

        try:
            fy  = g.loc[g.index.year == g.index[-1].year, "Close"].iloc[0]
            ytd = (latest / fy - 1.0) * 100.0
        except Exception:
            ytd = np.nan

        w     = g["Close"].tail(252)
        hi52  = w.max() if not w.empty else np.nan
        lo52  = w.min() if not w.empty else np.nan
        daily = g["Close"].pct_change(fill_method=None).dropna()
        vol_ann = daily.std() * np.sqrt(252) * 100.0 if not daily.empty else np.nan

        rows.append({
            "ticker":       tkr,
            "last":         float(latest),
            "chg_1d_pct":   float(chg1d)   if pd.notna(chg1d)   else None,
            "ytd_pct":      float(ytd)      if pd.notna(ytd)      else None,
            "ret_1m_pct":   float(pct(21))  if pd.notna(pct(21))  else None,
            "ret_3m_pct":   float(pct(63))  if pd.notna(pct(63))  else None,
            "ret_6m_pct":   float(pct(126)) if pd.notna(pct(126)) else None,
            "ret_1y_pct":   float(pct(252)) if pd.notna(pct(252)) else None,
            "hi_52w":       float(hi52)     if pd.notna(hi52)     else None,
            "lo_52w":       float(lo52)     if pd.notna(lo52)     else None,
            "vol_ann_pct":  float(vol_ann)  if pd.notna(vol_ann)  else None,
        })
    return pd.DataFrame(rows)


def build_timeseries(prices: pd.DataFrame, tickers: List[str]) -> pd.DataFrame:
    """Normalised price series (index = 100 at each ticker's first valid date)."""
    if prices.empty:
        return pd.DataFrame()
    _coerce_naive_utc_inplace(prices)
    pivot = prices.pivot_table(index="Date", columns="Ticker", values="Close")
    keep  = [t for t in tickers if t in pivot.columns]
    pivot = pivot[keep].dropna(how="all", axis=1)
    if pivot.empty:
        return pd.DataFrame()
    # Normalize each column to 100 at its own first valid price
    # (handles tickers with different inception dates correctly)
    first_valid = pivot.apply(lambda col: col.dropna().iloc[0] if not col.dropna().empty else np.nan)
    return (pivot / first_valid * 100.0)


def corr_matrix(prices: pd.DataFrame, tickers: List[str]) -> pd.DataFrame:
    """Pearson correlation of daily returns."""
    if prices.empty:
        return pd.DataFrame()
    _coerce_naive_utc_inplace(prices)
    pivot = prices.pivot_table(index="Date", columns="Ticker", values="Close")
    keep  = [t for t in tickers if t in pivot.columns]
    rets  = pivot[keep].pct_change(fill_method=None).dropna(how="all")
    if rets.empty:
        return pd.DataFrame()
    return rets.corr()
