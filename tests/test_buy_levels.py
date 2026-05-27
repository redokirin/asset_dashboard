# -*- coding: utf-8 -*-
import math

import pandas as pd

from core.buy_levels import (
    MarketData,
    compute_atr20,
    detect_regime,
    get_buy_levels,
    select_atv_model,
)


def test_compute_atr20_uses_true_range():
    df = pd.DataFrame(
        {
            "High": [11.0] * 20,
            "Low": [9.0] * 20,
            "Close": [10.0] * 20,
        }
    )

    assert compute_atr20(df) == 2.0


def test_detect_regime_bull_neutral_bear():
    assert detect_regime(MarketData(100, 30, 20, 10, 1)) == "bull"
    assert detect_regime(MarketData(100, 10, 20, 30, 1)) == "bear"
    assert detect_regime(MarketData(100, 20, 30, 10, 1)) == "neutral"


def test_select_atv_model_prefers_override():
    assert select_atv_model({"atv_model": "ATV_TW", "id": "VOO"}) == "ATV_TW"


def test_select_atv_model_routes_us_etf_cross_listed_on_tse():
    assert select_atv_model({"id": "1655.T", "market": "Japan"}) == "ATV_US"


def test_get_buy_levels_returns_ordered_contract_fields():
    result = get_buy_levels(
        asset={"id": "VOO", "market": "US"},
        data=MarketData(price=120.0, ma20=100.0, ma60=98.0, ma120=96.0, atr20=4.0),
        rs_p10_price=90.0,
    )

    assert result is not None
    assert result["model"] == "ATV_US"
    assert result["regime"] == "bull"
    assert result["trend_center"] == 98.6
    assert result["atr20"] == 4.0

    level_keys = list(result.keys())[:3]
    daily, pullback, sniper = (result[key] for key in level_keys)
    assert daily > pullback > sniper


def test_get_buy_levels_returns_none_when_required_data_missing():
    result = get_buy_levels(
        asset={"id": "VOO"},
        data=MarketData(price=120.0, ma20=100.0, ma60=math.nan, ma120=96.0, atr20=4.0),
    )

    assert result is None

