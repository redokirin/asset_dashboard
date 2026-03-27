# -*- coding: utf-8 -*-
import yfinance as yf
import pandas as pd
import sys
import math
import numpy as np

try:
    from scipy import stats

    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

from assets_config import ASSETS, RADAR_TICKERS, ALPHA_ANALYSIS
from dashboard_ui import (
    CURRENT_ENV,
    HAS_RICH,
    show_streamlit,
    show_console_rich,
    show_jupyter,
)


def get_exchange_rate():
    try:
        rate = yf.Ticker("JPYTWD=X").fast_info["last_price"]
        return rate if rate else 0.215
    except Exception:
        return 0.215


def get_market_radar_data():
    """抓取市場雷達數據，回傳 List of Dict"""
    data = []
    for ticker, name in RADAR_TICKERS.items():
        try:
            t = yf.Ticker(ticker)
            last_price = t.fast_info["last_price"]

            # 計算漲跌幅
            hist = t.history(period="2d")
            if not hist.empty and len(hist) >= 1:
                prev_close = hist["Close"].iloc[0]
                change_pct = ((last_price - prev_close) / prev_close) * 100
            else:
                change_pct = 0.0

            data.append(
                {"代碼": ticker, "名稱": name, "數值": last_price, "漲跌幅": change_pct}
            )

        except Exception:
            pass
    return data


def export_for_ai(df):
    # print(df)
    # sys.exit()
    """
    產生一個專門給 AI 分析用的純文字摘要
    """
    print("--- AI 分析專用數據摘要 ---")
    # 只挑選核心欄位，轉成 Markdown
    summary_cols = ["代碼", "股價", "漲跌", "平均成本", "單位數", "報酬率", "建議掛單"]
    print(df[summary_cols].to_markdown(index=False))
    print("-" * 30)


def calculate_tick_price(target_price, market_type):
    """
    根據目標價格與市場類型，修正為符合交易規則的 Tick
    """
    if market_type == "TW_STOCK":
        if target_price < 10:
            tick = 0.01
        elif target_price < 50:
            tick = 0.05
        elif target_price < 100:
            tick = 0.1
        elif target_price < 500:
            tick = 0.5
        elif target_price < 1000:
            tick = 1.0
        else:
            tick = 5.0
        return math.floor(round(target_price / tick, 8)) * tick

    elif market_type in ["TW_ETF", "TW_ETF_HIGH"]:
        # 台股 ETF 規則：50元以下 0.01，50元以上 0.05
        tick = 0.01 if target_price < 50 else 0.05
        return math.floor(round(target_price / tick, 8)) * tick

    # 其他市場（如日股）暫不處理特殊 Tick，直接回傳
    return round(target_price, 2)


