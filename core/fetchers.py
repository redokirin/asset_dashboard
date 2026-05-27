# -*- coding: utf-8 -*-
"""Compatibility facade for market data fetchers."""

from core.data_sources.cache import install_requests_cache
from core.data_sources.market_radar import get_market_radar_data
from core.data_sources.yahoo import (
    FETCHERS,
    fetch_common_data,
    fetch_historical_data,
    get_ticker_fundamental_info,
)


install_requests_cache()
