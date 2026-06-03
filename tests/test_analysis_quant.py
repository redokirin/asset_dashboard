# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd

from core import analysis_quant
from core.columns import (
    COL_ASSET_TYPE,
    COL_COMFORT_SCORE,
    COL_CURRENCY,
    COL_HISTORY_YEARS,
    COL_HOLD_ABILITY_SCORE,
    COL_MARKET_VALUE,
    COL_MATURITY_SCORE,
    COL_NAME,
    COL_PRICE,
    COL_TICKER,
)


def _price_frame(length=300):
    index = pd.date_range("2024-01-01", periods=length, freq="D")
    close = pd.Series(np.linspace(100.0, 140.0, length), index=index)
    return pd.DataFrame(
        {
            "Open": close - 0.5,
            "High": close + 1.0,
            "Low": close - 1.0,
            "Close": close,
            "Volume": 1000,
        },
        index=index,
    )


def test_calculate_moving_averages_returns_values_and_display_labels():
    df = _price_frame(260)

    values, labels = analysis_quant._calculate_moving_averages(df)

    assert values["ma5"] is not None
    assert values["ma20"] is not None
    assert values["ma60"] is not None
    assert values["ma120"] is not None
    assert values["ma250"] is not None
    assert labels["ma20"] == f"{values['ma20']:.2f}"
    assert labels["ma250"] == f"{values['ma250']:.2f}"


def test_calculate_rsi_for_monotonic_uptrend_is_high():
    df = _price_frame(30)

    assert analysis_quant._calculate_rsi(df) > 90


def test_calculate_alpha_metrics_without_enough_months_returns_zeroes():
    index = pd.date_range("2026-01-01", periods=20, freq="D")
    comb = pd.DataFrame({"p": 100.0, "b": 100.0, "r": 1.0}, index=index)

    m_ret, bat_avg, avg_alpha, sharpe = analysis_quant._calculate_alpha_metrics(comb)

    assert m_ret.empty
    assert bat_avg == 0.0
    assert avg_alpha == 0.0
    assert sharpe == 0.0


def test_calculate_drawdown_metrics_returns_contract_values():
    df = pd.DataFrame(
        {"Close": [100.0, 120.0, 90.0, 110.0]},
        index=pd.date_range("2026-01-01", periods=4, freq="D"),
    )

    drawdown_result, hold_ability_score, maturity_score, history_years, annualized_vol, vol_grade = (
        analysis_quant._calculate_drawdown_metrics(df, sharpe=1.0)
    )

    assert drawdown_result is not None
    assert drawdown_result.comfortScore == "Low"
    assert 0.0 <= hold_ability_score <= 1.0
    assert maturity_score == 0.4
    assert history_years == 0.0
    assert isinstance(annualized_vol, float)
    assert vol_grade in ("低波動", "中波動", "高波動", "數據不足")


def test_run_advanced_analysis_preserves_ui_output_contract(monkeypatch):
    ticker = "VOO"
    asset_df = pd.DataFrame(
        [
            {
                COL_TICKER: ticker,
                COL_NAME: "Vanguard S&P 500 ETF",
                COL_ASSET_TYPE: "ETF",
                COL_CURRENCY: "USD",
                COL_PRICE: 0.0,
                COL_MARKET_VALUE: 0,
                "_get_value": True,
            }
        ]
    )

    price_df = _price_frame(300)
    historical = pd.concat({ticker: price_df}, axis=1)

    common_index = price_df.index
    common = pd.concat(
        {
            "VOO": pd.DataFrame(
                {"Close": np.linspace(400.0, 450.0, 300)}, index=common_index
            ),
            "USDTWD=X": pd.DataFrame({"Close": 32.0}, index=common_index),
            "JPYTWD=X": pd.DataFrame({"Close": 0.22}, index=common_index),
        },
        axis=1,
    )

    monkeypatch.setattr(
        analysis_quant,
        "fetch_common_data",
        lambda tickers, period="2y": common,
    )
    monkeypatch.setattr(
        analysis_quant,
        "fetch_historical_data",
        lambda tickers, period="2y", group_by="ticker": historical,
    )
    monkeypatch.setattr(
        analysis_quant,
        "get_ticker_fundamental_info",
        lambda ticker_symbol: {
            "name": "Vanguard S&P 500 ETF",
            "eps": 1.0,
            "pe": 20.0,
            "dividendYield": 0.01,
            "pegRatio": 1.2,
            "volume": 100,
            "avg_volume": 100,
        },
    )

    result = analysis_quant.run_advanced_analysis(asset_df)

    assert len(result) == 1
    row = result.iloc[0]
    for key in [
        COL_HOLD_ABILITY_SCORE,
        COL_COMFORT_SCORE,
        COL_MATURITY_SCORE,
        COL_HISTORY_YEARS,
    ]:
        assert key in result.columns
        assert key in row
    assert isinstance(row[COL_HOLD_ABILITY_SCORE], float)
