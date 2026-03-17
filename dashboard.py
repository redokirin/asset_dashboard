# -*- coding: utf-8 -*-
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import platform
import sys
import math

from assets_config import ASSETS, RADAR_TICKERS, ALPHA_ANALYSIS

# 嘗試引入 rich
try:
    from rich.console import Console
    from rich.table import Table
    from rich import box

    HAS_RICH = True
except ImportError:
    HAS_RICH = False


# --- 1. 環境偵測 ---
def get_env():
    if "streamlit" in sys.modules or "streamlit.runtime" in sys.modules:
        return "streamlit"
    try:
        from IPython.core.getipython import get_ipython

        if get_ipython().__class__.__name__ == "ZMQInteractiveShell":
            return "jupyter"
    except Exception:
        pass
    return "console"


CURRENT_ENV = get_env()
if CURRENT_ENV == "streamlit":
    try:
        import streamlit as st
    except ImportError:
        CURRENT_ENV = "console"

# --- 2. 核心計算邏輯 ---


def set_chinese_font():
    system = platform.system()
    if system == "Darwin":
        plt.rcParams["font.sans-serif"] = ["Arial Unicode MS"]
    elif system == "Windows":
        plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei"]
    plt.rcParams["axes.unicode_minus"] = False


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


def get_batch_buy_signals(tickers: list):
    """
    For a list of tickers, download data in one batch and calculate the buy signal for each.
    This is much more efficient than downloading one by one in a loop.
    Returns a dictionary mapping each ticker to its signal light ('🔴', '🟡', '⚠️', '🟢').
    """
    if not tickers:
        return {}

    # Define signals
    strong = "🟠"  # 極度價值區 (低於季線，強力加碼)
    buy = "🟡"  # 價值區 (低於月線，適合分批加加碼)
    warning = "🔴"  # 過熱區 (遠離月線，暫緩加碼)
    healthy = "🟢"  # 趨勢區 (沿月線上漲，定期定額
    default_signal = "  "  # Default if data is unavailable

    signals = {}
    try:
        # Download data for all tickers at once. progress=False to keep console clean.
        # group_by='ticker' makes the data structure consistent even for a single ticker.
        # Use 1y period to be safer and ensure enough data for MA60
        data = yf.download(tickers, period="1y", progress=False, group_by="ticker")
        if data.empty:
            return {ticker: default_signal for ticker in tickers}

        for ticker in tickers:
            try:
                # Access data for the specific ticker. data.get(ticker) is safer.
                # When group_by='ticker', yfinance returns a multi-index DataFrame.
                # We select the sub-frame for the current ticker.
                if isinstance(data.columns, pd.MultiIndex):
                    ticker_df = data[ticker]
                else:  # Fallback for single ticker without MultiIndex
                    ticker_df = data

                if (
                    ticker_df is None
                    or ticker_df.empty
                    or ticker_df["Close"].isnull().all()
                ):
                    signals[ticker] = default_signal
                    continue

                ticker_data = ticker_df.copy()
                # Drop rows where 'Close' is NaN. This handles non-trading days or
                # days with incomplete data, which would cause MA to be NaN.
                ticker_data.dropna(subset=["Close"], inplace=True)

                # Calculate MAs
                ticker_data["MA20"] = ticker_data["Close"].rolling(window=20).mean()
                ticker_data["MA60"] = ticker_data["Close"].rolling(window=60).mean()

                # Get latest values
                latest = ticker_data.iloc[-1]
                current_price = latest["Close"]
                ma20 = latest["MA20"]
                ma60 = latest["MA60"]

                # Ensure values are not NaN before comparison
                if pd.isna(current_price) or pd.isna(ma20) or pd.isna(ma60):
                    signals[ticker] = default_signal
                    continue

                # Calculate bias and determine signal
                bias_ma20 = (current_price - ma20) / ma20 * 100
                if current_price <= ma60:
                    signals[ticker] = strong
                elif current_price <= ma20:
                    signals[ticker] = buy
                elif bias_ma20 > 5:
                    signals[ticker] = warning
                else:
                    signals[ticker] = healthy

            except KeyError, IndexError:
                signals[ticker] = default_signal  # This ticker might have failed
    except Exception:
        return {
            ticker: default_signal for ticker in tickers
        }  # General download failure
    return signals


