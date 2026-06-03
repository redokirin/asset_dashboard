# -*- coding: utf-8 -*-
import logging

import numpy as np
import pandas as pd

from core.analysis.benchmark import get_smart_benchmark
from core.analysis.diagnosis import generate_advanced_diagnosis
from core.analysis.technical import (
    calculate_alpha_metrics,
    calculate_drawdown_metrics,
    calculate_moving_averages,
    calculate_rsi,
    extract_ticker_frame,
    get_clean_col,
    to_float_scalar,
)
from core.buy_levels import MarketData, compute_atr20, get_buy_levels
from core.columns import (
    COL_ASSET_TYPE,
    COL_BUY_LEVELS,
    COL_COMFORT_SCORE,
    COL_CURRENCY,
    COL_DAILY_LEVEL,
    COL_GET_VALUE,
    COL_HISTORY_YEARS,
    COL_HOLD_ABILITY_SCORE,
    COL_MATURITY_SCORE,
    COL_NAME,
    COL_PRICE,
    COL_PULLBACK_LEVEL,
    COL_SNIPER_LEVEL,
    COL_TECH_DIAGNOSIS,
    COL_TICKER,
)
from core.fetchers import (
    fetch_common_data,
    fetch_historical_data,
    get_ticker_fundamental_info,
)
from core.risk import calculate_asset_drawdown


