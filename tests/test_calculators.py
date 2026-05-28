# -*- coding: utf-8 -*-
import pytest
import pandas as pd

from core import calculators
from core.columns import (
    COL_ASSET_TYPE,
    COL_AVG_COST,
    COL_CHANGE,
    COL_COST,
    COL_GET_VALUE,
    COL_MARKET,
    COL_MARKET_VALUE,
    COL_PRICE,
    COL_PROFIT_LOSS,
    COL_RETURN_PCT,
    COL_TICKER,
    COL_UNITS,
    COL_UPDATED_AT,
    COL_WEIGHT,
)


def _asset(**overrides):
    asset = {
        "id": "2330.TW",
        "name": "台積電",
        "market": "TW",
        "ccy": "TWD",
        "units": 10,
        "cost": 5000,
        "nav": 500,
        "enabled": True,
        "get_value": True,
    }
    asset.update(overrides)
    return asset


def test_calculate_asset_row_uses_price_and_exchange_rate():
    row = calculators.calculate_asset_row(
        _asset(ccy="USD", units=4, cost=100),
        "個股",
        {"USD": 30.0},
        price=40,
        change_val=1.5,
        update_time="2026-05-27",
    )

    assert row[COL_UNITS] == 4
    assert row[COL_AVG_COST] == 25
    assert row[COL_PRICE] == 40
    assert row[COL_CHANGE] == 1.5
    assert row[COL_UPDATED_AT] == "2026-05-27"
    assert row[COL_COST] == 3000
    assert row[COL_MARKET_VALUE] == 4800
    assert row[COL_PROFIT_LOSS] == 1800
    assert row[COL_RETURN_PCT] == pytest.approx(60.0)


def test_calculate_asset_row_falls_back_to_investment_lots():
    row = calculators.calculate_asset_row(
        _asset(
            units=0,
            cost=0,
            investment=[
                {"units": 2, "cost": 100},
                {"shares": 3, "cost": 300},
            ],
            nav=120,
        ),
        "ETF",
        {"TWD": 1.0},
    )

    assert row[COL_UNITS] == 5
    assert row[COL_AVG_COST] == 80
    assert row[COL_MARKET_VALUE] == 600
    assert row[COL_PROFIT_LOSS] == 200


def test_calculate_market_share_adds_weight_and_groups_by_market():
    df = pd.DataFrame(
        [
            {COL_MARKET: "TW", COL_MARKET_VALUE: 100},
            {COL_MARKET: "US", COL_MARKET_VALUE: 300},
        ]
    )

    market_share = calculators.calculate_market_share(df)

    assert df[COL_WEIGHT].tolist() == pytest.approx([25.0, 75.0])
    assert market_share["TW"][COL_MARKET_VALUE] == 100
    assert market_share["TW"][COL_WEIGHT] == 25.0
    assert market_share["US"][COL_WEIGHT] == 75.0


def test_fetch_batch_prices_uses_fetcher_without_live_network(monkeypatch):
    dates = pd.to_datetime(["2026-05-25", "2026-05-26"])
    hist_data = pd.DataFrame(
        {
            ("2330.TW", "Close"): [100.0, 105.0],
            ("0050.TW", "Close"): [50.0, 51.0],
        },
        index=dates,
    )
    hist_data.columns = pd.MultiIndex.from_tuples(hist_data.columns)

    def fake_fetch(tickers, period):
        assert tickers == ("2330.TW", "0050.TW")
        assert period == "1mo"
        return hist_data

    assets = {
        "stocks": {
            "2330.TW": _asset(id="2330.TW"),
            "0050.TW": _asset(id="0050.TW"),
            "disabled": _asset(id="1101.TW", enabled=False),
            "manual": _asset(id="9999.TW", get_value=False),
        }
    }
    monkeypatch.setattr(calculators, "fetch_historical_data", fake_fetch)

    prices, changes, times = calculators.fetch_batch_prices(assets, "stocks")

    assert prices == {"2330.TW": 105.0, "0050.TW": 51.0}
    assert changes == {"2330.TW": 5.0, "0050.TW": 1.0}
    assert times == {"2330.TW": "2026-05-26", "0050.TW": "2026-05-26"}


def test_calculate_assets_data_facade_keeps_output_contract(monkeypatch):
    assets = {
        "etfs": {"0050.TW": _asset(id="0050.TW", name="元大台灣50", units=10, cost=1000)},
        "stocks": {"2330.TW": _asset(id="2330.TW", name="台積電", units=2, cost=1000)},
        "funds": {
            "FUND": _asset(
                id="FUND",
                name="測試基金",
                market="US",
                ccy="USD",
                units=3,
                cost=30,
                nav=12,
                get_value=False,
            )
        },
        "banks": {
            "USD_BANK": {
                "id": "USD_BANK",
                "name": "USD Bank",
                "market": "Bank",
                "ccy": "USD",
                "balance": 100,
                "enabled": 1,
            },
            "DISABLED_BANK": {
                "id": "DISABLED_BANK",
                "name": "Disabled Bank",
                "market": "Bank",
                "ccy": "TWD",
                "balance": 999,
                "enabled": False,
            },
        },
    }

    def fake_fetch_batch_prices(all_assets, cat_key):
        assert all_assets is assets
        if cat_key == "etfs":
            return {"0050.TW": 120.0}, {"0050.TW": 2.0}, {"0050.TW": "2026-05-27"}
        if cat_key == "stocks":
            return {"2330.TW": 600.0}, {"2330.TW": 10.0}, {"2330.TW": "2026-05-27"}
        return {}, {}, {}

    monkeypatch.setattr(calculators, "get_assets", lambda: assets)
    monkeypatch.setattr(calculators, "fetch_batch_prices", fake_fetch_batch_prices)

    df, market_share = calculators.calculate_assets_data({"TWD": 1.0, "USD": 30.0})

    assert df[COL_TICKER].tolist() == ["0050.TW", "2330.TW", "FUND", "USD_BANK"]
    assert df[COL_ASSET_TYPE].tolist() == ["ETF", "個股", "基金", "Bank"]
    assert df[COL_MARKET_VALUE].tolist() == [1200, 1200, 1080, 3000]
    assert df[COL_CHANGE].iloc[:2].tolist() == [2.0, 10.0]
    assert pd.isna(df[COL_CHANGE].iloc[2])
    bank_row = df[df[COL_TICKER] == "USD_BANK"].iloc[0]
    assert bank_row[COL_COST] == 0
    assert bank_row[COL_PROFIT_LOSS] == 0
    assert bank_row[COL_RETURN_PCT] == 0
    assert not bool(bank_row[COL_GET_VALUE])
    assert market_share["TW"][COL_MARKET_VALUE] == 2400
    assert market_share["US"][COL_MARKET_VALUE] == 1080
    assert market_share["Bank"][COL_MARKET_VALUE] == 3000
