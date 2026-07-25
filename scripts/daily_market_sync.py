#!/usr/bin/env python3
"""Daily batch sync: fetch latest market data from yfinance into PostgreSQL."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import sys
from pathlib import Path
from typing import List

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.market import ALLOWLIST, fetch_prices
from backend.db.postgres_store import is_enabled, redacted_postgres_url


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync allowlisted tickers into PostgreSQL using incremental refresh."
    )
    parser.add_argument(
        "--tickers",
        default="",
        help="Comma-separated tickers. Default: full allowlist",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero exit code if any ticker fails",
    )
    return parser.parse_args()


def _resolve_tickers(raw: str) -> List[str]:
    if not raw.strip():
        return sorted(ALLOWLIST)

    requested = [t.strip().upper() for t in raw.split(",") if t.strip()]
    valid = [t for t in requested if t in ALLOWLIST]
    return sorted(set(valid))


def main() -> int:
    load_dotenv()
    args = parse_args()

    if not is_enabled():
        print("ERROR: POSTGRES_URL/DATABASE_URL is required for daily batch sync")
        return 1

    tickers = _resolve_tickers(args.tickers)
    if not tickers:
        print("ERROR: No valid tickers selected")
        return 1

    print("Batch start UTC:", datetime.now(timezone.utc).isoformat())
    print("PostgreSQL target:", redacted_postgres_url())
    print("Tickers to sync:", len(tickers))

    failed = []
    synced = 0

    for ticker in tickers:
        prices, errors = fetch_prices([ticker], period="max", interval="1d")

        if errors.get(ticker):
            failed.append((ticker, errors[ticker]))
            print(f"ERROR: {ticker}: {errors[ticker]}")
            continue

        if prices.empty:
            failed.append((ticker, "empty"))
            print(f"ERROR: {ticker}: empty")
            continue

        tdf = prices[prices["Ticker"] == ticker]
        last_date = tdf["Date"].max()
        synced += 1
        print(f"OK: {ticker}: rows={len(tdf)} last={last_date}")

    print("\n--- Daily Sync Summary ---")
    print(f"Synced: {synced}/{len(tickers)}")

    if failed:
        print("Failed tickers:")
        for ticker, reason in failed:
            print(f"- {ticker}: {reason}")
        return 1 if args.strict else 0

    print("OK: Daily sync complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
