#!/usr/bin/env python3
"""Load data_cache CSV files into PostgreSQL us_prices table."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.db.postgres_store import (  # noqa: E402
    is_enabled,
    load_csv_file,
    redacted_postgres_url,
    reset_us_prices as reset_market_prices,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import local OHLCV CSV files into PostgreSQL us_prices table."
    )
    parser.add_argument(
        "--dir",
        default="data_cache",
        help="Directory containing CSV files (default: data_cache)",
    )
    parser.add_argument(
        "--pattern",
        default="*_1d.csv",
        help="Glob pattern for files to load (default: *_1d.csv)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Truncate us_prices before loading",
    )
    return parser.parse_args()


def main() -> int:
    load_dotenv()
    args = parse_args()

    if not is_enabled():
        print("ERROR: PostgreSQL is not enabled. Set POSTGRES_URL or DATABASE_URL in .env")
        return 1

    source_dir = (ROOT / args.dir).resolve()
    if not source_dir.exists():
        print(f"ERROR: Directory not found: {source_dir}")
        return 1

    files = sorted(source_dir.glob(args.pattern))
    if not files:
        print(f"ERROR: No files found in {source_dir} matching pattern '{args.pattern}'")
        return 1

    print("PostgreSQL target:", redacted_postgres_url())
    print(f"Source directory: {source_dir}")
    print(f"Matching files: {len(files)}")

    if args.reset:
        if reset_market_prices():
            print("OK: Truncated us_prices")
        else:
            print("ERROR: Failed to truncate us_prices")
            return 1

    ok_files = 0
    failed_files = []
    total_rows = 0

    for path in files:
        ok, rows = load_csv_file(path)
        total_rows += rows
        if ok:
            ok_files += 1
            print(f"OK: {path.name}: {rows} rows")
        else:
            failed_files.append(path.name)
            print(f"ERROR: {path.name}: failed")

    print("\n--- Import Summary ---")
    print(f"Files loaded: {ok_files}/{len(files)}")
    print(f"Rows processed: {total_rows}")

    if failed_files:
        print("Failed files:")
        for name in failed_files:
            print(f"- {name}")
        return 1

    print("OK: PostgreSQL import complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
