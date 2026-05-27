# -*- coding: utf-8 -*-
import pandas as pd

from core.columns import COL_CHANGE_PCT, COL_NAME, COL_TICKER, COL_VALUE
from core.data_sources.market_radar import get_market_radar_data
from core.data_sources.patches import apply_yahoo_price_patches
from core.data_sources.yahoo import (
    fetch_common_data,
    fetch_historical_data,
    normalize_tickers,
    normalize_yfinance_columns,
)


def test_normalize_tickers_keeps_string_and_converts_sequences():
    assert normalize_tickers("VOO") == "VOO"
    assert normalize_tickers(("2330.TW", 1306)) == ["2330.TW", "1306"]


def test_normalize_yfinance_columns_swaps_price_ticker_multiindex():
    df = pd.DataFrame(
        {
            ("Close", "VOO"): [100.0],
            ("Open", "VOO"): [99.0],
        }
    )
    df.columns = pd.MultiIndex.from_tuples(df.columns)

    normalized = normalize_yfinance_columns(df)

    assert ("VOO", "Close") in normalized.columns
    assert ("VOO", "Open") in normalized.columns


def test_apply_yahoo_price_patches_repairs_known_split_multiindex_frame():
    dates = pd.to_datetime(["2026-05-25", "2026-05-26", "2026-05-27"])
    df = pd.DataFrame(
        {
            ("0052.TW", "Close"): [700.0, 770.0, 70.0],
            ("0052.TW", "Open"): [693.0, 763.0, 98.0],
            ("0052.TW", "Volume"): [10.0, 20.0, 30.0],
            ("2330.TW", "Close"): [500.0, 510.0, 520.0],
        },
        index=dates,
    )
    df.columns = pd.MultiIndex.from_tuples(df.columns)

    patched = apply_yahoo_price_patches(df, ["0052.TW", "2330.TW"])

    assert patched.loc[dates[0], ("0052.TW", "Close")] == 100.0
    assert patched.loc[dates[1], ("0052.TW", "Close")] == 110.0
    assert patched.loc[dates[2], ("0052.TW", "Close")] == 70.0
    assert patched.loc[dates[0], ("0052.TW", "Volume")] == 70.0
    assert patched.loc[dates[2], ("0052.TW", "Volume")] == 30.0
    assert patched.loc[dates[0], ("2330.TW", "Close")] == 500.0


def test_fetch_historical_data_uses_injected_fetcher_and_squeezes_single_ticker():
    dates = pd.to_datetime(["2026-05-26", "2026-05-27"])
    raw = pd.DataFrame({("VOO", "Close"): [100.0, 101.0]}, index=dates)
    raw.columns = pd.MultiIndex.from_tuples(raw.columns)

    def fake_historical(tickers, period, group_by):
        assert tickers == "VOO"
        assert period == "1mo"
        assert group_by == "ticker"
        return raw

    result = fetch_historical_data(
        "VOO",
        period="1mo",
        fetchers={"historical": fake_historical},
    )

    assert list(result.columns) == ["Close"]
    assert result["Close"].tolist() == [100.0, 101.0]


def test_fetch_common_data_uses_injected_fetcher():
    raw = pd.DataFrame({"Close": [1.0]})

    def fake_common(tickers, period):
        assert tickers == ["USDTWD=X", "JPYTWD=X"]
        assert period == "5d"
        return raw

    result = fetch_common_data(
        ("USDTWD=X", "JPYTWD=X"),
        period="5d",
        fetchers={"common": fake_common},
    )

    assert result is raw


def test_get_market_radar_data_uses_injected_ticker_factory():
    class FakeTicker:
        fast_info = {"last_price": 110.0}

        def history(self, period):
            if period == "2d":
                return pd.DataFrame({"Close": [100.0, 110.0]})
            return pd.DataFrame({"Close": [110.0]})

    result = get_market_radar_data(
        ticker_factory=lambda ticker: FakeTicker(),
        radar_tickers_provider=lambda: {"USDTWD=X": "美元"},
    )

    assert result == [
        {
            COL_TICKER: "USDTWD=X",
            COL_NAME: "美元",
            COL_VALUE: 110.0,
            COL_CHANGE_PCT: 10.0,
        }
    ]
