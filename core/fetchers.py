# -*- coding: utf-8 -*-
import yfinance as yf
import pandas as pd
import logging
import requests_cache
from functools import lru_cache
from core.data_loader import get_radar_tickers

# 設定 10 分鐘 (600 秒) 的 Requests 快取，減輕 API 負擔並加速執行
requests_cache.install_cache("asset_tracking_cache", expire_after=600)

# 定義資料抓取器註冊表
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


@lru_cache(maxsize=128)
def get_ticker_fundamental_info(ticker_symbol):
    """獲取 Ticker 的基本面與即時數據，並提供安全性處理"""
    try:
        t = yf.Ticker(ticker_symbol)
        info = t.info

        # 由於台日股數據常缺失，使用 get 確保安全性
        raw_dy = info.get("dividendYield", 0) or 0
        y_yd = info.get("yield", 0) or 0

        final_dy = 0
        if y_yd > 0:
            final_dy = y_yd
        else:
            calc_dy = (info.get("dividendRate", 0) or 0) / (
                info.get("previousClose", 1) or 1
            )
            if calc_dy > 0 and raw_dy > 0:
                if abs(raw_dy / 100.0 - calc_dy) < abs(raw_dy - calc_dy):
                    final_dy = raw_dy / 100.0
                else:
                    final_dy = raw_dy
            elif raw_dy > 0:
                # 預設多數股票 dividendYield 為百分制 (例如 1.18)
                final_dy = raw_dy / 100.0

        return {
            "name": info.get("shortName") or info.get("longName") or ticker_symbol,
            "eps": info.get("trailingEps", 0) or 0,
            "pe": info.get("trailingPE", 0) or 0,
            "dividendYield": final_dy,
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
        if df_all is not None:
            df_all = df_all.copy()
    except Exception as e:
        logging.error(f"資料抓取器執行失敗: {e}")
        return pd.DataFrame()

    if df_all is None or df_all.empty:
        return pd.DataFrame()

    # 統一 MultiIndex 方向為 (Ticker, Price)
    # yfinance 單 ticker 無 group_by 時可能回傳 (Price, Ticker) 結構
    if isinstance(df_all.columns, pd.MultiIndex) and df_all.columns.nlevels == 2:
        price_fields = {"open", "high", "low", "close", "volume", "adjclose", "adj close"}
        lv0_unique = {str(v).lower().replace(" ", "") for v in df_all.columns.get_level_values(0).unique()}
        if lv0_unique.issubset(price_fields):
            df_all = df_all.swaplevel(axis=1).sort_index(axis=1)

    # --- 歷史數據修正邏輯 (Yahoo Finance 數據錯誤 Patch) ---
    fix_configs = {
        "1306.T": {
            "ratio": 10.0,
            "threshold_factor": 3.5,
            "bug_price": 1000,
            "desc": "日本 1306.T (1:10 分割)",
        },
        "0052.TW": {
            "ratio": 7.0,
            "threshold_factor": 2.5,
            "bug_price": 80,
            "desc": "富邦科技 0052.TW (1:7 分割)",
        },
    }

    # 轉為大寫集合進行比對，增加穩健性
    target_tickers_set = {
        str(t).upper()
        for t in ([tickers] if isinstance(tickers, str) else list(tickers))
    }

    for t_id, cfg in fix_configs.items():
        if t_id.upper() in target_tickers_set:
            try:
                # 獲取該 Ticker 的數據視圖 (不分大小寫)
                ticker_key = None
                if isinstance(df_all.columns, pd.MultiIndex):
                    level0 = df_all.columns.get_level_values(0).unique()
                    for l0 in level0:
                        if str(l0).upper() == t_id.upper():
                            ticker_key = l0
                            break
                    if ticker_key:
                        t_df = df_all[ticker_key]
                    else:
                        continue
                else:
                    t_df = df_all
                    ticker_key = t_id  # 佔位

                if not t_df.empty:
                    # 尋找 Close 欄位 (不分大小寫)
                    close_col = None
                    for c in t_df.columns:
                        c_clean = str(c).lower().replace(" ", "")
                        if c_clean in ["close", "adjclose"]:
                            close_col = c
                            break

                    if close_col:
                        # 確保數據為數值型態
                        close_series = pd.to_numeric(t_df[close_col], errors="coerce")
                        clean_close = close_series.dropna()

                        if not clean_close.empty:
                            current_p = float(clean_close.iloc[-1])
                            ratio = cfg["ratio"]
                            threshold = current_p * cfg["threshold_factor"]

                            is_global_bug = current_p > cfg["bug_price"]

                            # 修正邏輯改進：
                            # 1. 若現價就已經過高，判定為全域錯誤。
                            # 2. 若現價正常但歷史有高價，則將「最後一個異常高價日期」之前的所有數據一併修正，避免遺漏。
                            if is_global_bug:
                                fix_dates = t_df.index
                            else:
                                abnormal_mask = close_series > threshold
                                if abnormal_mask.any():
                                    last_abnormal_date = t_df.index[abnormal_mask].max()
                                    fix_dates = t_df.index[
                                        t_df.index <= last_abnormal_date
                                    ]
                                else:
                                    fix_dates = pd.Index([])

                            if not fix_dates.empty:
                                # 需要修正的欄位關鍵字 (含 Adj Close)
                                fix_keywords = [
                                    "open",
                                    "high",
                                    "low",
                                    "close",
                                    "adjclose",
                                ]

                                for col_actual in t_df.columns:
                                    col_lower = str(col_actual).lower().replace(" ", "")
                                    if col_lower in fix_keywords:
                                        if isinstance(df_all.columns, pd.MultiIndex):
                                            df_all.loc[
                                                fix_dates, (ticker_key, col_actual)
                                            ] /= ratio
                                        else:
                                            df_all.loc[fix_dates, col_actual] /= ratio

                                    elif col_lower == "volume":
                                        if isinstance(df_all.columns, pd.MultiIndex):
                                            df_all.loc[
                                                fix_dates, (ticker_key, col_actual)
                                            ] *= ratio
                                        else:
                                            df_all.loc[fix_dates, col_actual] *= ratio

                                logging.info(
                                    f"已套用 {cfg['desc']} 修正補丁 (範圍: {len(fix_dates)} 筆數據)"
                                )
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
