# -*- coding: utf-8 -*-
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import platform
import sys
import math
from assets_config import ASSETS

# 嘗試引入 rich
try:
    from rich.console import Console
    from rich.table import Table
    from rich import box

    HAS_RICH = True
except ImportError:
    HAS_RICH = False


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


def set_chinese_font():
    system = platform.system()
    if system == "Darwin":
        plt.rcParams["font.sans-serif"] = ["Arial Unicode MS"]
    elif system == "Windows":
        plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei"]
    plt.rcParams["axes.unicode_minus"] = False


def get_batch_buy_signals(tickers: list):
    """
    計算買賣訊號燈號 (UI 輔助邏輯)
    """
    if not tickers:
        return {}
    strong, buy, warning, healthy, default_signal = "🟠", "🟡", "🔴", "🟢", "  "
    signals = {}
    try:
        data = yf.download(tickers, period="1y", progress=False, group_by="ticker")
        if data.empty:
            return {ticker: default_signal for ticker in tickers}
        for ticker in tickers:
            try:
                ticker_df = (
                    data[ticker] if isinstance(data.columns, pd.MultiIndex) else data
                )
                if (
                    ticker_df is None
                    or ticker_df.empty
                    or ticker_df["Close"].isnull().all()
                ):
                    signals[ticker] = default_signal
                    continue
                ticker_data = ticker_df.copy().dropna(subset=["Close"])
                ticker_data["MA20"] = ticker_data["Close"].rolling(window=20).mean()
                ticker_data["MA60"] = ticker_data["Close"].rolling(window=60).mean()
                latest = ticker_data.iloc[-1]
                current_price, ma20, ma60 = (
                    latest["Close"],
                    latest["MA20"],
                    latest["MA60"],
                )
                if pd.isna(current_price) or pd.isna(ma20) or pd.isna(ma60):
                    signals[ticker] = default_signal
                    continue
                bias_ma20 = (current_price - ma20) / ma20 * 100
                if current_price <= ma60:
                    signals[ticker] = strong
                elif current_price <= ma20:
                    signals[ticker] = buy
                elif bias_ma20 > 5:
                    signals[ticker] = warning
                else:
                    signals[ticker] = healthy
            except Exception:
                signals[ticker] = default_signal
    except Exception:
        return {ticker: default_signal for ticker in tickers}
    return signals


def plot_asset_allocation(df, exchange_rates):
    def make_autopct(values):
        def my_autopct(pct):
            total = sum(values)
            val = int(round(pct * total / 100.0))
            return f"{pct:.1f}%\n(${val:,})" if pct > 1 else ""

        return my_autopct

    set_chinese_font()
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    market_dist = df.groupby("市場")["市值"].sum()
    market_dist.plot(
        kind="pie",
        autopct=make_autopct(market_dist),
        startangle=140,
        shadow=True,
        ax=axes[0],
        ylabel="",
    )
    rates_str = ", ".join(
        [f"{k}/TWD: {v:.4f}" for k, v in exchange_rates.items() if k != "TWD"]
    )
    axes[0].set_title(f"資產分佈 - 市場別 ({rates_str})", fontsize=14)
    clean_names = df["名稱"].astype(str).str.replace(r"[🏆🚩]", "", regex=True)
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


def show_streamlit(df, radar_data, market_share_data, alpha_results, rs_results=None):
    import streamlit as st

    st.set_page_config(page_title="全球資產看板", layout="wide")
    st.title("📈 全球資產即時監控")
    cols = st.columns(len(radar_data) + 1)
    for i, item in enumerate(radar_data):
        cols[i].metric(item["名稱"], f"{item['數值']:,.2f}", f"{item['漲跌幅']:+.2f}%")
    total_pl = df["損益"].sum()
    roi = total_pl / df["成本"].sum() * 100
    cols[-1].metric("總損益", f"${total_pl:+,.0f}", f"{roi:+.2f}%")

    if rs_results is not None and not rs_results.empty:
        st.subheader("📊 跨市場 RS 強度排行榜")
        st.dataframe(rs_results.drop(columns=["score"]), use_container_width=True)

    st.subheader("📋 持倉明細")
    st.dataframe(
        df.style.format(
            {
                "單位數": "{:,.2f}",
                "平均成本": "{:,.2f}",
                "漲跌": lambda x: f"{x:+,.2f}" if pd.notnull(x) else "-",
                "股價": "{:,.2f}",
                "建議掛單": "{:,.2f}",
                "市值": "${:,.0f}",
                "損益": "${:+,.0f}",
                "報酬率": "{:+.2f}%",
                "佔比": "{:.1f}%",
            }
        ).map(
            lambda x: (
                "color: #ff4b4b"
                if (pd.notnull(x) and x > 0)
                else ("color: #00c853" if (pd.notnull(x) and x < 0) else "")
            ),
            subset=["損益", "漲跌"],
        ),
        use_container_width=True,
    )

    if alpha_results:
        st.subheader("🔬 Alpha 穩定性分析")
        st.dataframe(pd.DataFrame(alpha_results), use_container_width=True)


