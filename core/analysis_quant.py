# -*- coding: utf-8 -*-
"""Compatibility facade for advanced quantitative analysis."""

from core.analysis import advanced as _advanced
from core.analysis.benchmark import get_smart_benchmark
from core.analysis.diagnosis import generate_advanced_diagnosis
from core.analysis.technical import (
    calculate_alpha_metrics as _calculate_alpha_metrics,
    calculate_drawdown_metrics as _calculate_drawdown_metrics,
    calculate_moving_averages as _calculate_moving_averages,
    calculate_rsi as _calculate_rsi,
    extract_ticker_frame as _extract_ticker_frame,
    get_clean_col as _get_clean_col,
    to_float_scalar as _to_float_scalar,
)
from core.fetchers import (
    fetch_common_data,
    fetch_historical_data,
    get_ticker_fundamental_info,
)


def run_advanced_analysis(df_res):
    """Run advanced analysis while preserving monkeypatch compatibility."""
    _advanced.fetch_common_data = fetch_common_data
    _advanced.fetch_historical_data = fetch_historical_data
    _advanced.get_ticker_fundamental_info = get_ticker_fundamental_info
    _advanced.get_smart_benchmark = get_smart_benchmark
    _advanced.generate_advanced_diagnosis = generate_advanced_diagnosis
    return _advanced.run_advanced_analysis(df_res)
