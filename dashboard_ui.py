# -*- coding: utf-8 -*-
import pandas as pd
import matplotlib.pyplot as plt
import platform

# 嘗試引入 rich
try:
    from rich.console import Console
    from rich.table import Table
    from rich import box
    from rich.align import Align

    HAS_RICH = True
except ImportError:
    HAS_RICH = False


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

    # st.set_page_config 應在進入點 dashboard.py 優先執行，此處已移除
    st.title("📈 全球資產即時監控")
    cols = st.columns(len(radar_data) + 1)
    for i, item in enumerate(radar_data):
        cols[i].metric(item["名稱"], f"{item['數值']:,.2f}", f"{item['漲跌幅']:+.2f}%")
    total_pl = df["損益"].sum()
    roi = total_pl / df["成本"].sum() * 100
    cols[-1].metric("總損益", f"${total_pl:+,.0f}", f"{roi:+.2f}%")

    st.subheader("📋 持倉明細")
    event = st.dataframe(
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
        width="stretch",
        on_select="rerun",
        selection_mode="single-row",
    )

    # 處理點擊選取事件
    if event and event.selection and event.selection.rows:
        idx = event.selection.rows[0]
        selected_row = df.iloc[idx]
        ticker = selected_row["代碼"]
        category = selected_row["類型"]

        if category == "ETF":
            st.markdown(f"### 🔍 {selected_row['名稱']} ({ticker}) 進階量化分析")
            from dashboard_logic import run_advanced_analysis

            with st.spinner(f"正在分析 {ticker} 的相對強度與 Alpha 穩定性..."):
                # 執行進階分析 (針對單一選定股票)
                adv_results = run_advanced_analysis(pd.DataFrame([selected_row]))

                if not adv_results.empty:
                    res = adv_results.iloc[0]
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("RS 百分位", res["RS 百分位"], res["狀態"])
                    col2.metric("Alpha 勝率", res["Alpha 勝率"])
                    col3.metric("月度 Alpha", res["月度 Alpha"])
                    col4.metric("夏普值 (Sharpe)", res["夏普值"])

                    # 診斷與掛單區塊
                    st.info(f"**技術診斷：**\n{res['技術診斷']}")

                    with st.expander("📊 技術位階與建議掛單", expanded=True):
                        c1, c2, c3 = st.columns(3)
                        c1.write(f"**日常波段點位:** {res['日常波段']}")
                        c2.write(f"**技術回測點位:** {res['技術回測']}")
                        c3.write(f"**狙擊防守位:** {res['狙擊位']}")
                        st.caption(
                            f"當前股價: {res['股價']} | MA20: {res['MA20']} | MA60: {res['MA60']} | MA120: {res['MA120']}"
                        )
                else:
                    st.warning("暫無進階數據（可能因歷史資料不足或抓取失敗）")
        else:
            st.info(
                f"「{selected_row['名稱']}」為{category}類型，暫不支援進階量化分析。"
            )


def show_console_rich(
    df,
    radar_data,
    market_share_data,
    advanced_results=None,
    show_report=True,
    console=None,
    is_list_mode=False,
):
    if not HAS_RICH:
        print(df.to_string())
        return
    console = console or Console()
    # 1. 顯示雷達
    console.print("\n[bold cyan]--- 全球市場即時雷達 ---[/bold cyan]")
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
        console.print("[bold cyan]--- 市場分佈佔比 ---[/bold cyan]")
        market_share_table = Table(box=box.SIMPLE_HEAD, show_header=True)
        market_share_table.add_column("市場", style="cyan")
        market_share_table.add_column("總市值", justify="right")
        market_share_table.add_column("佔比", justify="right")

        for market, data in market_share_data.items():
            market_share_table.add_row(
                market, f"${data['市值']:,.0f}", f"{data['佔比']:.1f}%"
            )
        console.print(market_share_table)

    if advanced_results is not None and not advanced_results.empty:
        console.print("\n[bold cyan]--- 進階量化分析 ---[/bold cyan]")

        for _, row in advanced_results.iterrows():
            ticker = str(row["代碼"])
            console.print(f"\n[bold yellow]== {ticker} ==[/bold yellow]")

            console.print(
                f"EPS:{row.get('EPS', 0):.2f} 本益比:{row.get('PE', 0):.1f} 成交量比率:{row.get('量比', '-')}"
            )

            console.print(
                f"\n股價位置:{row.get('狀態', '-')} 燈號:{row.get('技術燈號', '-')} "
            )

            if is_list_mode:
                # 列表模式：直接輸出關鍵數值，確保 AI 讀取不截斷
                val_alpha = (
                    str(row.get("月度 Alpha", "-"))
                    .replace("[red]", "")
                    .replace("[green]", "")
                    .replace("[/]", "")
                )
                metrics = [
                    f"  > 股價: {row.get('股價', '-')} | RS: {row.get('當前 RS', '-')} ({row.get('RS 百分位', '-')})",
                    f"  > Alpha勝率: {row.get('Alpha 勝率', '-')} | 月度Alpha: {val_alpha} | 夏普值: {row.get('夏普值', '-')}",
                    f"  > 乖離率: {row.get('乖離率 (Bias)', '-')} | MA20: {row.get('MA20', '-')} | MA250: {row.get('MA250', '-')}",
                    f"  > 建議位階: 波段 {row.get('日常波段', '-')} / 回測 {row.get('技術回測', '-')} / 狙擊 {row.get('狙擊位', '-')}",
                ]
                for line in metrics:
                    console.print(line)
            else:
                # 原始表格模式 (適用於終端機寬螢幕顯示)
                mini_table = Table(box=box.SIMPLE, show_header=True)
                cols = [
                    "股價",
                    "RS",
                    "RS%",
                    "α勝率",
                    "月度α",
                    "夏普值",
                    "乖離率",
                    "MA20",
                    "MA60",
                    "MA120",
                    "MA250",
                    "波段",
                    "回測",
                    "狙擊",
                ]
                for col in cols:
                    style = "magenta" if col in ["波段", "回測", "狙擊"] else None
                    mini_table.add_column(col, justify="right", style=style)

                val_alpha = row.get("月度 Alpha", "-")
                alpha_color = (
                    "red"
                    if "+" in str(val_alpha)
                    else "green"
                    if "-" in str(val_alpha)
                    else "white"
                )

                mini_table.add_row(
                    str(row.get("股價", "-")),
                    str(row.get("當前 RS", "-")),
                    str(row.get("RS 百分位", "-")),
                    str(row.get("Alpha 勝率", "-")),
                    f"[{alpha_color}]{val_alpha}[/{alpha_color}]",
                    str(row.get("夏普值", "-")),
                    str(row.get("乖離率 (Bias)", "-")),
                    str(row.get("MA20", "-")),
                    str(row.get("MA60", "-")),
                    str(row.get("MA120", "-")),
                    str(row.get("MA250", "-")),
                    str(row.get("日常波段", "-")),
                    str(row.get("技術回測", "-")),
                    str(row.get("狙擊位", "-")),
                )
                console.print(mini_table)

            console.print(f"{row.get('技術診斷', '-')}")

            console.print("\n" + "=" * 73)

    if show_report:
        # 顯示資產表
        console.print(
            f"\n[bold yellow]📅 報表時間: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}[/bold yellow]"
        )
        table = Table(box=box.SIMPLE)
        cols_config = [
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
