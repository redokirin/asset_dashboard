# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np

from core.risk import calculateAssetDrawdown


def to_float_scalar(value) -> float | None:
    """yfinance MultiIndex 邊界情況下 .iloc[-1] 可能回傳 Series，統一轉為 float scalar。"""
    if isinstance(value, pd.Series):
        value = value.iloc[0]
    return float(value) if pd.notnull(value) else None


def get_clean_col(df, ticker_name, col_name):
    try:
        if isinstance(df.columns, pd.MultiIndex):
            if ticker_name in df.columns.get_level_values(0):
                series = df.xs(ticker_name, axis=1, level=0)[col_name]
            else:
                series = df[col_name]
        else:
            series = df[col_name]
        if isinstance(series.index, pd.MultiIndex):
            series.index = series.index.get_level_values(0)
        series.index = pd.to_datetime(series.index)
        if hasattr(series.index, "tz") and series.index.tz is not None:
            series.index = series.index.tz_localize(None)
        if isinstance(series, pd.DataFrame):
            series = series.iloc[:, 0]
        return series
    except Exception:
        return pd.Series()


def extract_ticker_frame(t_data_all_raw, ticker):
    if isinstance(t_data_all_raw.columns, pd.MultiIndex):
        if ticker not in t_data_all_raw.columns.get_level_values(0):
            return None
        ticker_df = t_data_all_raw.xs(ticker, axis=1, level=0).copy()
    else:
        ticker_df = t_data_all_raw.copy()

    if isinstance(ticker_df.columns, pd.MultiIndex):
        ticker_df.columns = ticker_df.columns.get_level_values(-1)
    ticker_df.index = pd.to_datetime(ticker_df.index)
    if hasattr(ticker_df.index, "tz") and ticker_df.index.tz is not None:
        ticker_df.index = ticker_df.index.tz_localize(None)

    if "Close" not in ticker_df.columns:
        return None

    clean_df = ticker_df[ticker_df["Close"].notnull()].copy()
    return clean_df if not clean_df.empty else None


def calculate_moving_averages(t_df_clean):
    ma_values = {
        "ma5": None,
        "ma20": None,
        "ma60": None,
        "ma120": None,
        "ma250": None,
    }
    ma_labels = {"ma20": "-", "ma60": "數據不足", "ma120": "數據不足", "ma250": "-"}

    windows = [
        (5, "ma5"),
        (20, "ma20"),
        (60, "ma60"),
        (120, "ma120"),
        (250, "ma250"),
    ]
    for window, key in windows:
        if len(t_df_clean) >= window:
            ma_values[key] = to_float_scalar(
                t_df_clean["Close"].rolling(window).mean().iloc[-1]
            )

    for key in ["ma20", "ma60", "ma120", "ma250"]:
        if ma_values[key] is not None:
            ma_labels[key] = f"{ma_values[key]:.2f}"

    return ma_values, ma_labels


def calculate_rsi(t_df_clean):
    if len(t_df_clean) < 15:
        return 0.0

    delta = t_df_clean["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    with np.errstate(divide="ignore", invalid="ignore"):
        rs_val = gain / loss
        rsi_series = 100 - (100 / (1 + rs_val))
    return float(rsi_series.iloc[-1]) if not pd.isna(rsi_series.iloc[-1]) else 0.0


def calculate_alpha_metrics(comb):
    monthly_price = comb.resample("ME").last()
    monthly_return = pd.DataFrame(
        {
            "target_ret": (monthly_price["p"] * monthly_price["r"]).pct_change(),
            "bench_ret": monthly_price["b"].pct_change(),
        }
    ).dropna()

    if monthly_return.empty or len(monthly_return) < 2:
        return monthly_return, 0.0, 0.0, 0.0

    monthly_return["Alpha"] = monthly_return["target_ret"] - monthly_return["bench_ret"]
    avg_alpha = monthly_return["Alpha"].mean() * 100
    benchmark_alpha_trailing_avg = (monthly_return["Alpha"] > 0).mean() * 100
    std_return = monthly_return["target_ret"].std()
    sharpe = (
        monthly_return["target_ret"].mean() / std_return * (12**0.5)
        if std_return != 0
        else 0.0
    )
    return monthly_return, benchmark_alpha_trailing_avg, avg_alpha, sharpe


def calculate_drawdown_metrics(t_df_clean, sharpe):
    drawdown_result = None
    if len(t_df_clean) >= 2:
        price_history = [
            {"date": str(idx.date()), "value": float(value)}
            for idx, value in zip(t_df_clean.index, t_df_clean["Close"])
            if pd.notnull(value) and float(value) > 0
        ]
        drawdown_result = calculateAssetDrawdown(price_history)

    comfort_map = {"High": 1.0, "Medium": 0.5, "Low": 0.0}
    comfort_num = comfort_map.get(
        drawdown_result.comfortScore if drawdown_result else None, 0.5
    )
    sharpe_norm = min(1.0, max(0.0, sharpe / 2.0))
    pain_num = drawdown_result.painRatio if drawdown_result else 0.5

    history_years = (
        (t_df_clean.index[-1] - t_df_clean.index[0]).days / 365.25
        if len(t_df_clean) >= 2
        else 0.0
    )
    if history_years >= 10:
        maturity_score = 1.0
    elif history_years >= 5:
        maturity_score = 0.8
    elif history_years >= 2:
        maturity_score = 0.6
    else:
        maturity_score = 0.4

    holdability_score = round(
        0.35 * comfort_num
        + 0.25 * sharpe_norm
        + 0.20 * (1.0 - pain_num)
        + 0.20 * maturity_score,
        4,
    )
    return drawdown_result, holdability_score, maturity_score, round(history_years, 1)
