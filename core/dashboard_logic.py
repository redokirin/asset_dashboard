# -*- coding: utf-8 -*-
"""
dashboard_logic.py - 業務邏輯外觀模組 (Facade)
此檔案整合了所有子模組的功能，並維持既有的 API 相容性。
"""

import logging
from core.data_loader import get_assets, get_radar_tickers, get_config, get_secret
from core.fetchers import (
    get_ticker_fundamental_info, 
    fetch_historical_data, 
    fetch_common_data, 
    get_market_radar_data,
    FETCHERS
)
from core.calculators import calculate_tick_price, exchange_rate, calculate_assets_data
from core.analysis_quant import (
    calculate_buffered_entries, 
    generate_advanced_diagnosis, 
    run_advanced_analysis
)
from core.exporters import export_for_ai

# 設定全域日誌配置
logging.basicConfig(
    level=logging.WARNING, format="%(asctime)s - [%(levelname)s] - %(message)s"
)

# 為了相容性保留 HAS_SCIPY 標記
try:
    from scipy import stats
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
