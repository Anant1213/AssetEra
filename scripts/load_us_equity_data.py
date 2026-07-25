#!/usr/bin/env python3
"""
Fetch 10 years of daily OHLCV for 150 US equities
(50 large / 50 mid / 50 small cap, NYSE + NASDAQ)
and load into the us_equity_prices table in Supabase.

Usage:
    python scripts/load_us_equity_data.py               # all 150 tickers
    python scripts/load_us_equity_data.py --cap LARGE   # large cap only
    python scripts/load_us_equity_data.py --reset       # truncate first
    python scripts/load_us_equity_data.py --ticker AAPL # single ticker
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
import yfinance as yf

from backend.db.postgres_store import (
    is_enabled,
    redacted_postgres_url,
    upsert_equity_prices,
    reset_equity_prices,
    _ensure_equity_schema,
)

# ── US equity universe ────────────────────────────────────────────────
# S&P 500 top 50 by market cap (NYSE + NASDAQ large caps)
LARGE_CAP: list[str] = [
    "AAPL",  "MSFT",  "NVDA",  "AMZN",  "GOOGL",
    "META",  "TSLA",  "AVGO",  "JPM",   "LLY",
    "V",     "UNH",   "XOM",   "MA",    "JNJ",
    "PG",    "HD",    "COST",  "MRK",   "ABBV",
    "WMT",   "BAC",   "NFLX",  "CRM",   "CVX",
    "AMD",   "ORCL",  "PEP",   "KO",    "TMO",
    "ACN",   "MCD",   "CSCO",  "WFC",   "GE",
    "NOW",   "ADBE",  "TXN",   "QCOM",  "DHR",
    "PM",    "CAT",   "AMGN",  "INTU",  "SPGI",
    "MS",    "GS",    "IBM",   "RTX",   "BRK-B",
]

# S&P MidCap 400 representative selection
MID_CAP: list[str] = [
    "DECK",  "SAIA",  "BURL",  "GNRC",  "CLH",
    "TXRH",  "KTOS",  "LSTR",  "MATX",  "BJ",
    "SFM",   "ELS",   "ITT",   "AWI",   "NVT",
    "UFPI",  "ATI",   "WMS",   "GATX",  "MTB",
    "CINF",  "CFG",   "ZION",  "RJF",   "NTRS",
    "AIZ",   "STE",   "PNW",   "ATO",   "WTFC",
    "RGEN",  "BLD",   "EXPO",  "PRI",   "HLI",
    "OHI",   "LCII",  "HLNE",  "RNR",   "RGLD",
    "CBSH",  "BOOT",  "CUBE",  "LPLA",  "NEU",
    "WEX",   "SBCF",  "MMSI",  "CRVL",  "FHB",  # SNV → SBCF
]

# S&P SmallCap 600 / Russell 2000 representative selection
# Note: delisted tickers replaced — HAYN→HWKN, RCII→PRDO, SJW→YORW,
#       HTLF→HFWA, HIBB→CULP, NWLI→NMIH, CBTX→COFS, SPNS→SPFI
SMALL_CAP: list[str] = [
    "ABM",   "AMSF",  "CAKE",  "CATO",  "CENX",
    "CHCO",  "CSWC",  "DLB",   "DXPE",  "FCPT",
    "FFIN",  "HWKN",  "IPAR",  "JJSF",  "KALU",
    "KFRC",  "LGND",  "MRTN",  "MTRN",  "NTGR",
    "OFG",   "PKOH",  "PRK",   "PRDO",  "RUSHA",
    "YORW",  "SMPL",  "STBA",  "SYBT",  "TRMK",
    "UFPT",  "WEYS",  "ZEUS",  "BANF",  "HFWA",
    "JELD",  "DGII",  "ASO",   "BLBD",  "CAL",
    "CULP",  "FRPH",  "HAIN",  "NMIH",  "LQDT",
    "RAMP",  "MGNI",  "DIN",   "COFS",  "SPFI",
]

ALL_TICKERS: dict[str, list[str]] = {
    "LARGE": LARGE_CAP,
    "MID":   MID_CAP,
    "SMALL": SMALL_CAP,
}

START_DATE = (date.today() - timedelta(days=365 * 10 + 5)).isoformat()
END_DATE   = date.today().isoformat()


# ── Fetch helpers ─────────────────────────────────────────────────────

def _fetch_ticker(ticker: str) -> pd.DataFrame | None:
    try:
        raw = yf.download(
            ticker,
            start=START_DATE,
            end=END_DATE,
            interval="1d",
            progress=False,
            auto_adjust=True,
        )
        if raw is None or raw.empty:
            return None

        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)

        raw = raw.reset_index()
        raw = raw.rename(columns={"index": "Date", "Datetime": "Date"})
        raw["Date"] = pd.to_datetime(raw["Date"], utc=True).dt.tz_convert(None)
        raw["Ticker"] = ticker.upper()

        for c in ["Open", "High", "Low", "Close", "Volume"]:
            if c not in raw.columns:
                raw[c] = np.nan
        raw["Adj Close"] = raw.get("Close", np.nan)

        cols = ["Date", "Ticker", "Close", "Open", "High", "Low", "Adj Close", "Volume"]
        return raw[cols].dropna(subset=["Close"])
    except Exception:
        return None


def _load_ticker(ticker: str, cap: str, verbose: bool = True) -> tuple[bool, int]:
    df = _fetch_ticker(ticker)
    if df is None or df.empty:
        if verbose:
            print(f"  SKIP  {ticker:<12} — no data from yfinance")
        return False, 0

    ok   = upsert_equity_prices(df, cap)
    rows = len(df)
    if verbose:
        status     = "OK   " if ok else "FAIL "
        date_range = f"{df['Date'].min().date()} → {df['Date'].max().date()}"
        print(f"  {status} {ticker:<12} {rows:>5} rows  {date_range}")
    return ok, rows


# ── CLI ───────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Load US equity data into us_equity_prices.")
    p.add_argument("--cap",    choices=["LARGE", "MID", "SMALL"], help="Load only this cap tier")
    p.add_argument("--reset",  action="store_true",               help="Truncate table before loading")
    p.add_argument("--ticker", default="",                         help="Load a single ticker (e.g. AAPL)")
    p.add_argument("--delay",  type=float, default=0.3,            help="Seconds between yfinance calls")
    return p.parse_args()


def main() -> int:
    load_dotenv()
    args = parse_args()

    if not is_enabled():
        print("ERROR: PostgreSQL not enabled. Set POSTGRES_URL or DATABASE_URL in .env")
        return 1

    print(f"PostgreSQL target: {redacted_postgres_url()}")
    print(f"Fetch window: {START_DATE} → {END_DATE}")

    if not _ensure_equity_schema():
        print("ERROR: Could not create us_equity_prices table")
        return 1

    if args.reset:
        if reset_equity_prices():
            print("OK: Truncated us_equity_prices")
        else:
            print("ERROR: Failed to truncate"); return 1

    # Single-ticker mode
    if args.ticker:
        t = args.ticker.upper()
        cap = "LARGE" if t in LARGE_CAP else "MID" if t in MID_CAP else "SMALL"
        ok, _ = _load_ticker(t, cap)
        return 0 if ok else 1

    # Batch mode
    caps_to_load = [args.cap] if args.cap else ["LARGE", "MID", "SMALL"]
    total_ok = total_fail = total_rows = 0
    failed: list[str] = []

    for cap in caps_to_load:
        tickers = ALL_TICKERS[cap]
        print(f"\n── {cap} CAP ({len(tickers)} tickers) ──")
        for ticker in tickers:
            ok, rows = _load_ticker(ticker, cap)
            total_rows += rows
            if ok:
                total_ok += 1
            else:
                total_fail += 1
                failed.append(f"{cap}:{ticker}")
            time.sleep(args.delay)

    print("\n" + "=" * 50)
    print(f"Loaded : {total_ok} tickers")
    print(f"Failed : {total_fail} tickers")
    print(f"Rows   : {total_rows:,}")
    if failed:
        print("\nFailed / no data:")
        for t in failed:
            print(f"  {t}")

    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
