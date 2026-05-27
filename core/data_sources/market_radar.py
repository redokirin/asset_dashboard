# -*- coding: utf-8 -*-
import logging

import yfinance as yf

from core.columns import COL_CHANGE_PCT, COL_NAME, COL_TICKER, COL_VALUE
from core.data_loader import get_radar_tickers


def get_market_radar_data(ticker_factory=yf.Ticker, radar_tickers_provider=get_radar_tickers):
    """抓取市場雷達數據"""
    data = []
    radar_tickers = radar_tickers_provider()
    for ticker, name in radar_tickers.items():
        try:
            ticker_data = ticker_factory(ticker)
            try:
                last_price = ticker_data.fast_info["last_price"]
            except Exception:
                hist_1d = ticker_data.history(period="1d")
                if not hist_1d.empty:
                    last_price = hist_1d["Close"].iloc[-1]
                else:
                    logging.warning(f"無法獲取雷達數據價格 [{ticker}]")
                    continue

            hist = ticker_data.history(period="2d")
            change_pct = (
                ((last_price - hist["Close"].iloc[0]) / hist["Close"].iloc[0] * 100)
                if not hist.empty and len(hist) >= 2
                else 0.0
            )
            data.append(
                {
                    COL_TICKER: ticker,
                    COL_NAME: name,
                    COL_VALUE: last_price,
                    COL_CHANGE_PCT: change_pct,
                }
            )
        except Exception as exc:
            logging.warning(f"無法獲取雷達數據 [{ticker}]: {exc}")
    return data
