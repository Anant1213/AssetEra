#!/usr/bin/env python3
"""
Fetch 10 years of NSE daily OHLCV data for 150 stocks (50 large / 50 mid / 50 small cap)
and load into the nse_prices table in Supabase PostgreSQL.

Usage:
    python scripts/load_nse_data.py               # load all 150 tickers
    python scripts/load_nse_data.py --cap LARGE   # load only large-cap
    python scripts/load_nse_data.py --reset       # truncate table first
    python scripts/load_nse_data.py --ticker RELIANCE.NS  # single ticker
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

import pandas as pd
import numpy as np
import yfinance as yf

from backend.db.postgres_store import (
    is_enabled,
    redacted_postgres_url,
    upsert_nse_prices,
    reset_nse_prices,
    _ensure_nse_schema,
)

# ── NSE ticker lists ──────────────────────────────────────────────────
# Nifty 50 constituents — blue-chip large caps
# Note: TATAMOTORS.NS replaced by PIDILITIND.NS (yfinance feed issue)
LARGE_CAP: list[str] = [
    "ADANIENT.NS",    "ADANIPORTS.NS",  "APOLLOHOSP.NS",  "ASIANPAINT.NS",  "AXISBANK.NS",
    "BAJAJ-AUTO.NS",  "BAJAJFINSV.NS",  "BAJFINANCE.NS",  "BHARTIARTL.NS",  "BPCL.NS",
    "BRITANNIA.NS",   "CIPLA.NS",       "COALINDIA.NS",   "DIVISLAB.NS",    "DRREDDY.NS",
    "EICHERMOT.NS",   "GRASIM.NS",      "HCLTECH.NS",     "HDFCBANK.NS",    "HDFCLIFE.NS",
    "HEROMOTOCO.NS",  "HINDALCO.NS",    "HINDUNILVR.NS",  "ICICIBANK.NS",   "INDUSINDBK.NS",
    "INFY.NS",        "ITC.NS",         "JSWSTEEL.NS",    "KOTAKBANK.NS",   "LT.NS",
    "M&M.NS",         "MARUTI.NS",      "NESTLEIND.NS",   "NTPC.NS",        "ONGC.NS",
    "POWERGRID.NS",   "RELIANCE.NS",    "SBILIFE.NS",     "SBIN.NS",        "SHREECEM.NS",
    "SUNPHARMA.NS",   "PIDILITIND.NS",  "TATACONSUM.NS",  "TATASTEEL.NS",   "TCS.NS",
    "TECHM.NS",       "TITAN.NS",       "TRENT.NS",       "ULTRACEMCO.NS",  "WIPRO.NS",
]

# Nifty Midcap 50 / 100 selection
MID_CAP: list[str] = [
    "AARTIIND.NS",    "ABCAPITAL.NS",   "ASTRAL.NS",      "AUROPHARMA.NS",  "BANDHANBNK.NS",
    "BANKBARODA.NS",  "BIOCON.NS",      "CANBK.NS",       "CDSL.NS",        "CHOLAFIN.NS",
    "COFORGE.NS",     "CONCOR.NS",      "CRISIL.NS",      "CROMPTON.NS",    "DEEPAKNTR.NS",
    "DLF.NS",         "DMART.NS",       "ESCORTS.NS",     "FEDERALBNK.NS",  "GLENMARK.NS",
    "GODREJPROP.NS",  "HAVELLS.NS",     "IDFCFIRSTB.NS",  "INDHOTEL.NS",    "INDIANB.NS",
    "IRCTC.NS",       "KEI.NS",         "LALPATHLAB.NS",  "LTIM.NS",        "LUPIN.NS",
    "MFSL.NS",        "MUTHOOTFIN.NS",  "NAUKRI.NS",      "NMDC.NS",        "OBEROIRLTY.NS",
    "PAGEIND.NS",     "PERSISTENT.NS",  "PIIND.NS",       "PNB.NS",         "POLYCAB.NS",
    "PRESTIGE.NS",    "SUNDRMFAST.NS",  "TORNTPHARM.NS",  "UNIONBANK.NS",   "VOLTAS.NS",
    "MANAPPURAM.NS",  "ABFRL.NS",       "METROPOLIS.NS",  "INDIAMART.NS",   "BLUEDART.NS",
]

# Nifty Smallcap 50 / 100 selection
# Notes: AEGISCHEM.NS → AEGISLOG.NS (Aegis Logistics), CENTURYTEX.NS → CENTURYPLY.NS,
#        GMRINFRA.NS → GMRAIRPORT.NS (renamed)
SMALL_CAP: list[str] = [
    "AAVAS.NS",       "AEGISLOG.NS",    "APLLTD.NS",      "BALRAMCHIN.NS",  "CARBORUNIV.NS",
    "CENTURYPLY.NS",  "DCMSHRIRAM.NS",  "FINEORG.NS",     "FLUOROCHEM.NS",  "GESHIP.NS",
    "GMRAIRPORT.NS",  "GRINDWELL.NS",   "GSPL.NS",        "HFCL.NS",        "IBREALEST.NS",
    "INOXWIND.NS",    "JKCEMENT.NS",    "JKPAPER.NS",     "KNRCON.NS",      "KPITTECH.NS",
    "MRPL.NS",        "MOTILALOFS.NS",  "NAVINFLUOR.NS",  "NIACL.NS",       "NOCIL.NS",
    "ORIENTELEC.NS",  "PFIZER.NS",      "QUESS.NS",       "RAIN.NS",        "RATNAMANI.NS",
    "RAYMOND.NS",     "RITES.NS",       "RPOWER.NS",      "SAFARI.NS",      "SANOFI.NS",
    "SCHAEFFLER.NS",  "SJVN.NS",        "SPARC.NS",       "SUPREMEIND.NS",  "SUZLON.NS",
    "SYMPHONY.NS",    "THERMAX.NS",     "TTKPRESTIG.NS",  "UJJIVANSFB.NS",  "VGUARD.NS",
    "WABAG.NS",       "RAMCOIND.NS",    "ASTEC.NS",       "GALAXYSURF.NS",  "IIFL.NS",
]

ALL_TICKERS: dict[str, list[str]] = {
    "LARGE": LARGE_CAP,
    "MID":   MID_CAP,
    "SMALL": SMALL_CAP,
}

START_DATE = (date.today() - timedelta(days=365 * 10 + 5)).isoformat()  # ~10 years
END_DATE   = date.today().isoformat()

# ── Fetch helpers ─────────────────────────────────────────────────────

def _fetch_ticker(ticker: str) -> pd.DataFrame | None:
    """Download OHLCV from yfinance, return normalised DataFrame or None."""
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

        # yfinance 1.x always returns MultiIndex columns
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
    except Exception as e:
        return None


def _load_ticker(ticker: str, cap: str, verbose: bool = True) -> tuple[bool, int]:
    df = _fetch_ticker(ticker)
    if df is None or df.empty:
        if verbose:
            print(f"  SKIP  {ticker:<22} — no data from yfinance")
        return False, 0

    ok = upsert_nse_prices(df, cap)
    rows = len(df)
    if verbose:
        status = "OK   " if ok else "FAIL "
        date_range = f"{df['Date'].min().date()} → {df['Date'].max().date()}"
        print(f"  {status} {ticker:<22} {rows:>5} rows  {date_range}")
    return ok, rows


# ── CLI ───────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Load NSE stock data into nse_prices table.")
    p.add_argument("--cap",    choices=["LARGE", "MID", "SMALL"], help="Load only this cap category")
    p.add_argument("--reset",  action="store_true",               help="Truncate nse_prices before loading")
    p.add_argument("--ticker", default="",                         help="Load a single NSE ticker (e.g. RELIANCE.NS)")
    p.add_argument("--delay",  type=float, default=0.3,            help="Seconds to wait between yfinance calls (default 0.3)")
    return p.parse_args()


def main() -> int:
    load_dotenv()
    args = parse_args()

    if not is_enabled():
        print("ERROR: PostgreSQL is not enabled. Set POSTGRES_URL or DATABASE_URL in .env")
        return 1

    print("PostgreSQL target:", redacted_postgres_url())
    print(f"Fetch window: {START_DATE} → {END_DATE}")

    if not _ensure_nse_schema():
        print("ERROR: Could not create nse_prices table")
        return 1

    if args.reset:
        if reset_nse_prices():
            print("OK: Truncated nse_prices")
        else:
            print("ERROR: Failed to truncate nse_prices")
            return 1

    # Single-ticker mode
    if args.ticker:
        t = args.ticker.upper()
        # Auto-append .NS if missing
        if not t.endswith(".NS"):
            t += ".NS"
        cap = "LARGE" if t in [x.upper() for x in LARGE_CAP] else \
              "MID"   if t in [x.upper() for x in MID_CAP]   else "SMALL"
        ok, rows = _load_ticker(t, cap)
        return 0 if ok else 1

    # Batch mode
    caps_to_load = [args.cap] if args.cap else ["LARGE", "MID", "SMALL"]

    total_ok = total_fail = total_rows = 0
    failed_tickers: list[str] = []

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
                failed_tickers.append(f"{cap}:{ticker}")
            time.sleep(args.delay)

    print("\n" + "=" * 55)
    print("NSE Load Summary")
    print(f"  Loaded:  {total_ok} tickers")
    print(f"  Failed:  {total_fail} tickers")
    print(f"  Rows:    {total_rows:,}")
    if failed_tickers:
        print("\nFailed / no data:")
        for t in failed_tickers:
            print(f"  {t}")

    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