def calculate_assets_data(exchange_rates):
    """計算所有資產數據"""
    results = []
    # PROFIT_GOAL = 100

    def process_asset(asset, category, price=None, change_val=None):
        try:
            ccy = asset["ccy"]
            rate = exchange_rates.get(ccy, 1)  # 從字典取匯率，預設為 1 (TWD)

            if "units" in asset:
                total_units = float(asset["units"])
            elif "shares" in asset:
                total_units = float(asset["shares"])
            else:
                inv = asset.get("investment", [])
                total_units = sum(i.get("units", i.get("shares", 0)) for i in inv)

            if "cost" in asset:
                total_cost_origin = float(asset["cost"])
            else:
                inv = asset.get("investment", [])
                total_cost_origin = sum(i.get("cost", 0) for i in inv)

            avg_cost = (total_cost_origin / total_units) if total_units > 0 else 0

            if price is None:  # 基金
                current_price = asset.get("nav", 0)
                val_origin = asset.get("value", current_price * total_units)
            else:  # ETF
                current_price = price
                val_origin = current_price * total_units

            val_twd = val_origin * rate
            cost_twd = total_cost_origin * rate
            pl_val = val_twd - cost_twd
            pl_pct = (pl_val / cost_twd * 100) if cost_twd != 0 else 0

            # 計算建議掛單
            suggested_bid = 0.0
            m_type = asset.get("market_type")
            if price is not None and m_type:
                discount = asset.get("discount", 0.985)
                market_target = price * discount

                # 成本錨點 (Cost Anchor) 邏輯：確保掛單價能降低平均成本
                if avg_cost > 0:
                    cost_target = avg_cost * 0.998  # 預留 0.2% 降本空間
                    final_target = min(market_target, cost_target)
                else:
                    final_target = market_target

                suggested_bid = calculate_tick_price(final_target, m_type)

            # 獲利標記
            display_name = asset["name"]
            # if pl_pct >= PROFIT_GOAL:
            #     display_name = "🏆 " + display_name
            # elif pl_pct >= 20:
            #     display_name = "🚩 " + display_name

            return {
                "市場": asset["market"],
                "類型": category,
                "名稱": display_name,
                "代碼": asset["id"],
                "幣別": asset["ccy"],
                "單位數": total_units,
                "平均成本": avg_cost,
                "漲跌": change_val,
                "股價": current_price,
                "建議掛單": suggested_bid,
                "成本": round(cost_twd),
                "市值": round(val_twd),
                "損益": round(pl_val),
                "報酬率": pl_pct,
            }
        except Exception:
            return None

    # 處理資產迴圈
    all_assets = [(ASSETS["funds"], "基金"), (ASSETS["etfs"], "ETF")]
    for asset_dict, category in all_assets:
        for asset in asset_dict.values():
            # 若設定 enabled: False 則跳過不計算
            if not asset.get("enabled", True):
                continue

            price = None
            change_val = None
            if asset.get("get_value", False):
                try:
                    t = yf.Ticker(asset["id"])
                    info = t.fast_info
                    # 修正：使用屬性訪問 (Attribute Access) 而非字典索引
                    price = getattr(info, "last_price", None)
                    # 僅針對 ETF 計算單日漲跌數值
                    if category == "ETF" and price is not None:
                        change_val = 0.0  # ETF 預設為 0.0 而非 None
                        prev_close = getattr(info, "previous_close", None)
                        if prev_close is not None and prev_close != 0:
                            change_val = price - prev_close
                except Exception:
                    pass
            res = process_asset(asset, category, price, change_val)
            if res:
                results.append(res)

    df = pd.DataFrame(results)  # This df contains individual asset data
    if not df.empty:
        # df.sort_values(by=["幣別", "報酬率"], ascending=[False, False], inplace=True)
        total_portfolio_value = df["市值"].sum()
        df["佔比"] = df["市值"] / total_portfolio_value * 100

        # Calculate market share
        market_distribution_twd = df.groupby("市場")["市值"].sum()
        market_share_series = (
            market_distribution_twd / total_portfolio_value * 100
        ).round(1)
    else:
        market_share_series = pd.Series(dtype=float)  # Handle empty df case
    return df, market_share_series


def get_rs_percentile_rank(tickers_list, benchmark="0050.TW"):
    """
    計算所有標的相對於 benchmark 的 RS 百分位數排名 (跨市場比較)
    """
    if not HAS_SCIPY:
        print(
            "警告：缺少 'scipy' 套件，無法進行 RS 分析。請執行 'pip install scipy' 或 'poetry add scipy'"
        )
        return pd.DataFrame()

    results = []
    try:
        # 預先下載 Benchmark 與匯率數據
        common_tickers = [benchmark, "JPYTWD=X", "USDTWD=X"]
        common_data = yf.download(common_tickers, period="2y", progress=False)["Close"]

        for ticker in tickers_list:
            try:
                # 抓取 2 年歷史數據計算百分位 (RS 需要較長的觀察期)
                data = yf.download(ticker, period="2y", progress=False)["Close"]
                if data.empty:
                    continue

                # 判斷幣別 (使用 ticker 後綴判定)
                ccy = (
                    "JPY"
                    if ticker.endswith(".T")
                    else "TWD"
                    if ticker.endswith(".TW")
                    else "USD"
                )

                rate = (
                    common_data["JPYTWD=X"]
                    if ccy == "JPY"
                    else common_data["USDTWD=X"]
                    if ccy == "USD"
                    else 1.0
                )

                # 計算 RS 系列 (標的 TWD 價格 / Benchmark 價格)
                # 確保 index 對齊
                combined = pd.DataFrame(
                    {"price": data, "rate": rate, "bench": common_data[benchmark]}
                ).dropna()
                rs_series = (combined["price"] * combined["rate"]) / combined["bench"]

                if len(rs_series) < 20:
                    continue

                current_rs = rs_series.iloc[-1]
                percentile = stats.percentileofscore(rs_series, current_rs)

                results.append(
                    {
                        "代碼": ticker,
                        "當前 RS": round(current_rs, 4),
                        "RS 百分位": percentile,
                        "狀態": "🔵 深水"
                        if percentile <= 15
                        else ("🔥 過熱" if percentile >= 85 else "⚪ 正常"),
                        "score": percentile,  # 用於排序
                    }
                )
            except Exception:
                continue
    except Exception as e:
        print(f"RS 分析發生錯誤: {e}")

    if not results:
        return pd.DataFrame()

    return pd.DataFrame(results).sort_values("score")


