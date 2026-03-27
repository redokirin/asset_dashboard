# -*- coding: utf-8 -*-
import yfinance as yf
import pandas as pd
import math
import numpy as np
import logging
from assets_config import ASSETS, RADAR_TICKERS

logging.basicConfig(
    level=logging.WARNING, format="%(asctime)s - [%(levelname)s] - %(message)s"
)

try:
    from scipy import stats

    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


def get_market_radar_data():
    """抓取市場雷達數據"""
    data = []
    for ticker, name in RADAR_TICKERS.items():
        try:
            t = yf.Ticker(ticker)
            last_price = t.fast_info["last_price"]
            hist = t.history(period="2d")
            change_pct = (
                ((last_price - hist["Close"].iloc[0]) / hist["Close"].iloc[0] * 100)
                if not hist.empty
                else 0.0
            )
            data.append(
                {"代碼": ticker, "名稱": name, "數值": last_price, "漲跌幅": change_pct}
            )
        except Exception as e:
            logging.warning(f"無法獲取雷達數據 [{ticker}]: {e}")
    return data


def calculate_tick_price(target_price, market_type):
    """計算符合市場規則的跳動價位 (Tick Size)"""
    if market_type == "TW_STOCK":
        ticks = [(10, 0.01), (50, 0.05), (100, 0.1), (500, 0.5), (1000, 1.0)]
        tick = 5.0
        for limit, t in ticks:
            if target_price < limit:
                tick = t
                break
        return math.floor(round(target_price / tick, 8)) * tick
    elif market_type in ["TW_ETF", "TW_ETF_HIGH"]:
        tick = 0.01 if target_price < 50 else 0.05
        return math.floor(round(target_price / tick, 8)) * tick
    return round(target_price, 2)


def get_batch_buy_signals(tickers: list):
    """計算技術面買賣訊號"""
    if not tickers:
        return {}
    strong, buy, warning, healthy, default_signal = "🟠", "🟡", "🔴", "🟢", "  "
    signals = {}
    try:
        data = yf.download(tickers, period="1y", progress=False, group_by="ticker")
        for ticker in tickers:
            try:
                df = data[ticker] if isinstance(data.columns, pd.MultiIndex) else data
                if df is None or df.empty or df["Close"].isnull().all():
                    signals[ticker] = default_signal
                    continue
                df = df.dropna(subset=["Close"]).copy()
                ma20, ma60 = (
                    df["Close"].rolling(20).mean().iloc[-1],
                    df["Close"].rolling(60).mean().iloc[-1],
                )
                price = df["Close"].iloc[-1]
                bias = (price - ma20) / ma20 * 100
                if price <= ma60:
                    signals[ticker] = strong
                elif price <= ma20:
                    signals[ticker] = buy
                elif bias > 5:
                    signals[ticker] = warning
                else:
                    signals[ticker] = healthy
            except Exception as e:
                logging.warning(f"計算買賣訊號單項失敗 [{ticker}]: {e}")
                signals[ticker] = default_signal
    except Exception as e:
        logging.error(f"批量計算買賣訊號整體失敗: {e}")
        return {t: default_signal for t in tickers}
    return signals


def exchange_rate(radar):
    jpy_rate = next(
        (item["數值"] for item in radar if item["代碼"] == "JPYTWD=X"), None
    )
    usd_rate = next(
        (item["數值"] for item in radar if item["代碼"] == "USDTWD=X"), None
    )

    if jpy_rate is None:
        logging.warning("無法取得 JPY 匯率，啟用預設值 0.215！")
        jpy_rate = 0.215

    if usd_rate is None:
        logging.warning("無法取得 USD 匯率，啟用預設值 32.0！")
        usd_rate = 32.0

    return {
        "JPY": jpy_rate,
        "USD": usd_rate,
        "TWD": 1.0,
    }


