# -*- coding: utf-8 -*-
import pandas as pd
import matplotlib.pyplot as plt
import platform
import sys

from dashboard_logic import get_batch_buy_signals
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


def show_streamlit(df, radar_data):
    import streamlit as st

    st.set_page_config(page_title="全球資產看板", layout="wide")
    st.title("📈 全球資產即時監控")
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


def show_console_rich(
    df, radar_data, market_share_data, advanced_results=None, show_report=True
):
    if not HAS_RICH:
        print(df.to_string())
        return
    console = Console()
    # 1. 顯示雷達
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

    # 2. 顯示市場分佈佔比
    if show_report:
        console.print("[bold cyan]--- 🌍 市場分佈佔比 ---[/bold cyan]")
        market_share_table = Table(box=box.SIMPLE_HEAD, show_header=True)
        market_share_table.add_column("市場", style="cyan")
        market_share_table.add_column("總市值", justify="right")
        market_share_table.add_column("佔比", justify="right")

        for market, data in market_share_data.items():
            market_share_table.add_row(market, f"${data['市值']:,.0f}", f"{data['佔比']:.1f}%")
        console.print(market_share_table)

    if advanced_results is not None and not advanced_results.empty:
        console.print("\n[bold cyan]--- 🔬 進階量化分析 (RS & Alpha) ---[/bold cyan]")
        adv_table = Table(box=box.SIMPLE_HEAD, show_header=True)
        adv_table.add_column("代碼", style="dim")
        adv_table.add_column("名稱", style="white")
        adv_table.add_column("當前 RS", justify="right")
        adv_table.add_column("RS 百分位", justify="right", style="bold")
        adv_table.add_column("狀態", justify="left")
        adv_table.add_column("Alpha 勝率", justify="right", style="magenta")
        adv_table.add_column("月度 Alpha", justify="right", style="bold")
        adv_table.add_column("夏普值", justify="right")

        for _, row in advanced_results.iterrows():
            alpha_val = row["月度 Alpha"]
            alpha_color = "red" if "+" in str(alpha_val) else "green" if "-" in str(alpha_val) else "white"
            
            adv_table.add_row(
                str(row["代碼"]),
                str(row["名稱"]),
                str(row["當前 RS"]),
                str(row["RS 百分位"]),
                str(row["狀態"]),
                str(row["Alpha 勝率"]),
                f"[{alpha_color}]{alpha_val}[/{alpha_color}]",
                str(row["夏普值"])
            )
        console.print(adv_table)
        console.print("")

    if show_report:
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


def show_jupyter(df, radar_data, exchange_rates):
    from IPython.display import display

    set_chinese_font()
    print("--- 🌍 全球市場雷達 ---")
    display(pd.DataFrame(radar_data).style.hide(axis="index"))

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