def calculate_tick_price(price, market_type):
    """根據不同市場與價格區間，計算合法的掛單跳動單位"""
    if market_type == "JP_ETF":
        return round(price, 1)  # 日股 ETF 通常小數點第一位
    elif market_type == "TW_ETF":
        # 台股 50 元以下 ETF，跳動單位為 0.05
        return math.floor(price / 0.05) * 0.05
    elif market_type in ["TW_STOCK_HIGH", "TW_ETF_HIGH"]:
        # 台股 1000 元以上，跳動單位為 5 元
        return math.floor(price / 5.0) * 5.0
    return round(price, 2)


def calculate_assets_data(exchange_rates):
    """計算所有資產數據"""
    results = []
    # PROFIT_GOAL = 100

    def process_asset(asset, category, price=None):
        try:
            ccy = asset["ccy"]
            rate = exchange_rates.get(ccy, 1)  # 從字典取匯率，預設為 1 (TWD)
            inv = asset.get("investment", [])
            total_units = sum(i.get("units", i.get("shares", 0)) for i in inv)
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
            discount = asset.get("discount")
            if price is not None and m_type and discount:
                suggested_bid = calculate_tick_price(price * discount, m_type)

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
            price = None
            if asset.get("get_value", False):
                try:
                    price = yf.Ticker(asset["id"]).fast_info["last_price"]
                except Exception:
                    pass
            res = process_asset(asset, category, price)
            if res:
                results.append(res)

    df = pd.DataFrame(results)  # This df contains individual asset data
    if not df.empty:
        df.sort_values(by=["幣別", "報酬率"], ascending=[False, False], inplace=True)
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


# --- 3. 顯示層 ---
def plot_asset_allocation(df, exchange_rates):
    """繪製資產分佈圓餅圖 (市場別 & 項目別)"""

    # 定義共用的 autopct 產生器
    def make_autopct(values):
        def my_autopct(pct):
            total = sum(values)
            val = int(round(pct * total / 100.0))
            # 若佔比小於 1% 則不顯示文字，避免重疊
            return f"{pct:.1f}%\n(${val:,})" if pct > 1 else ""

        return my_autopct

    # 建立 1x2 的子圖 (寬度設大一點以容納兩張圖)
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # --- 左圖：市場分佈 ---
    market_dist = df.groupby("市場")["市值"].sum()
    market_dist.plot(
        kind="pie",
        autopct=make_autopct(market_dist),
        startangle=140,
        shadow=True,
        ax=axes[0],
        ylabel="",
    )
    rates_str_parts = []
    if "JPY" in exchange_rates:
        rates_str_parts.append(f"JPY/TWD: {exchange_rates['JPY']:.4f}")
    if "USD" in exchange_rates:
        rates_str_parts.append(f"USD/TWD: {exchange_rates['USD']:.2f}")
    axes[0].set_title(f"資產分佈 - 市場別 ({', '.join(rates_str_parts)})", fontsize=14)

    # --- 右圖：項目分佈 ---
    # 移除名稱中的 Emoji，避免 Matplotlib 字型警告
    clean_names = (
        df["名稱"]
        .astype(str)
        .str.replace("🏆 ", "", regex=False)
        .str.replace("🚩 ", "", regex=False)
    )
    item_dist = df.set_index(clean_names)["市值"]
    item_dist.plot(
        kind="pie",
        autopct=make_autopct(item_dist),
        startangle=140,
        shadow=True,
        ax=axes[1],
        ylabel="",
    )
    axes[1].set_title("資產分佈 - 項目別", fontsize=14)

    plt.tight_layout()
    plt.show()