def calculate_assets_data(exchange_rates):
    """資產價值核心計算"""
    results = []

    def process_asset(asset, category, price=None, change_val=None):
        rate = exchange_rates.get(asset["ccy"], 1.0)
        units = float(asset.get("units", asset.get("shares", 0)))
        if units == 0 and "investment" in asset:
            units = sum(i.get("units", i.get("shares", 0)) for i in asset["investment"])

        cost_origin = float(asset.get("cost", 0))
        if cost_origin == 0 and "investment" in asset:
            cost_origin = sum(i.get("cost", 0) for i in asset["investment"])

        avg_cost = cost_origin / units if units > 0 else 0
        current_price = price if price is not None else asset.get("nav", 0)

        val_twd, cost_twd = (current_price * units * rate), (cost_origin * rate)
        pl_val = val_twd - cost_twd

        suggested_bid = 0.0
        if price is not None and asset.get("market_type"):
            target = min(
                price * asset.get("discount", 0.985),
                avg_cost * 0.998 if avg_cost > 0 else 999999,
            )
            suggested_bid = calculate_tick_price(target, asset["market_type"])

        return {
            "市場": asset["market"],
            "類型": category,
            "名稱": asset["name"],
            "代碼": asset["id"],
            "幣別": asset["ccy"],
            "單位數": units,
            "平均成本": avg_cost,
            "漲跌": change_val,
            "股價": current_price,
            "建議掛單": suggested_bid,
            "成本": round(cost_twd),
            "市值": round(val_twd),
            "損益": round(pl_val),
            "報酬率": (pl_val / cost_twd * 100) if cost_twd != 0 else 0,
        }

    # 批次下載價格與歷史資料
    tickers_to_fetch = []
    for cat_key in ["funds", "etfs"]:
        for asset in ASSETS[cat_key].values():
            if asset.get("enabled", True) and asset.get("get_value"):
                tickers_to_fetch.append(asset["id"])

    batch_prices = {}
    batch_changes = {}
    if tickers_to_fetch:
        try:
            # 獲取近兩天資料以計算昨日收盤
            hist_data = yf.download(
                tickers_to_fetch, period="2d", progress=False, group_by="ticker"
            )
            for ticker in tickers_to_fetch:
                try:
                    df = (
                        hist_data[ticker]
                        if isinstance(hist_data.columns, pd.MultiIndex)
                        else hist_data
                    )
                    if df is not None and not df.empty and "Close" in df.columns:
                        df_clean = df.dropna(subset=["Close"])
                        if len(df_clean) >= 1:
                            current_price = float(df_clean["Close"].iloc[-1])
                            change_val = 0.0
                            if len(df_clean) >= 2:
                                prev_close = float(df_clean["Close"].iloc[-2])
                                change_val = current_price - prev_close

                            batch_prices[ticker] = current_price
                            batch_changes[ticker] = change_val
                except Exception as e:
                    logging.warning(f"解析 {ticker} 歷史資料失敗: {e}")
        except Exception as e:
            logging.error(f"批次下載價格資料失敗: {e}")

    for cat_key, cat_name in [("funds", "基金"), ("etfs", "ETF")]:
        for asset in ASSETS[cat_key].values():
            if not asset.get("enabled", True):
                continue

            price, change_val = None, None
            if asset.get("get_value"):
                price = batch_prices.get(asset["id"])
                if cat_key == "etfs":
                    change_val = batch_changes.get(asset["id"])

            res = process_asset(asset, cat_name, price, change_val)
            if res:
                results.append(res)

    df = pd.DataFrame(results)
    if df.empty:
        return df, pd.Series(dtype=float)

    total_val = df["市值"].sum()
    df["佔比"] = df["市值"] / total_val * 100
    market_sum = df.groupby("市場")["市值"].sum()
    market_share = pd.DataFrame(
        {"市值": market_sum, "佔比": (market_sum / total_val * 100).round(1)}
    ).to_dict(orient="index")
    return df, market_share


