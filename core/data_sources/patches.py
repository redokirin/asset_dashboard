# -*- coding: utf-8 -*-
import logging

import pandas as pd


YAHOO_PRICE_PATCH_CONFIGS = {
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


def _matching_ticker_key(columns, ticker_id):
    level0 = columns.get_level_values(0).unique()
    for value in level0:
        if str(value).upper() == ticker_id.upper():
            return value
    return None


def _close_column(columns):
    for column in columns:
        column_key = str(column).lower().replace(" ", "")
        if column_key in ["close", "adjclose"]:
            return column
    return None


def apply_yahoo_price_patches(df_all, tickers, fix_configs=None):
    """Apply known Yahoo Finance split/data repair patches."""
    if df_all is None or df_all.empty:
        return df_all

    patched = df_all.copy()
    fix_configs = fix_configs or YAHOO_PRICE_PATCH_CONFIGS
    ticker_list = [tickers] if isinstance(tickers, str) else list(tickers)
    target_tickers = {str(t).upper() for t in ticker_list}

    for ticker_id, config in fix_configs.items():
        if ticker_id.upper() not in target_tickers:
            continue

        try:
            ticker_key = ticker_id
            if isinstance(patched.columns, pd.MultiIndex):
                ticker_key = _matching_ticker_key(patched.columns, ticker_id)
                if ticker_key is None:
                    continue
                ticker_df = patched[ticker_key]
            else:
                ticker_df = patched

            if ticker_df.empty:
                continue

            close_col = _close_column(ticker_df.columns)
            if close_col is None:
                continue

            close_series = pd.to_numeric(ticker_df[close_col], errors="coerce")
            clean_close = close_series.dropna()
            if clean_close.empty:
                continue

            current_price = float(clean_close.iloc[-1])
            ratio = config["ratio"]
            threshold = current_price * config["threshold_factor"]

            if current_price > config["bug_price"]:
                fix_dates = ticker_df.index
            else:
                abnormal_mask = close_series > threshold
                if abnormal_mask.any():
                    last_abnormal_date = ticker_df.index[abnormal_mask].max()
                    fix_dates = ticker_df.index[ticker_df.index <= last_abnormal_date]
                else:
                    fix_dates = pd.Index([])

            if fix_dates.empty:
                continue

            for column in ticker_df.columns:
                column_key = str(column).lower().replace(" ", "")
                if column_key in ["open", "high", "low", "close", "adjclose"]:
                    if isinstance(patched.columns, pd.MultiIndex):
                        patched.loc[fix_dates, (ticker_key, column)] /= ratio
                    else:
                        patched.loc[fix_dates, column] /= ratio
                elif column_key == "volume":
                    if isinstance(patched.columns, pd.MultiIndex):
                        patched.loc[fix_dates, (ticker_key, column)] *= ratio
                    else:
                        patched.loc[fix_dates, column] *= ratio

            logging.info(
                f"已套用 {config['desc']} 修正補丁 (範圍: {len(fix_dates)} 筆數據)"
            )
        except Exception as exc:
            logging.debug(f"{ticker_id} 數據修正失敗: {exc}")

    return patched
