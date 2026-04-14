# -*- coding: utf-8 -*-
import yfinance as yf
import pandas as pd
import logging
import requests_cache
from functools import lru_cache
from data_loader import get_radar_tickers

# 設定 10 分鐘 (600 秒) 的 Requests 快取，減輕 API 負擔並加速執行
requests_cache.install_cache("asset_tracking_cache", expire_after=600)

# 定義資料抓取器註冊表
FETCHERS = {
    "historical": lambda tickers, **kwargs: yf.download(
        list(tickers),
        period=kwargs.get("period", "2y"),
        progress=kwargs.get("progress", False),
        group_by=kwargs.get("group_by", "ticker"),
        auto_adjust=True,
    ),
    "common": lambda tickers, **kwargs: yf.download(
        list(tickers),
        period=kwargs.get("period", "2y"),
        progress=kwargs.get("progress", False),
        auto_adjust=True,
    ),
}


@lru_cache(maxsize=128)
def get_ticker_fundamental_info(ticker_symbol):
    """獲取 Ticker 的基本面與即時數據，並提供安全性處理"""
    try:
        t = yf.Ticker(ticker_symbol)
        info = t.info

        # 由於台日股數據常缺失，使用 get 確保安全性
        return {
            "name": info.get("shortName") or info.get("longName") or ticker_symbol,
            "eps": info.get("trailingEps", 0) or 0,
            "pe": info.get("trailingPE", 0) or 0,
            "dividendYield": info.get("dividendYield", 0) or 0,
            "pegRatio": info.get("trailingPegRatio", 0) or info.get("pegRatio", 0) or 0,
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
            "volume": 0,
            "avg_volume": 1,
        }


def fetch_historical_data(tickers, period="2y", group_by="ticker"):
    """
    抓取歷史價格數據，並包含特殊標的修正邏輯 (如股票分割修正)
    """
    # 確保 tickers 是字串清單，避免 int 造成的抓取失敗
    if isinstance(tickers, (list, tuple, set)):
        tickers = [str(t) for t in tickers]
    elif not isinstance(tickers, str):
        tickers = str(tickers)

    try:
        df_all = FETCHERS["historical"](tickers, period=period, group_by=group_by)
    except Exception as e:
        logging.error(f"資料抓取器執行失敗: {e}")
        return pd.DataFrame()

    if df_all is None or df_all.empty:
        return pd.DataFrame()

    # --- 歷史數據修正邏輯 (Yahoo Finance 數據錯誤 Patch) ---
    fix_configs = {
        "1306.T": {
            "ratio": 10.0,
            "threshold_factor": 5.0,
            "bug_price": 10000,
            "desc": "日本 1306.T (1:10 分割)",
        },
        "0052.TW": {
            "ratio": 7.0,
            "threshold_factor": 3.0,
            "bug_price": 200,
            "desc": "富邦科技 0052.TW (1:7 分割)",
        },
    }

    target_tickers_list = [tickers] if isinstance(tickers, str) else list(tickers)
    for t_id, cfg in fix_configs.items():
        if t_id in target_tickers_list:
            try:
                if isinstance(df_all.columns, pd.MultiIndex):
                    t_df = df_all[t_id].copy()
                else:
                    t_df = df_all.copy()

                if not t_df.empty and "Close" in t_df.columns:
                    clean_close = t_df["Close"].dropna()
                    if not clean_close.empty:
                        current_p = float(clean_close.iloc[-1])
                        ratio = cfg["ratio"]
                        threshold = current_p * cfg["threshold_factor"]
                        is_global_bug = current_p > cfg["bug_price"]
                        high_price_dates = (
                            t_df.index[t_df["Close"] > threshold]
                            if not is_global_bug
                            else t_df.index
                        )

                        if is_global_bug or not high_price_dates.empty:
                            cols_to_fix = ["Open", "High", "Low", "Close"]
                            if isinstance(df_all.columns, pd.MultiIndex):
                                for col in cols_to_fix:
                                    if (t_id, col) in df_all.columns:
                                        if is_global_bug:
                                            df_all.loc[:, (t_id, col)] /= ratio
                                        else:
                                            df_all.loc[
                                                high_price_dates, (t_id, col)
                                            ] /= ratio
                                if (t_id, "Volume") in df_all.columns:
                                    if is_global_bug:
                                        df_all.loc[:, (t_id, "Volume")] *= ratio
                                    else:
                                        df_all.loc[
                                            high_price_dates, (t_id, "Volume")
                                        ] *= ratio
                            else:
                                available_cols = [
                                    c for c in cols_to_fix if c in df_all.columns
                                ]
                                if is_global_bug:
                                    df_all.loc[:, available_cols] /= ratio
                                    if "Volume" in df_all.columns:
                                        df_all["Volume"] *= ratio
                                else:
                                    df_all.loc[high_price_dates, available_cols] /= (
                                        ratio
                                    )
                                    if "Volume" in df_all.columns:
                                        df_all.loc[high_price_dates, "Volume"] *= ratio
            except Exception as e:
                logging.debug(f"{t_id} 數據修正失敗: {e}")

    # --- 降維處理 ---
    try:
        if isinstance(df_all.columns, pd.MultiIndex):
            all_cols = df_all.columns.tolist()
            tickers_in_df = list(
                set([c[0] if isinstance(c, tuple) else c for c in all_cols])
            )
            if len(tickers_in_df) == 1:
                t_name = tickers_in_df[0]
                df_all = df_all[t_name].copy()
    except Exception as e:
        logging.debug(f"降維處理跳過: {e}")

    return df_all


def fetch_common_data(tickers, period="2y"):
    """抓取基準指數或匯率等共用數據"""
    # 確保 tickers 是字串清單
    if isinstance(tickers, (list, tuple, set)):
        tickers = [str(t) for t in tickers]
    elif not isinstance(tickers, str):
        tickers = str(tickers)

    try:
        return FETCHERS["common"](tickers, period=period)
    except Exception as e:
        logging.error(f"抓取共用數據失敗: {e}")
        return pd.DataFrame()


def get_market_radar_data():
    """抓取市場雷達數據"""
    data = []
    radar_tickers = get_radar_tickers()
    for ticker, name in radar_tickers.items():
        try:
            t = yf.Ticker(ticker)
            # 優先從 fast_info 獲取
            try:
                last_price = t.fast_info["last_price"]
            except Exception:
                # 備援方案：從歷史數據獲取最後收盤價
                hist_1d = t.history(period="1d")
                if not hist_1d.empty:
                    last_price = hist_1d["Close"].iloc[-1]
                else:
                    logging.warning(f"無法獲取雷達數據價格 [{ticker}]")
                    continue

            hist = t.history(period="2d")
            change_pct = (
                ((last_price - hist["Close"].iloc[0]) / hist["Close"].iloc[0] * 100)
                if not hist.empty and len(hist) >= 2
                else 0.0
            )
            data.append(
                {"代碼": ticker, "名稱": name, "數值": last_price, "漲跌幅": change_pct}
            )
        except Exception as e:
            logging.warning(f"無法獲取雷達數據 [{ticker}]: {e}")
    return data