# RS & 百分位：解決了「現在相對於台股，誰便宜、誰貴？」（相對位階）
# Alpha（勝率/月度）：解決了「誰是真的有能力賺贏大盤，而不只是跟風？」（超額能力）
# 夏普值 (Sharpe Ratio)：解決了「誰的報酬是拿高風險換來的？誰賺得最穩？」（風險效率）
def run_advanced_analysis(df_res, benchmark="0050.TW"):
    """合併執行 RS (相對強度) 與 Alpha (穩定性) 進階分析"""
    active_tickers = df_res[df_res["類型"] == "ETF"]["代碼"].tolist()
    if not active_tickers or not HAS_SCIPY:
        if not active_tickers:
            print("警告：沒有適合進行進階分析的 ETF Ticker")
        return pd.DataFrame()

    results = []
    try:
        common = yf.download(
            [benchmark, "JPYTWD=X", "USDTWD=X"], period="2y", progress=False
        )
        if common.empty:
            return pd.DataFrame()
        price_col = (
            "Adj Close"
            if "Adj Close" in common.columns.get_level_values(0)
            else "Close"
        )
        c_data = common[price_col]
        b_series = c_data[benchmark].squeeze()
        jpy_rate = (
            c_data["JPYTWD=X"].squeeze() if "JPYTWD=X" in c_data.columns else 0.215
        )
        usd_rate = (
            c_data["USDTWD=X"].squeeze() if "USDTWD=X" in c_data.columns else 32.0
        )

        t_data_all = yf.download(
            active_tickers, period="2y", progress=False, group_by="ticker"
        )

        for ticker in active_tickers:
            try:
                if len(active_tickers) == 1:
                    t_df = t_data_all
                else:
                    t_df = (
                        t_data_all[ticker]
                        if isinstance(t_data_all.columns, pd.MultiIndex)
                        else t_data_all
                    )

                if t_df is None or t_df.empty or "Close" not in t_df.columns:
                    continue

                t_col = "Adj Close" if "Adj Close" in t_df.columns else "Close"

                # 自動判斷幣別
                ccy = (
                    "JPY"
                    if ticker.endswith(".T")
                    else "USD"
                    if ".US" in ticker or ticker.isupper()
                    else "TWD"
                )
                rate = jpy_rate if ccy == "JPY" else usd_rate if ccy == "USD" else 1.0

                p_series = t_df[t_col].squeeze()
                r_series = rate.squeeze() if hasattr(rate, "squeeze") else rate

                comb = pd.DataFrame(
                    {"p": p_series, "r": r_series, "b": b_series}
                ).dropna()

                if comb.empty:
                    continue

                # --- 1. RS 計算 ---
                rs_series = (comb["p"] * comb["r"]) / comb["b"]
                if len(rs_series) < 20:
                    continue

                curr_rs = float(rs_series.iloc[-1])
                pct = stats.percentileofscore(rs_series.values.flatten(), curr_rs)

                # --- 2. Alpha 穩定性與夏普計算 ---
                # 在換算為 TWD 基準下重新取樣至月底
                m_price = comb.resample("ME").last()
                m_ret = pd.DataFrame(
                    {
                        "target_ret": (m_price["p"] * m_price["r"]).pct_change(),
                        "bench_ret": m_price["b"].pct_change(),
                    }
                ).dropna()

                if m_ret.empty or len(m_ret) < 2:
                    bat_avg, avg_alpha, sharpe = 0.0, 0.0, 0.0
                else:
                    m_ret["Alpha"] = m_ret["target_ret"] - m_ret["bench_ret"]
                    avg_alpha = m_ret["Alpha"].mean() * 100
                    bat_avg = (m_ret["Alpha"] > 0).mean() * 100
                    std_r = m_ret["target_ret"].std()
                    sharpe = (
                        (m_ret["target_ret"].mean() / std_r * (12**0.5))
                        if std_r != 0
                        else 0.0
                    )

                # --- 結合結果 ---
                asset_match = df_res[df_res["代碼"] == ticker]
                asset_name = (
                    asset_match["名稱"].iloc[0] if not asset_match.empty else ticker
                )

                results.append(
                    {
                        "代碼": ticker,
                        "名稱": asset_name,
                        "當前 RS": round(curr_rs, 4),
                        "RS 百分位": f"{pct:.1f}%",
                        "狀態": "🔵 深水"
                        if pct <= 15
                        else ("🔥 過熱" if pct >= 85 else "⚪ 正常"),
                        "Alpha 勝率": f"{bat_avg:.1f}%" if len(m_ret) >= 2 else "-",
                        "月度 Alpha": f"{avg_alpha:+.2f}%" if len(m_ret) >= 2 else "-",
                        "夏普值": f"{sharpe:.2f}" if len(m_ret) >= 2 else "-",
                        "_score": pct,
                    }
                )
            except Exception as e:
                logging.warning(f"進階分析計算異常 [{ticker}]: {e}")
                continue
    except Exception as e:
        logging.error(f"取得進階分析資料失敗: {e}")

    if results:
        df_rs = pd.DataFrame(results).sort_values("_score", ascending=False)
        return df_rs.drop(columns=["_score"])

    return pd.DataFrame()


def export_for_ai(df):
    """導出 AI 分析文本"""
    print("--- AI 分析專用數據摘要 ---")
    cols = ["代碼", "股價", "漲跌", "平均成本", "單位數", "報酬率", "建議掛單"]
    print(df[cols].to_markdown(index=False))
    print("-" * 30)