def show_streamlit(df, radar_data, market_share_data, alpha_results):
    st.set_page_config(page_title="全球資產看板", layout="wide")
    st.title("📈 全球資產即時監控")

    # 雷達區
    cols = st.columns(len(radar_data) + 1)
    for i, item in enumerate(radar_data):
        cols[i].metric(item["名稱"], f"{item['數值']:,.2f}", f"{item['漲跌幅']:+.2f}%")

    total_pl = df["損益"].sum()
    roi = total_pl / df["成本"].sum() * 100
    cols[-1].metric("總損益", f"${total_pl:+,.0f}", f"{roi:+.2f}%")

    st.subheader("📋 持倉明細")
    st.dataframe(
        df.style.format(
            {
                "單位數": "{:,.2f}",
                "平均成本": "{:,.2f}",
                "股價": "{:,.2f}",
                "建議掛單": "{:,.2f}",
                "市值": "${:,.0f}",
                "損益": "${:+,.0f}",
                "報酬率": "{:+.2f}%",
                "佔比": "{:.1f}%",
            }
        ).map(
            lambda x: "color: #ff4b4b" if x > 0 else "color: #00c853", subset=["損益"]
        ),
        use_container_width=True,
    )

    st.subheader("📊 資產分佈")
    st.subheader("🌍 市場分佈佔比")
    market_share_cols = st.columns(len(market_share_data))
    for i, (market, share) in enumerate(market_share_data.items()):
        market_share_cols[i].metric(market, f"{share:.1f}%")

    set_chinese_font()
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.pie(
        df["市值"],
        labels=df["名稱"].str.replace(r"[^\w\s-]", "", regex=True),
        autopct="%1.1f%%",
    )
    st.pyplot(fig)

    if alpha_results:
        st.subheader("🔬 Alpha 穩定性分析")
        for result in alpha_results:
            with st.expander(
                f"{result['name']} ({result['target']} vs {result['benchmark']})"
            ):
                col1, col2, col3 = st.columns(3)
                col1.metric("觀測月份", f"{result['total_months']} 個月")
                col2.metric("月度勝率", f"{result['batting_avg']:.1f}%")
                col3.metric("平均月 Alpha", f"{result['avg_alpha']:+.2f}%")
                st.text("近期對決明細 (每月 Alpha %):")
                st.dataframe(
                    result["recent_alpha"].to_frame("Alpha").style.format("{:+.2%}")
                )