def calculate_single_alpha(target, benchmark, start):
    """為單一目標與基準計算 Alpha 相關指標"""
    try:
        # progress=False 避免在下載時印出訊息
        df = yf.download([target, benchmark], start=start, progress=False)["Close"]
        if (
            df.empty
            or df.shape[1] < 2
            or df[target].isnull().all()
            or df[benchmark].isnull().all()
        ):
            return None

        monthly_returns = df.resample("ME").last().pct_change().dropna()
        if monthly_returns.empty:
            return None

        monthly_returns["Monthly_Alpha"] = (
            monthly_returns[target] - monthly_returns[benchmark]
        )

        win_months = monthly_returns["Monthly_Alpha"] > 0
        batting_avg = win_months.mean() * 100
        avg_alpha = monthly_returns["Monthly_Alpha"].mean() * 100

        # 計算年化夏普比率 (假設無風險利率為 0)
        mean_ret = monthly_returns[target].mean()
        std_ret = monthly_returns[target].std()
        sharpe_ratio = (mean_ret / std_ret) * (12**0.5) if std_ret != 0 else 0

        return {
            "total_months": len(monthly_returns),
            "batting_avg": batting_avg,
            "avg_alpha": avg_alpha,
            "sharpe_ratio": sharpe_ratio,
            "recent_alpha": monthly_returns["Monthly_Alpha"].tail(5),
        }
    except Exception:
        return None


def run_alpha_analysis():
    """根據 assets_config 中的 ALPHA_ANALYSIS 配置執行分析"""
    analysis_results = []
    # 確保 ALPHA_ANALYSIS 存在且不為空
    if "ALPHA_ANALYSIS" not in globals() or not ALPHA_ANALYSIS:
        return analysis_results

    for analysis in ALPHA_ANALYSIS:
        targets = analysis["target"]
        names = analysis["name"]
        benchmark = analysis["benchmark"]
        start = analysis["start"]

        # 支援多檔同時設定 (List) 或 單檔 (String)
        if not isinstance(targets, list):
            targets_list = [targets]
            names_list = [names]
        else:
            targets_list = targets
            names_list = names if isinstance(names, list) else [names] * len(targets)

        for target, name in zip(targets_list, names_list):
            result = calculate_single_alpha(target, benchmark, start)
            if result:
                analysis_results.append(
                    {"name": name, "target": target, "benchmark": benchmark, **result}
                )
    return analysis_results


# --- 4. 主程式 ---

if __name__ == "__main__":
    alpha_results = run_alpha_analysis() if "--alpha" in sys.argv else None
    radar = get_market_radar_data()
    exchange_rates = {
        "JPY": next(
            (item["數值"] for item in radar if item["代碼"] == "JPYTWD=X"), 0.215
        ),
        "USD": next(
            (item["數值"] for item in radar if item["代碼"] == "USDTWD=X"), 32.0
        ),
        "TWD": 1,
    }
    df_res, market_share_data = calculate_assets_data(exchange_rates)

    # 跨市場 RS 分析 (選用)
    rs_results = None
    if "--rs" in sys.argv:
        # 取得所有啟用的標的 ID，僅包含 .T, .TW 或明顯的 Ticker 格式
        active_tickers = [
            t
            for t in df_res["代碼"].tolist()
            if (".T" in t or ".TW" in t or t.isupper()) and not t.isdigit()
        ]
        if active_tickers:
            rs_results = get_rs_percentile_rank(active_tickers)
        else:
            print("警告：沒有適合進行 RS 分析的 Ticker (例如 .TW 或 .T)")

    if "--ai" in sys.argv:
        export_for_ai(df_res)
    else:
        if CURRENT_ENV == "streamlit":
            show_streamlit(df_res, radar, market_share_data, alpha_results, rs_results)
        elif CURRENT_ENV == "jupyter":
            show_jupyter(
                df_res,
                radar,
                exchange_rates,
                market_share_data,
                alpha_results,
                rs_results,
            )
        elif HAS_RICH:
            show_console_rich(
                df_res, radar, market_share_data, alpha_results, rs_results
            )
        else:
            print(df_res.to_string())
