"""
Performance / regression tests for the page-load choke points.

These tests protect the fixes made to keep local Streamlit page loads fast:

  * The decorative ticker tape must use a small fixed list, never the full
    ALLOWLIST universe (~200 symbols).
  * ``fetch_prices`` must not fall back to yfinance when the local/S3 cache is
    already fresh (no duplicate per-ticker network calls).
  * S3 reads must go directly to one asset-class key for known symbols instead
    of probing equities → etf → fixed_income in sequence.

Runnable without pytest:  ``python -m unittest tests.test_perf_tape``
"""
from __future__ import annotations

import unittest
from datetime import date
from unittest import mock

import numpy as np
import pandas as pd

from backend import market


def _fresh_frame(ticker: str) -> pd.DataFrame:
    """A minimal, already-up-to-date OHLCV frame for one ticker."""
    today = pd.Timestamp(date.today())
    return pd.DataFrame({
        "Date": [today - pd.Timedelta(days=1), today],
        "Ticker": [ticker, ticker],
        "Open": [1.0, 1.0], "High": [1.0, 1.0], "Low": [1.0, 1.0],
        "Close": [1.0, 2.0], "Adj Close": [1.0, 2.0], "Volume": [10, 10],
    })[market._REQUIRED_COLS]


class TapeTickerListTests(unittest.TestCase):
    def test_tape_list_is_small(self):
        self.assertLessEqual(len(market.TAPE_TICKERS), 10)
        self.assertGreater(len(market.TAPE_TICKERS), 0)

    def test_tape_tickers_are_allowed(self):
        # Every tape symbol must survive the ALLOWLIST filter, otherwise the
        # tape silently renders nothing.
        for t in market.TAPE_TICKERS:
            self.assertIn(t.upper(), market.ALLOWLIST)

    def test_tape_list_far_smaller_than_universe(self):
        # Guards against anyone re-pointing the tape at the full universe.
        self.assertLess(len(market.TAPE_TICKERS), len(market.ALLOWLIST) / 2)


class FetchPricesFreshnessTests(unittest.TestCase):
    def setUp(self):
        market._mem_cache.clear()

    def test_no_yfinance_when_cache_is_fresh(self):
        tickers = market.TAPE_TICKERS[:3]

        with mock.patch.object(market, "_read_base_cache",
                               side_effect=lambda t: _fresh_frame(t)) as m_cache, \
             mock.patch.object(market, "_fetch_yfinance") as m_yf:
            df, errors = market.fetch_prices(tickers, period="5d", interval="1d")

        self.assertFalse(df.empty)
        self.assertEqual(errors, {})
        # Fresh cache → no network fallback at all.
        m_yf.assert_not_called()
        # Exactly one base-cache read per ticker (no duplicate lookups).
        self.assertEqual(m_cache.call_count, len(tickers))

    def test_filters_to_allowlist(self):
        df, errors = market.fetch_prices(["NOT_A_REAL_TICKER_XYZ"], period="5d")
        self.assertTrue(df.empty)


class S3DirectKeyTests(unittest.TestCase):
    def test_mapped_symbol_reads_single_asset_class(self):
        # Pick any symbol we can classify from the universe map.
        if not market._SYMBOL_ASSET_CLASS:
            self.skipTest("datalayer universe not available")
        symbol = next(iter(market._SYMBOL_ASSET_CLASS))

        fake_curated = mock.Mock(return_value="curated/key")
        fake_read = mock.Mock(return_value=pd.DataFrame({
            "trade_date": [pd.Timestamp("2024-01-02")],
            "symbol": [symbol], "open": [1.0], "high": [1.0], "low": [1.0],
            "close": [1.0], "adj_close": [1.0], "volume": [1],
        }))

        s3_mod = mock.Mock(read_parquet=fake_read, curated_key=fake_curated)
        with mock.patch.object(market, "_USE_S3", True), \
             mock.patch.dict("sys.modules", {"datalayer.s3": s3_mod}):
            out = market._read_from_s3(symbol)

        self.assertIsNotNone(out)
        # Direct map hit → exactly one key built + one parquet read (no 3x probe).
        self.assertEqual(fake_curated.call_count, 1)
        self.assertEqual(fake_read.call_count, 1)


if __name__ == "__main__":
    unittest.main()
