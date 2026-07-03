# -*- coding: utf-8 -*-
import logging

import pandas as pd
import numpy as np

from core.risk import calculate_asset_drawdown


def _remove_price_spikes(df: pd.DataFrame, factor: float = 3.0, label: str = "") -> pd.DataFrame:
    """
    移除價格超出 5 日 rolling median `factor` 倍的資料點。
    防止 yfinance 回傳單日錯誤 adjusted close 污染波動率 / MDD 計算。
    若清理後不足 20 筆則 fallback 回原始資料（避免短歷史標的被過度過濾）。

    label: 供 log 識別是哪個標的/基準的過濾結果（不影響計算）。
    """
    if len(df) < 10:
        return df
    close = df["Close"]
    med = close.rolling(5, center=True, min_periods=2).median()
    valid = (close <= med * factor) & (close >= med / factor)
    # NaN 跟任何數字比較都是 False，會被 valid 判定為要丟棄，但那只是缺盤日
    # （例如多檔一起批次下載時，其他市場交易但當地休市造成的日期對齊空值），
    # 不是真正的價格異常，計數/log 時要排除，只算真正超出 rolling median 的暴衝點
    n_spikes = int(((~valid) & close.notna()).sum())
    if n_spikes:
        tag = f"{label} " if label else ""
        logging.warning(f"[technical] {tag}移除 {n_spikes} 筆異常價格點（超出 rolling median {factor}×）")
    cleaned = df[valid].copy()
    return cleaned if len(cleaned) >= 20 else df


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


def calculate_drawdown_metrics(t_df_clean, sharpe, label=""):
    t_df_clean = _remove_price_spikes(t_df_clean, label=label)

    drawdown_result = None
    if len(t_df_clean) >= 2:
        price_history = [
            {"date": str(idx.date()), "value": float(value)}
            for idx, value in zip(t_df_clean.index, t_df_clean["Close"])
            if pd.notnull(value) and float(value) > 0
        ]
        drawdown_result = calculate_asset_drawdown(price_history)

    # 年化波動率（日常波動特性，不受系統性股災影響）
    annualized_vol = 0.0
    vol_grade = "數據不足"
    if len(t_df_clean) >= 20:
        daily_returns = t_df_clean["Close"].pct_change().dropna()
        annualized_vol = float(daily_returns.std() * (252 ** 0.5))
        if annualized_vol < 0.15:
            vol_grade = "低波動"
        elif annualized_vol <= 0.30:
            vol_grade = "中波動"
        else:
            vol_grade = "高波動"

    sharpe_norm = min(1.0, max(0.0, sharpe / 2.0))
    pain_num = min(1.0, drawdown_result.painRatio if drawdown_result else 0.5)

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

    # 歷史越短，指標可信度越低，向中性值 0.5 收斂
    confidence = maturity_score

    # 波動度分數取代 MDD/comfort 在持有力中的角色：波動越低分數越高
    # 合理波動範圍 0–40%，超過 40% 視為極高波動
    vol_norm = min(1.0, annualized_vol / 0.40) if annualized_vol > 0 else 0.5
    vol_score = 1.0 - vol_norm
    vol_score_adjusted = 0.5 + (vol_score - 0.5) * confidence

    sharpe_adjusted = 0.5 + (sharpe_norm - 0.5) * confidence
    pain_adjusted = 0.5 + ((1.0 - pain_num) - 0.5) * confidence

    hold_ability_score = round(
        0.35 * vol_score_adjusted
        + 0.25 * sharpe_adjusted
        + 0.20 * pain_adjusted
        + 0.20 * maturity_score,
        4,
    )
    return (
        drawdown_result,
        hold_ability_score,
        maturity_score,
        round(history_years, 1),
        annualized_vol,
        vol_grade,
    )