def show_console_rich(df, radar_data, market_share_data, alpha_results):
    console = Console()

    # 1. 顯示雷達
    console.print("\n[bold cyan]--- 🌍 全球市場即時雷達 ---[/bold cyan]")
    radar_table = Table(box=box.SIMPLE_HEAD, show_header=True)
    radar_table.add_column("指標名稱", style="cyan")
    radar_table.add_column("數值", justify="right")
    radar_table.add_column("漲跌幅", justify="right")

    for item in radar_data:
        color = "red" if item["漲跌幅"] > 0 else "green"
        radar_table.add_row(
            item["名稱"],
            f"{item['數值']:,.2f}",
            f"[{color}]{item['漲跌幅']:+.2f}%[/{color}]",
        )
    console.print(radar_table)
    console.print("")

    # 2. 顯示市場分佈佔比
    console.print("[bold cyan]--- 🌍 市場分佈佔比 ---[/bold cyan]")
    market_share_table = Table(box=box.SIMPLE_HEAD, show_header=True)
    market_share_table.add_column("市場", style="cyan")
    market_share_table.add_column("佔比", justify="right")

    for market, share in market_share_data.items():
        market_share_table.add_row(market, f"{share:.1f}%")
    console.print(market_share_table)
    console.print("")

    # Alpha 分析
    if alpha_results:
        console.print("[bold cyan]--- 🔬 Alpha 穩定性分析 ---[/bold cyan]")
        for result in alpha_results:
            title = f"{result['name']} ({result['target']} vs {result['benchmark']})"
            summary_table = Table(box=box.ROUNDED, show_header=False, title=title)
            summary_table.add_row("觀測月份", f"{result['total_months']} 個月")
            summary_table.add_row("月度勝率", f"{result['batting_avg']:.1f}%")
            summary_table.add_row("平均月 Alpha", f"{result['avg_alpha']:+.2f}%")
            console.print(summary_table)

            details_table = Table(
                box=box.SIMPLE, show_header=True, caption="近期對決明細 (每月 Alpha %)"
            )
            details_table.add_column("月份", style="dim")
            details_table.add_column("Alpha (%)", justify="right")
            for date, value in result["recent_alpha"].items():
                color = "red" if value > 0 else "green"
                details_table.add_row(
                    date.strftime("%Y-%m"), f"[{color}]{value:+.2%}[/{color}]"
                )
            console.print(details_table)
        console.print("")

    # 2. 顯示資產表
    console.print(
        f"[bold yellow]📅 報表時間: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}[/bold yellow]"
    )
    table = Table(box=box.SIMPLE, show_header=True)

    # Pre-calculate buy signals for all ETFs to avoid repeated downloads in the loop

    # Only get signals for ETFs configured with "ge__value": True
    # Only get signals for assets configured with "get_value": True from both funds and etfs
    tickers_to_signal = [
        asset["id"]
        for category in ["funds", "etfs"]
        for asset in ASSETS[category].values()
        if asset.get("get_value", False)
    ]
    buy_signals = get_batch_buy_signals(tickers_to_signal)

    cols_config = [
        ("訊號", "dim white", "center"),
        ("市場", "cyan", "left"),
        ("名稱", "white", "left"),
        ("代碼", "dim white", "left"),
        ("幣別", "yellow", "center"),
        ("單位數", "dim white", "right"),
        ("平均成本", "dim white", "right"),
        ("股價", "bold white", "right"),
        ("建議掛單", "magenta", "right"),
        ("成本", "dim white", "right"),
        ("市值", "bold white", "right"),
        ("損益", "bold", "right"),
        ("報酬率", "bold", "right"),
        ("佔比", "blue", "right"),
    ]
    for c, s, j in cols_config:
        table.add_column(c, style=s, justify=j)

    for _, row in df.iterrows():
        color = "red" if row["損益"] > 0 else "green"

        # 從預先計算的結果中查找買賣訊號
        signal = buy_signals.get(row["代碼"], " ")
        bid_str = f"{row['建議掛單']:,.2f}" if row["建議掛單"] > 0 else "-"

        table.add_row(
            signal,
            row["市場"],
            row["名稱"],
            row["代碼"],
            row["幣別"],
            f"{row['單位數']:,.2f}",
            f"{row['平均成本']:,.2f}",
            f"{row['股價']:,.2f}",
            bid_str,
            f"${row['成本']:,}",
            f"${row['市值']:,}",
            f"[{color}]{row['損益']:+,.0f}[/]",
            f"[{color}]{row['報酬率']:+.1f}%[/]",
            f"{row['佔比']:.1f}%",
        )
    console.print(table)

    # 3. 總結
    t_val = df["市值"].sum()
    t_pl = df["損益"].sum()
    t_roi = t_pl / df["成本"].sum() * 100
    console.print(
        f"\n💰 [bold]總市值: ${t_val:,}[/] | 📈 [bold]總損益: [{'red' if t_pl > 0 else 'green'}]{t_pl:+,.0f} ({t_roi:+.2f}%)[/]"
    )
    console.print("=" * 60)