def show_console_rich(
    df, radar_data, market_share_data, alpha_results, rs_results=None
):
    if not HAS_RICH:
        print(df.to_string())
        return
    console = Console()
    console.print("\n[bold cyan]--- 🌍 全球市場即時雷達 ---[/bold cyan]")
    radar_table = Table(box=box.SIMPLE_HEAD)
    radar_table.add_column("指標名稱")
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

    if rs_results is not None and not rs_results.empty:
        console.print("\n[bold cyan]--- 📊 跨市場 RS 排行榜 ---[/bold cyan]")
        rs_table = Table(box=box.SIMPLE_HEAD)
        for col in rs_results.columns:
            rs_table.add_column(col)
        for _, row in rs_results.iterrows():
            rs_table.add_row(*[str(v) for v in row.values])
        console.print(rs_table)

    # 顯示資產表
    console.print(
        f"\n[bold yellow]📅 報表時間: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}[/bold yellow]"
    )
    table = Table(box=box.SIMPLE)
    tickers_to_signal = [
        a["id"]
        for cat in ["funds", "etfs"]
        for a in ASSETS[cat].values()
        if a.get("get_value") and a.get("enabled", True)
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
        ("漲跌", "bold", "right"),
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

        # 處理漲跌欄位的顏色 (Console)
        if pd.notnull(row["漲跌"]):
            change_color = "red" if row["漲跌"] > 0 else "green"
            change_str = f"[{change_color}]{row['漲跌']:+,.2f}[/]"
        else:
            change_str = "-"

        bid_str = f"{row['建議掛單']:,.2f}" if row["建議掛單"] > 0 else "-"

        table.add_row(
            buy_signals.get(row["代碼"], " "),
            row["市場"],
            row["名稱"],
            row["代碼"],
            row["幣別"],
            f"{row['單位數']:,.2f}",
            f"{row['平均成本']:,.2f}",
            change_str,
            f"{row['股價']:,.2f}",
            bid_str,
            f"${row['成本']:,}",
            f"${row['市值']:,}",
            f"[{color}]{row['損益']:+,.0f}[/]",
            f"[{color}]{row['報酬率']:+.1f}%[/]",
            f"{row['佔比']:.1f}%",
        )
    console.print(table)
    t_val, t_pl = df["市值"].sum(), df["損益"].sum()
    console.print(
        f"\n💰 [bold]總市值: ${t_val:,}[/] | 📈 [bold]總損益: {t_pl:+,.0f}[/]"
    )


def show_jupyter(
    df, radar_data, exchange_rates, market_share_data, alpha_results, rs_results=None
):
    from IPython.display import display

    set_chinese_font()
    print("--- 🌍 全球市場雷達 ---")
    display(pd.DataFrame(radar_data).style.hide(axis="index"))
    if rs_results is not None:
        print("\n--- 📊 RS 排行榜 ---")
        display(rs_results.hide(axis="index"))
    print("\n--- 📋 資產明細 ---")
    display(
        df.style.format(
            {
                "單位數": "{:,.2f}",
                "平均成本": "{:,.2f}",
                "漲跌": lambda x: f"{x:+,.2f}" if pd.notnull(x) else "-",
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
            subset=["損益", "報酬率", "漲跌"],
        )
    )
    plot_asset_allocation(df, exchange_rates)