def run_advanced_analysis(df_res):
    """
    合併執行 RS (相對強度) 與 Alpha (穩定性) 進階分析。
    自動處理幣別轉換與 Smart Benchmarking 對齊。
    """
    try:
        from scipy import stats
    except ImportError:
        logging.error(
            "🚨 缺少 scipy 套件，無法執行進階診斷。請執行 `poetry add scipy`。"
        )
        return pd.DataFrame()

    if COL_GET_VALUE in df_res.columns:
        df_to_analyze = df_res[df_res[COL_GET_VALUE] == True]
    else:
        df_to_analyze = df_res

    active_tickers = df_to_analyze[COL_TICKER].tolist()

    results = []
    try:
        required_benchmarks = {get_smart_benchmark(t) for t in active_tickers}
        all_bench_tickers = list(required_benchmarks) + ["JPYTWD=X", "USDTWD=X"]
        logging.info(f"正在批次抓取智能基準數據: {all_bench_tickers}")
        common_raw = fetch_common_data(tuple(all_bench_tickers), period="2y")

        t_data_all_raw = fetch_historical_data(
            tuple(active_tickers), period="2y", group_by="ticker"
        )

        for ticker in active_tickers:
            try:
                row_data = df_to_analyze[df_to_analyze[COL_TICKER] == ticker].iloc[0]
                asset_type = row_data.get(COL_ASSET_TYPE, "個股")

                current_benchmark = get_smart_benchmark(ticker)
                b_series_final = get_clean_col(common_raw, current_benchmark, "Close")

                if b_series_final.empty:
                    logging.warning(
                        f"標的 {ticker} 的基準 {current_benchmark} 無數據，跳過分析"
                    )
                    continue

                bench_price_history = [
                    {"date": str(idx.date()), "value": float(v)}
                    for idx, v in b_series_final.items()
                    if pd.notnull(v) and float(v) > 0
                ]
                bench_drawdown = calculate_asset_drawdown(bench_price_history)
                bench_mdd = bench_drawdown.maxDrawdownPercent if bench_drawdown else None

                t_df_clean = extract_ticker_frame(t_data_all_raw, ticker)
                if t_df_clean is None:
                    continue

                price_val = to_float_scalar(t_df_clean["Close"].iloc[-1])
                prev_close = (
                    to_float_scalar(t_df_clean["Close"].iloc[-2])
                    if len(t_df_clean) >= 2
                    else price_val
                )

                day_change_pct = ((price_val - prev_close) / prev_close) * 100

                ma_values, ma_labels = calculate_moving_averages(t_df_clean)
                ma5_val = ma_values["ma5"]
                ma20_val = ma_values["ma20"]
                ma60_val = ma_values["ma60"]
                ma120_val = ma_values["ma120"]
                ma250_val = ma_values["ma250"]
                ma20_str = ma_labels["ma20"]
                ma60_str = ma_labels["ma60"]
                ma120_str = ma_labels["ma120"]
                ma250_str = ma_labels["ma250"]

                bias_str, bias_numeric = "-", float("nan")
                if ma20_val is not None and ma20_val > 0:
                    bias_numeric = ((price_val - ma20_val) / ma20_val) * 100
                    bias_str = f"{bias_numeric:.2f}%"

                p_series = t_df_clean["Close"].copy()
                if isinstance(p_series, pd.DataFrame):
                    p_series = p_series.iloc[:, 0]

                ccy = str(row_data.get(COL_CURRENCY, "")).strip().upper()
                if ccy not in {"TWD", "USD", "JPY"}:
                    if ticker.endswith(".T"):
                        ccy = "JPY"
                    elif ticker.endswith((".TW", ".TWO")):
                        ccy = "TWD"
                    else:
                        ccy = "USD"
                if ccy == "JPY":
                    r_series = get_clean_col(common_raw, "JPYTWD=X", "Close")
                elif ccy == "USD":
                    r_series = get_clean_col(common_raw, "USDTWD=X", "Close")
                else:
                    r_series = 1.0

                comb_dict = {"p": p_series, "b": b_series_final}
                if isinstance(r_series, (pd.Series, pd.DataFrame)):
                    comb_dict["r"] = r_series
                comb = pd.DataFrame(comb_dict).ffill()
                if "r" not in comb.columns:
                    comb["r"] = 1.0
                comb = comb[comb["p"].notnull() & comb["b"].notnull()]

                if comb.empty:
                    continue

                rs_series = comb["p"] / comb["b"]
                if len(rs_series) < 20:
                    continue
                curr_rs = float(rs_series.iloc[-1])
                pct = stats.percentileofscore(rs_series.values.flatten(), curr_rs)

                rsi_val = calculate_rsi(t_df_clean)

                rs_p10 = float(np.percentile(rs_series.values.flatten(), 10))
                rs_p10_price = rs_p10 * comb["b"].iloc[-1]

                # Self-benchmark 標的 (ticker == benchmark) RS ≡ 1.0，
                # rs_p10_price 會卡在現價附近，反而讓 sniper 失去狙擊意義 — 此時不傳。
                if current_benchmark == ticker:
                    rs_p10_price = None

                suggested_bid_str = "-"
                daily_wave, tech_retest, sniper_pos = "-", "-", "-"
                entries = None
                if (
                    ma20_val is not None
                    and ma60_val is not None
                    and ma120_val is not None
                ):
                    if not {"High", "Low", "Close"}.issubset(t_df_clean.columns):
                        logging.debug(f"[{ticker}] 買點計算跳過：缺少 OHLC 欄位")
                    else:
                        try:
                            atr20_val = compute_atr20(t_df_clean)
                        except Exception:
                            atr20_val = None
                        if atr20_val is None or pd.isna(atr20_val):
                            logging.debug(f"[{ticker}] 買點計算跳過：ATR20 無法計算")
                        else:
                            market_data = MarketData(
                                price=price_val,
                                ma20=ma20_val,
                                ma60=ma60_val,
                                ma120=ma120_val,
                                atr20=float(atr20_val),
                            )
                            entries = get_buy_levels(
                                asset=row_data.to_dict(),
                                data=market_data,
                                rs_p10_price=rs_p10_price,
                            )
                else:
                    missing = [
                        name
                        for name, value in [("MA60", ma60_val), ("MA120", ma120_val)]
                        if value is None
                    ]
                    if missing:
                        logging.debug(
                            f"[{ticker}] 買點計算跳過：{', '.join(missing)} 資料不足"
                        )
                if entries:
                    suggested_bid_str = f"{entries['日常波段']:.2f} | {entries['技術回測']:.2f} | {entries['狙擊位']:.2f}"
                    daily_wave, tech_retest, sniper_pos = (
                        f"{entries['日常波段']:.2f}",
                        f"{entries['技術回測']:.2f}",
                        f"{entries['狙擊位']:.2f}",
                    )

                m_ret, bat_avg, avg_alpha, sharpe = calculate_alpha_metrics(comb)

                fundamentals = get_ticker_fundamental_info(ticker)
                vol_ratio = (
                    fundamentals["volume"] / fundamentals["avg_volume"]
                    if fundamentals["avg_volume"] > 0
                    else 1.0
                )

                alpha_win_str = f"{bat_avg:.1f}%" if not m_ret.empty else "0%"

                (
                    drawdown_result,
                    hold_ability_score,
                    maturity_score,
                    history_years,
                ) = calculate_drawdown_metrics(t_df_clean, sharpe)

                full_diag_text, tags = generate_advanced_diagnosis(
                    bias=bias_numeric,
                    sharpe=sharpe,
                    rs_percentile=pct,
                    ticker=ticker,
                    price_change_pct=day_change_pct,
                    vol_ratio=vol_ratio,
                    rsi=rsi_val,
                    price=price_val,
                    ma5=ma5_val,
                    ma20=ma20_val,
                    ma250=ma250_val,
                    eps=fundamentals.get("eps"),
                    pe_ratio=fundamentals.get("pe"),
                    dividend_yield=fundamentals.get("dividendYield"),
                    peg_ratio=fundamentals.get("pegRatio"),
                    pb_ratio=fundamentals.get("priceToBook"),
                    asset_type=asset_type,
                    alpha_win_rate=alpha_win_str,
                    history_years=history_years,
                )

                results.append(
                    {
                        COL_TICKER: ticker,
                        COL_NAME: fundamentals.get("name", ticker),
                        COL_PRICE: f"{price_val:.2f}",
                        "乖離率 (Bias)": bias_str,
                        COL_TECH_DIAGNOSIS: full_diag_text,
                        COL_BUY_LEVELS: suggested_bid_str,
                        COL_DAILY_LEVEL: daily_wave,
                        COL_PULLBACK_LEVEL: tech_retest,
                        COL_SNIPER_LEVEL: sniper_pos,
                        "MA20": ma20_str,
                        "MA60": ma60_str,
                        "MA120": ma120_str,
                        "MA250": ma250_str,
                        "當前 RS": round(curr_rs, 4),
                        "RS 百分位": f"{pct:.1f}%",
                        "RSI": rsi_val,
                        "Alpha 勝率": f"{bat_avg:.1f}%" if len(m_ret) >= 2 else "-",
                        "月度 Alpha": f"{avg_alpha:+.2f}%" if len(m_ret) >= 2 else "-",
                        "夏普值": f"{sharpe:.2f}" if len(m_ret) >= 2 else "-",
                        "EPS": fundamentals["eps"],
                        "PE": fundamentals["pe"],
                        "殖利率": f"{fundamentals['dividendYield']:.2%}"
                        if fundamentals["dividendYield"]
                        else "-",
                        "PEG": f"{fundamentals['pegRatio']:.2f}"
                        if fundamentals["pegRatio"]
                        else "-",
                        "量比": f"{vol_ratio:.2f}",
                        "_vol_ratio_raw": vol_ratio,
                        "_score": pct,
                        "tags": tags,
                        "ATV模型": entries.get("model", "-") if entries else "-",
                        "ATV趨勢": entries.get("regime", "-") if entries else "-",
                        "maxDrawdownPct": drawdown_result.maxDrawdownPercent
                        if drawdown_result
                        else None,
                        "currentDrawdownPct": drawdown_result.currentDrawdownPercent
                        if drawdown_result
                        else None,
                        "painRatio": drawdown_result.painRatio
                        if drawdown_result
                        else None,
                        COL_COMFORT_SCORE: drawdown_result.comfortScore
                        if drawdown_result
                        else None,
                        COL_HOLD_ABILITY_SCORE: hold_ability_score,
                        COL_MATURITY_SCORE: maturity_score,
                        COL_HISTORY_YEARS: round(history_years, 1),
                        "benchmarkMddPct": bench_mdd,
                        "benchmarkName": current_benchmark,
                    }
                )
            except Exception as exc:
                logging.warning(f"進階分析計算異常 [{ticker}]: {exc}")
                continue
    except Exception as exc:
        logging.error(f"取得進階分析資料失敗: {exc}")

    if results:
        df_rs = pd.DataFrame(results).sort_values("_score", ascending=False)
        return df_rs.drop(columns=["_score"])
    return pd.DataFrame()
