# -*- coding: utf-8 -*-
import math
import logging
import pandas as pd
import numpy as np
from fetchers import fetch_historical_data, fetch_common_data, get_ticker_fundamental_info

def calculate_buffered_entries(df, ma20, ma250, current_price, rs_p10_price):
    """計算具備緩衝的建議掛單價位"""
    if "High" not in df.columns or "Low" not in df.columns or len(df) < 14:
        return None

    high_low = df["High"] - df["Low"]
    atr = high_low.rolling(window=14).mean().iloc[-1]
    if pd.isna(atr):
        return None

    prev_close = df["Close"].iloc[-2] if len(df) >= 2 else current_price

    BUFFER_PERCENT = 0.005  # 0.5% 讓利緩衝
    MIN_GAP = 0.015  # 1.5% 強制價格階梯間隔

    raw_daily = prev_close - (1.0 * atr)
    raw_tech = ma20 * 0.97
    long_term_floor = ma250 * 0.98 if ma250 is not None else 999999.0
    raw_sniper = min(ma20 * 0.95, rs_p10_price, long_term_floor)

    ceiling = current_price * 0.995
    final_daily = min(raw_daily * (1 + BUFFER_PERCENT), ceiling)
    final_tech = min(raw_tech * (1 + BUFFER_PERCENT), final_daily * (1 - MIN_GAP))
    final_sniper = min(raw_sniper * (1 + BUFFER_PERCENT), final_tech * (1 - MIN_GAP))

    return {
        "日常波段": round(final_daily, 2),
        "技術回測": round(final_tech, 2),
        "狙擊位": round(final_sniper, 2),
    }

def generate_advanced_diagnosis(
    bias,
    sharpe,
    rs_percentile,
    ticker,
    price_change_pct=0,
    vol_ratio=1.0,
    rsi=0,
    price=None,
    ma20=None,
    ma250=None,
    eps=None,
    pe_ratio=None,
    dividend_yield=None,
    peg_ratio=None,
):
    """綜合量化診斷邏輯 (整合基本面、技術位、RS、RSI 與量價關係)"""
    tags = []

    if ma250 is None or math.isnan(ma250):
        lt_context, lt_desc = "LONG_UNKNOWN", "長線趨勢數據不足"
    elif price is not None and price > ma250:
        lt_context, lt_desc = "BULLISH", "長線多頭格局"
    else:
        lt_context, lt_desc = "BEARISH", "長線空頭排列"

    st_momentum = "MOM_UNKNOWN"
    if price is not None and ma20 is not None and not math.isnan(ma20):
        st_momentum = "STRONG" if price > ma20 else "WEAK"

    match (lt_context, st_momentum):
        case ("BULLISH", "STRONG"):
            tags.append("🔥 極致強勢")
            advice_base = "標的處於長短線多頭共振，向上動能極強。"
        case ("BULLISH", "WEAK"):
            tags.append("🟢 長線多頭")
            advice_base = "標的維持長線多頭格局，但短線出現技術性背離（跌破月線），正進行結構性回測。"
        case ("BEARISH", "STRONG"):
            tags.append("💧 弱勢反彈")
            advice_base = "長線空頭趨勢未變，當前僅屬超跌後的短線乖離修正。"
        case ("BEARISH", "WEAK"):
            tags.append("🔵 長線偏弱")
            advice_base = "長短線均受制於均線下行，技術面承壓，尚未見止跌訊號。"
        case _:
            tags.append("⚪ 中性整理")
            advice_base = "趨勢動能不明，建議於關鍵支撐位階觀察。"

    if rs_percentile > 85:
        tags.append("🔥 過熱區")
    elif rs_percentile <= 15:
        tags.append("🔵 深水區")
    else:
        tags.append("⚪ 正常區")

    if rsi > 70:
        tags.append("🟢 超買")
    elif rsi < 30:
        tags.append("🔴 超賣")

    if bias is not None and not math.isnan(bias):
        if bias <= -7:
            tags.append("🟠 極度價值區 (低於月線 -7%)")
        elif -7 < bias <= -4:
            tags.append("💧 跌深反彈區 (低於月線 -4%~-7%)")
        elif bias >= 7:
            tags.append("🔴 過熱區 (高於月線 +7%)")
        else:
            tags.append("🟢 趨勢區" if bias >= 0 else "🟡 價值區")

    fund_advice = ""
    if eps is not None and not math.isnan(eps) and eps > 0:
        tags.append("📊 盈利穩健")
        if pe_ratio is not None and not math.isnan(pe_ratio) and pe_ratio > 0:
            pe_desc = "低估值" if pe_ratio < 15 else "合理估值" if pe_ratio <= 30 else "高成長溢價"
            fund_advice += f"基本面 EPS 正向，反映出{pe_desc}。"

    if dividend_yield is not None and not math.isnan(dividend_yield) and dividend_yield > 0.035:
        if rs_percentile < 20 or lt_context == "BEARISH":
            tags.append("🛡️ 息收護城河")
            fund_advice += f"具備高股息殖利率 ({dividend_yield:.1%})，為深水區提供防禦支撐。"

    if peg_ratio is not None and not math.isnan(peg_ratio) and peg_ratio > 0:
        if peg_ratio < 1.0:
            tags.append("💎 估值極具吸引力 (PEG < 1)")
            fund_advice += " 成長估值具備極高吸引力 (PEG < 1)。"
        elif peg_ratio > 2.0:
            tags.append("⚠️ 成長溢價過高 (PEG > 2)")
            if lt_context == "BULLISH":
                fund_advice += " 需注意成長性已透支估值 (PEG > 2)。"

    if sharpe > 1.2:
        tags.append("💎 高效率資產")

    vp_advice = ""
    if price_change_pct > 1.5:
        if vol_ratio > 1.5:
            vp_advice = "今日價量齊揚，主動性買盤積極介入。"
        elif vol_ratio < 0.75:
            vp_advice = "⚠️ 注意價漲量縮現象，反彈動能缺乏支撐，慎防追高風險。"
    elif price_change_pct < -1.5:
        if vol_ratio > 2.0:
            vp_advice = "😱 偵測到異常爆量 (2.0x+)，技術支撐可能失效，建議暫緩接單並觀察防守位。"
        elif vol_ratio > 1.5:
            vp_advice = "😱 帶量下殺，反映恐慌性賣壓持續湧現，建議優先觀察狙擊位。"
        elif vol_ratio < 0.8:
            vp_advice = "量縮下跌，賣壓出現竭盡跡象，有利於短線止跌整理。"

    full_advice = f"{lt_desc}。 {advice_base}\n{fund_advice}\n{vp_advice}".strip()
    return full_advice, tags

