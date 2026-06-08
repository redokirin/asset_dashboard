# -*- coding: utf-8 -*-
import logging
from functools import lru_cache

import pandas as pd
import yfinance as yf

from core.data_sources.patches import apply_yahoo_price_patches


FETCHERS = {
    "historical": lambda tickers, **kwargs: yf.download(
        tickers if isinstance(tickers, list) else [tickers],
        period=kwargs.get("period", "2y"),
        progress=kwargs.get("progress", False),
        group_by=kwargs.get("group_by", "ticker"),
        auto_adjust=True,
    ),
    "common": lambda tickers, **kwargs: yf.download(
        tickers if isinstance(tickers, list) else [tickers],
        period=kwargs.get("period", "2y"),
        progress=kwargs.get("progress", False),
        auto_adjust=True,
    ),
}


def normalize_tickers(tickers):
    """Normalize ticker input before passing it to yfinance."""
    if isinstance(tickers, (list, tuple, set)):
        return [str(ticker) for ticker in tickers]
    if not isinstance(tickers, str):
        return str(tickers)
    return tickers


def normalize_yfinance_columns(df_all):
    """Normalize yfinance MultiIndex columns to (Ticker, Price)."""
    if not isinstance(df_all.columns, pd.MultiIndex) or df_all.columns.nlevels != 2:
        return df_all

    price_fields = {"open", "high", "low", "close", "volume", "adjclose", "adjclose"}
    level0 = {
        str(value).lower().replace(" ", "")
        for value in df_all.columns.get_level_values(0).unique()
    }
    if level0.issubset(price_fields):
        return df_all.swaplevel(axis=1).sort_index(axis=1)
    return df_all


def squeeze_single_ticker_frame(df_all):
    """Keep historical facade compatible for single-ticker yfinance responses."""
    try:
        if isinstance(df_all.columns, pd.MultiIndex):
            tickers_in_df = list(
                {column[0] if isinstance(column, tuple) else column for column in df_all.columns}
            )
            if len(tickers_in_df) == 1:
                return df_all[tickers_in_df[0]].copy()
    except Exception as exc:
        logging.debug(f"降維處理跳過: {exc}")
    return df_all


@lru_cache(maxsize=128)
def get_ticker_fundamental_info(ticker_symbol):
    """獲取 Ticker 的基本面與即時數據，並提供安全性處理"""
    try:
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.info

        raw_dividend_yield = info.get("dividendYield", 0) or 0
        yahoo_yield = info.get("yield", 0) or 0

        final_dividend_yield = 0
        if yahoo_yield > 0:
            final_dividend_yield = yahoo_yield
        else:
            calculated_yield = (info.get("dividendRate", 0) or 0) / (
                info.get("previousClose", 1) or 1
            )
            if calculated_yield > 0 and raw_dividend_yield > 0:
                if abs(raw_dividend_yield / 100.0 - calculated_yield) < abs(
                    raw_dividend_yield - calculated_yield
                ):
                    final_dividend_yield = raw_dividend_yield / 100.0
                else:
                    final_dividend_yield = raw_dividend_yield
            elif raw_dividend_yield > 0:
                final_dividend_yield = raw_dividend_yield / 100.0

        return {
            "name": info.get("shortName") or info.get("longName") or ticker_symbol,
            "eps": info.get("trailingEps", 0) or 0,
            "pe": info.get("trailingPE", 0) or 0,
            "dividendYield": final_dividend_yield,
            "pegRatio": info.get("trailingPegRatio", 0) or info.get("pegRatio", 0) or 0,
            "priceToBook": info.get("priceToBook", 0) or 0,
            "volume": info.get("volume", 0) or 0,
            "avg_volume": info.get("averageVolume", 1) or 1,
        }
    except Exception:
        return {
            "name": ticker_symbol,
            "eps": 0,
            "pe": 0,
            "dividendYield": 0,
            "pegRatio": 0,
            "priceToBook": 0,
            "volume": 0,
            "avg_volume": 1,
        }


def fetch_historical_data(tickers, period="2y", group_by="ticker", fetchers=None):
    """抓取歷史價格數據，並包含特殊標的修正邏輯"""
    normalized_tickers = normalize_tickers(tickers)
    if not normalized_tickers:
        return pd.DataFrame()

    active_fetchers = fetchers or FETCHERS
    try:
        df_all = active_fetchers["historical"](
            normalized_tickers, period=period, group_by=group_by
        )
        if df_all is not None:
            df_all = df_all.copy()
    except Exception as exc:
        logging.error(f"資料抓取器執行失敗: {exc}")
        return pd.DataFrame()

    if df_all is None or df_all.empty:
        return pd.DataFrame()

    df_all = normalize_yfinance_columns(df_all)
    df_all = apply_yahoo_price_patches(df_all, normalized_tickers)
    return squeeze_single_ticker_frame(df_all)


def fetch_ohlc(ticker: str, date: str) -> dict | None:
    """
    取得指定日期的單日 OHLC。date 格式：'2026-06-08'。
    回傳 {"open", "high", "low", "close"} 或 None。
    """
    try:
        from datetime import datetime, timedelta
        next_day = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        df = yf.download(ticker, start=date, end=next_day,
                         interval="1d", auto_adjust=True, progress=False)
        if df is None or df.empty:
            return None
        df = normalize_yfinance_columns(df)
        df = squeeze_single_ticker_frame(df)
        if df.empty:
            return None
        row = df.iloc[0]
        return {
            "open":  float(row["Open"]),
            "high":  float(row["High"]),
            "low":   float(row["Low"]),
            "close": float(row["Close"]),
        }
    except Exception as exc:
        logging.warning(f"[yahoo] fetch_ohlc {ticker} {date} 失敗: {exc}")
        return None


def fetch_common_data(tickers, period="2y", fetchers=None):
    """抓取基準指數或匯率等共用數據"""
    normalized_tickers = normalize_tickers(tickers)
    if not normalized_tickers:
        return pd.DataFrame()

    active_fetchers = fetchers or FETCHERS
    try:
        df = active_fetchers["common"](normalized_tickers, period=period)
    except Exception as exc:
        logging.error(f"抓取共用數據失敗: {exc}")
        return pd.DataFrame()

    if df is None or df.empty:
        return pd.DataFrame()

    df = normalize_yfinance_columns(df)
    df = apply_yahoo_price_patches(df, normalized_tickers)
    return df
