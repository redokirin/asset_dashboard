# -*- coding: utf-8 -*-
import yfinance as yf
import pandas as pd
import math
import numpy as np
from assets_config import ASSETS, RADAR_TICKERS, ALPHA_ANALYSIS

try:
    from scipy import stats

    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


def get_exchange_rate():
    """獲取匯率數據"""
    try:
        rate = yf.Ticker("JPYTWD=X").fast_info["last_price"]
        return rate if rate else 0.215
    except Exception:
        return 0.215


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
        except Exception:
            pass
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
            except Exception:
                signals[ticker] = default_signal
    except Exception:
        return {t: default_signal for t in tickers}
    return signals


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

    for cat_key, cat_name in [("funds", "基金"), ("etfs", "ETF")]:
        for asset in ASSETS[cat_key].values():
            if not asset.get("enabled", True):
                continue
            price, change_val = None, None
            if asset.get("get_value"):
                try:
                    info = yf.Ticker(asset["id"]).fast_info
                    price = getattr(info, "last_price", None)
                    if cat_key == "etfs" and price:
                        prev = getattr(info, "previous_close", 0)
                        change_val = price - prev if prev else 0.0
                except Exception:
                    pass
            res = process_asset(asset, cat_name, price, change_val)
            if res:
                results.append(res)

    df = pd.DataFrame(results)
    if df.empty:
        return df, pd.Series(dtype=float)

    total_val = df["市值"].sum()
    df["佔比"] = df["市值"] / total_val * 100
    market_share = (df.groupby("市場")["市值"].sum() / total_val * 100).round(1)
    return df, market_share


def get_rs_percentile_rank(tickers_list, benchmark="0050.TW"):
    """計算跨市場相對強度百分位"""
    if not HAS_SCIPY or not tickers_list:
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

        for ticker in tickers_list:
            try:
                t_df = yf.download(ticker, period="2y", progress=False)
                if t_df.empty:
                    continue
                t_col = "Adj Close" if "Adj Close" in t_df.columns else "Close"

                ccy = (
                    "JPY"
                    if ticker.endswith(".T")
                    else "USD"
                    if ".US" in ticker or ticker.isupper()
                    else "TWD"
                )
                rate = (
                    c_data["JPYTWD=X"]
                    if ccy == "JPY"
                    else c_data["USDTWD=X"]
                    if ccy == "USD"
                    else 1.0
                )

                comb = pd.DataFrame(
                    {"p": t_df[t_col], "r": rate, "b": c_data[benchmark]}
                ).dropna()
                rs_series = (comb["p"] * comb["r"]) / comb["b"]
                if len(rs_series) < 20:
                    continue

                curr = rs_series.iloc[-1]
                pct = stats.percentileofscore(rs_series, curr)
                results.append(
                    {
                        "代碼": ticker,
                        "當前 RS": round(curr, 4),
                        "RS 百分位": pct,
                        "狀態": "🔵 深水"
                        if pct <= 15
                        else ("🔥 過熱" if pct >= 85 else "⚪ 正常"),
                        "score": pct,
                    }
                )
            except Exception:
                continue
    except Exception:
        pass
    return pd.DataFrame(results).sort_values("score") if results else pd.DataFrame()


def calculate_single_alpha(target, benchmark, start):
    """計算 Alpha 穩定性指標"""
    try:
        df = yf.download([target, benchmark], start=start, progress=False)["Close"]
        if df.empty or df.shape[1] < 2:
            return None
        m_ret = df.resample("ME").last().pct_change().dropna()
        if m_ret.empty:
            return None

        m_ret["Alpha"] = m_ret[target] - m_ret[benchmark]
        avg_a = m_ret["Alpha"].mean() * 100
        std_r = m_ret[target].std()
        return {
            "total_months": len(m_ret),
            "batting_avg": (m_ret["Alpha"] > 0).mean() * 100,
            "avg_alpha": avg_a,
            "sharpe_ratio": (m_ret[target].mean() / std_r * (12**0.5))
            if std_r != 0
            else 0,
        }
    except Exception:
        return None


def run_alpha_analysis():
    """批量執行 Alpha 分析"""
    if not ALPHA_ANALYSIS:
        return []
    res = []
    for cfg in ALPHA_ANALYSIS:
        targets = cfg["target"] if isinstance(cfg["target"], list) else [cfg["target"]]
        names = (
            cfg["name"]
            if isinstance(cfg["name"], list)
            else [cfg["name"]] * len(targets)
        )
        for t, n in zip(targets, names):
            stat = calculate_single_alpha(t, cfg["benchmark"], cfg["start"])
            if stat:
                res.append(
                    {"name": n, "target": t, "benchmark": cfg["benchmark"], **stat}
                )
    return res


def export_for_ai(df):
    """導出 AI 分析文本"""
    print("--- AI 分析專用數據摘要 ---")
    cols = ["代碼", "股價", "漲跌", "平均成本", "單位數", "報酬率", "建議掛單"]
    print(df[cols].to_markdown(index=False))
    print("-" * 30)