def run_advanced_analysis(df_res, benchmark="0050.TW", has_scipy=True):
    """合併執行 RS (相對強度) 與 Alpha (穩定性) 進階分析"""
    if len(df_res) == 1:
        active_tickers = df_res["代碼"].tolist()
    else:
        active_tickers = df_res[df_res["類型"] == "ETF"]["代碼"].tolist()

    if not active_tickers or not has_scipy:
        return pd.DataFrame()

    try:
        from scipy import stats
    except ImportError:
        return pd.DataFrame()

    results = []
    try:
        common_raw = fetch_common_data((benchmark, "JPYTWD=X", "USDTWD=X"), period="2y")

        def get_clean_col(df, ticker_name, col_name):
            try:
                if isinstance(df.columns, pd.MultiIndex):
                    if ticker_name in df.columns.get_level_values(0):
                        s = df.xs(ticker_name, axis=1, level=0)[col_name]
                    else:
                        s = df[col_name]
                else:
                    s = df[col_name]
                if isinstance(s.index, pd.MultiIndex):
                    s.index = s.index.get_level_values(0)
                s.index = pd.to_datetime(s.index)
                if hasattr(s.index, "tz") and s.index.tz is not None:
                    s.index = s.index.tz_localize(None)
                if isinstance(s, pd.DataFrame):
                    s = s.iloc[:, 0]
                return s
            except:
                return pd.Series()

        b_series_final = get_clean_col(common_raw, benchmark, "Close")
        if b_series_final.empty:
            return pd.DataFrame()

        t_data_all_raw = fetch_historical_data(tuple(active_tickers), period="2y", group_by="ticker")

        for ticker in active_tickers:
            try:
                if isinstance(t_data_all_raw.columns, pd.MultiIndex):
                    if ticker in t_data_all_raw.columns.get_level_values(0):
                        t_df = t_data_all_raw.xs(ticker, axis=1, level=0).copy()
                    else:
                        t_df = t_data_all_raw.copy()
                else:
                    t_df = t_data_all_raw.copy()

                if t_df is None or t_df.empty:
                    continue

                if isinstance(t_df.columns, pd.MultiIndex):
                    t_df.columns = t_df.columns.get_level_values(-1)
                t_df.index = pd.to_datetime(t_df.index)
                if hasattr(t_df.index, "tz") and t_df.index.tz is not None:
                    t_df.index = t_df.index.tz_localize(None)

                if "Close" not in t_df.columns:
                    continue

                t_df_clean = t_df[t_df["Close"].notnull()].copy()
                if len(t_df_clean) == 0:
                    continue

                ma20_str, ma60_str, ma120_str = "-", "數據不足", "數據不足"
                bias_str, bias_numeric = "-", 0.0
                ma20_val, ma250_val, ma250_str = None, None, "-"

                last_close_val = t_df_clean["Close"].iloc[-1]
                price_val = float(last_close_val.iloc[0]) if isinstance(last_close_val, pd.Series) else float(last_close_val)

                if len(t_df_clean) >= 2:
                    prev_close_val = t_df_clean["Close"].iloc[-2]
                    prev_close = float(prev_close_val.iloc[0]) if isinstance(prev_close_val, pd.Series) else float(prev_close_val)
                else:
                    prev_close = price_val

                day_change_pct = ((price_val - prev_close) / prev_close) * 100

                if len(t_df_clean) >= 20:
                    ma20_series = t_df_clean["Close"].rolling(20).mean()
                    ma20_last = ma20_series.iloc[-1]
                    ma20_val = float(ma20_last.iloc[0]) if isinstance(ma20_last, pd.Series) else float(ma20_last)
                    if pd.notnull(ma20_val) and ma20_val > 0:
                        ma20_str = f"{ma20_val:.2f}"
                        bias_numeric = ((price_val - ma20_val) / ma20_val) * 100
                        bias_str = f"{bias_numeric:.2f}%"

                if len(t_df_clean) >= 60:
                    ma60_last = t_df_clean["Close"].rolling(60).mean().iloc[-1]
                    if pd.notnull(ma60_last):
                        ma60_str = f"{float(ma60_last):.2f}"
                
                if len(t_df_clean) >= 120:
                    ma120_last = t_df_clean["Close"].rolling(120).mean().iloc[-1]
                    if pd.notnull(ma120_last):
                        ma120_str = f"{float(ma120_last):.2f}"

                if len(t_df_clean) >= 250:
                    ma250_last = t_df_clean["Close"].rolling(250).mean().iloc[-1]
                    ma250_val = float(ma250_last) if pd.notnull(ma250_last) else None
                    if ma250_val:
                        ma250_str = f"{ma250_val:.2f}"

                p_series = t_df_clean["Close"].copy()
                if isinstance(p_series, pd.DataFrame): p_series = p_series.iloc[:, 0]

                ccy = "JPY" if ticker.endswith(".T") else "USD" if ".US" in ticker or ticker.isupper() else "TWD"
                if ccy == "JPY": r_series = get_clean_col(common_raw, "JPYTWD=X", "Close")
                elif ccy == "USD": r_series = get_clean_col(common_raw, "USDTWD=X", "Close")
                else: r_series = 1.0

                comb_dict = {"p": p_series, "b": b_series_final}
                if isinstance(r_series, (pd.Series, pd.DataFrame)): comb_dict["r"] = r_series
                comb = pd.DataFrame(comb_dict).ffill()
                if "r" not in comb.columns: comb["r"] = 1.0
                comb = comb[comb["p"].notnull() & comb["b"].notnull()]

                if comb.empty: continue

                rs_series = (comb["p"] * comb["r"]) / comb["b"]
                if len(rs_series) < 20: continue
                curr_rs = float(rs_series.iloc[-1])
                pct = stats.percentileofscore(rs_series.values.flatten(), curr_rs)

                rsi_val = 0.0
                if len(t_df_clean) >= 15:
                    delta = t_df_clean["Close"].diff()
                    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                    with np.errstate(divide="ignore", invalid="ignore"):
                        rs_val = gain / loss
                        rsi_series = 100 - (100 / (1 + rs_val))
                    rsi_val = float(rsi_series.iloc[-1]) if not pd.isna(rsi_series.iloc[-1]) else 0.0

                rs_p10 = float(np.percentile(rs_series.values.flatten(), 10))
                rs_p10_price = (rs_p10 * comb["b"].iloc[-1]) / comb["r"].iloc[-1]

                suggested_bid_str = "-"
                daily_wave, tech_retest, sniper_pos = "-", "-", "-"
                if ma20_val is not None:
                    entries = calculate_buffered_entries(t_df_clean, ma20_val, ma250_val, price_val, rs_p10_price)
                    if entries:
                        suggested_bid_str = f"{entries['日常波段']:.2f} | {entries['技術回測']:.2f} | {entries['狙擊位']:.2f}"
                        daily_wave, tech_retest, sniper_pos = f"{entries['日常波段']:.2f}", f"{entries['技術回測']:.2f}", f"{entries['狙擊位']:.2f}"

                m_price = comb.resample("ME").last()
                m_ret = pd.DataFrame({"target_ret": (m_price["p"] * m_price["r"]).pct_change(), "bench_ret": m_price["b"].pct_change()}).dropna()
                bat_avg, avg_alpha, sharpe = 0.0, 0.0, 0.0
                if not m_ret.empty and len(m_ret) >= 2:
                    m_ret["Alpha"] = m_ret["target_ret"] - m_ret["bench_ret"]
                    avg_alpha, bat_avg = m_ret["Alpha"].mean() * 100, (m_ret["Alpha"] > 0).mean() * 100
                    std_r = m_ret["target_ret"].std()
                    sharpe = (m_ret["target_ret"].mean() / std_r * (12**0.5)) if std_r != 0 else 0.0

                fundamentals = get_ticker_fundamental_info(ticker)
                vol_ratio = fundamentals["volume"] / fundamentals["avg_volume"] if fundamentals["avg_volume"] > 0 else 1.0

                full_diag_text, tags = generate_advanced_diagnosis(
                    bias_numeric, sharpe, pct, ticker, price_change_pct=day_change_pct, vol_ratio=vol_ratio, rsi=rsi_val,
                    price=price_val, ma20=ma20_val, ma250=ma250_val, eps=fundamentals.get("eps"), pe_ratio=fundamentals.get("pe"),
                    dividend_yield=fundamentals.get("dividendYield"), peg_ratio=fundamentals.get("pegRatio")
                )

                results.append({
                    "代碼": ticker, "名稱": fundamentals.get("name", ticker), "股價": f"{price_val:.2f}",
                    "乖離率 (Bias)": bias_str, "技術診斷": full_diag_text, "建議掛單": suggested_bid_str,
                    "日常波段": daily_wave, "技術回測": tech_retest, "狙擊位": sniper_pos,
                    "MA20": ma20_str, "MA60": ma60_str, "MA120": ma120_str, "MA250": ma250_str,
                    "當前 RS": round(curr_rs, 4), "RS 百分位": f"{pct:.1f}%", "RSI": rsi_val,
                    "Alpha 勝率": f"{bat_avg:.1f}%" if len(m_ret) >= 2 else "-",
                    "月度 Alpha": f"{avg_alpha:+.2f}%" if len(m_ret) >= 2 else "-",
                    "夏普值": f"{sharpe:.2f}" if len(m_ret) >= 2 else "-",
                    "EPS": fundamentals["eps"], "PE": fundamentals["pe"], "量比": f"{vol_ratio:.2f}",
                    "_vol_ratio_raw": vol_ratio, "_score": pct, "tags": tags,
                })
            except Exception as e:
                logging.warning(f"進階分析計算異常 [{ticker}]: {e}")
                continue
    except Exception as e:
        logging.error(f"取得進階分析資料失敗: {e}")

    if results:
        df_rs = pd.DataFrame(results).sort_values("_score", ascending=False)
        return df_rs.drop(columns=["_score"])
    return pd.DataFrame()