def show_jupyter(df, radar_data, exchange_rates, market_share_data, alpha_results):
    from IPython.display import display, HTML

    set_chinese_font()

    # 1. 顯示雷達 (使用 DataFrame 取代 print 以解決跑版)
    print("--- 🌍 全球市場雷達 ---")
    radar_df = pd.DataFrame(radar_data)[["名稱", "數值", "漲跌幅"]]
    # 格式化
    radar_style = radar_df.style.format({"數值": "{:,.2f}", "漲跌幅": "{:+.2f}%"}).map(
        lambda x: "color: red" if x > 0 else "color: green", subset=["漲跌幅"]
    )
    # 隱藏 index 並顯示
    display(radar_style.hide(axis="index"))

    # 顯示市場分佈佔比
    print("\n--- 🌍 市場分佈佔比 ---")
    market_share_df_display = market_share_data.reset_index()
    market_share_df_display.columns = ["市場", "佔比"]
    display(
        market_share_df_display.style.format({"佔比": "{:.1f}%"}).hide(axis="index")
    )
    print("\n")

    # Alpha 分析
    if alpha_results:
        print("\n--- 🔬 Alpha 穩定性分析 ---")
        for result in alpha_results:
            print(f"\n{result['name']} ({result['target']} vs {result['benchmark']})")

            summary_data = {
                "指標": ["觀測月份", "月度勝率", "平均月 Alpha"],
                "數值": [
                    f"{result['total_months']} 個月",
                    f"{result['batting_avg']:.1f}%",
                    f"{result['avg_alpha']:+.2f}%",
                ],
            }
            summary_df = pd.DataFrame(summary_data)
            display(summary_df.style.hide(axis="index"))

            print("\n近期對決明細 (每月 Alpha %):")
            recent_alpha_df = result["recent_alpha"].to_frame("Alpha (%)")
            recent_alpha_df.index = recent_alpha_df.index.strftime("%Y-%m")
            display(recent_alpha_df.style.format({"Alpha (%)": "{:+.2%}"}))
        print("\n")

    print("\n")

    # 2. 顯示資產表
    display(
        df.style.format(
            {
                "單位數": "{:,.2f}",
                "平均成本": "{:,.2f}",
                "股價": "{:,.2f}",
                "建議掛單": "{:,.2f}",
                "成本": "${:,.0f}",
                "市值": "${:,.0f}",
                "損益": "${:+,.0f}",
                "報酬率": "{:+.2f}%",
                "佔比": "{:.1f}%",
            }
        ).map(
            lambda x: "color: red" if x > 0 else "color: green",
            subset=["損益", "報酬率"],
        )
    )

    # 3. 總結
    t_pl = df["損益"].sum()
    t_cost = df["成本"].sum()
    print(
        f"💰 總市值: ${df['市值'].sum():,} | 📈 總損益: ${t_pl:+,.0f} ({(t_pl / t_cost * 100):+.2f}%)"
    )

    plot_asset_allocation(df, exchange_rates)


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

        return {
            "total_months": len(monthly_returns),
            "batting_avg": batting_avg,
            "avg_alpha": avg_alpha,
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
        result = calculate_single_alpha(
            analysis["target"], analysis["benchmark"], analysis["start"]
        )
        if result:
            analysis_results.append(
                {
                    "name": analysis["name"],
                    "target": analysis["target"],
                    "benchmark": analysis["benchmark"],
                    **result,
                }
            )
    return analysis_results


# --- 4. 主程式 ---

if __name__ == "__main__":
    # alpha_results = run_alpha_analysis()
    alpha_results = None
    radar = get_market_radar_data()
    exchange_rates = {
        "JPY": next(
            (item["數值"] for item in radar if item["代碼"] == "JPYTWD=X"), 0.215
        ),
        "USD": next(
            (item["數值"] for item in radar if item["代碼"] == "USDTWD=X"), 32.0
        ),
        "TWD": 1,
    }  # This is correct
    df_res, market_share_data = calculate_assets_data(exchange_rates)

    if CURRENT_ENV == "streamlit":
        show_streamlit(df_res, radar, market_share_data, alpha_results)
    elif CURRENT_ENV == "jupyter":
        show_jupyter(df_res, radar, exchange_rates, market_share_data, alpha_results)
    elif HAS_RICH:
        show_console_rich(df_res, radar, market_share_data, alpha_results)
    else:
        print(df_res.to_string())
