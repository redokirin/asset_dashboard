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
    return fig


def render_advanced_analysis_ui(res):
    """合併後的進階量化分析渲染組件 - 仿範例圖配置"""
    import streamlit as st

    # 注入局部 CSS 縮小此區塊的 Metric 字體
    st.markdown(
        """
        <style>
        /* 使用更強大的選擇器並確保 !important */
        div[data-testid="stMetricValue"] > div { font-size: 1.1rem !important; }
        div[data-testid="stMetricLabel"] > div { font-size: 0.75rem !important; }
        div[data-testid="stMetricDelta"] > div { font-size: 0.75rem !important; }
        </style>
    """,
        unsafe_allow_html=True,
    )

    # --- 1. 標籤雲 ---
    if "tags" in res and res["tags"]:
        tag_html = "".join(
            [
                f'<span style="background-color: #262730; color: white; padding: 3px 10px; border-radius: 10px; margin-right: 6px; border: 1px solid #464646; font-size: 0.8rem; font-weight: 500;">{tag}</span>'
                for tag in res["tags"]
            ]
        )
        st.markdown(tag_html, unsafe_allow_html=True)
        # st.write("**💡 技術診斷**")
        st.info(f"{res['技術診斷']}")
        # st.write("")

    # --- 2. 綜合診斷 (1:1 佈局) ---
    c1, c2 = st.columns(2)

    with c1:
        st.write("**🎯 建議掛單位階**")
        b1, b2, b3, b4 = st.columns(4)
        b1.metric("股價", res["股價"])
        b2.metric("日常波段", res["日常波段"])
        b3.metric("技術回測", res["技術回測"])
        b4.metric("狙擊防守", res["狙擊位"])

        st.write("**📊 均線參考**")
        sc1, sc2, sc3, sc4 = st.columns(4)
        sc1.metric("MA20", res["MA20"])
        sc2.metric("MA60", res["MA60"])
        sc3.metric("MA120", res["MA120"])
        sc4.metric("MA250", res["MA250"])

    with c2:
        st.markdown('<div class="small-metric">', unsafe_allow_html=True)
        st.write("**📊 財務指標**")
        f1, f2, f3 = st.columns(3)
        f1.metric("每股盈餘 (EPS)", res["EPS"])
        f2.metric("本益比 (PE)", f"{res['PE']:.1f}")
        f3.metric("成交量比 (量比)", res["量比"])

        st.write("**📊 量化核心指標**")
        # 合併數據顯示
        m1, m2, m3 = st.columns(3)
        m1.metric("RS 百分位", res["RS 百分位"])
        m2.metric("RSI (14)", f"{res.get('RSI', 0):.1f}")
        m3.metric("夏普值 (Sharpe)", res["夏普值"])

        m4, m5, m6 = st.columns(3)
        m4.metric("Alpha 勝率", res["Alpha 勝率"])
        m5.metric("月度 Alpha", res["月度 Alpha"])
        m6.metric("乖離率 (Bias)", res["乖離率 (Bias)"])

        # st.markdown("</div>", unsafe_allow_html=True)


def show_manual_analysis_page():
    import streamlit as st
    import pandas as pd
    from dashboard_logic import run_advanced_analysis

    st.info("請在此輸入標的代碼，系統將執行深度量化診斷。")
    manual_codes = st.text_input(
        "🔍 代碼輸入", placeholder="例如: 2330.TW 6284.TWO VOO"
    )

    if manual_codes:
        codes = [c.strip().upper() for c in manual_codes.split() if c.strip()]
        if codes:
            manual_df = pd.DataFrame(
                [
                    {
                        "市場": "手動",
                        "類型": "ETF",
                        "名稱": c,
                        "代碼": c,
                        "幣別": "TWD",
                        "單位數": 0,
                        "平均成本": 0.0,
                        "漲跌": "-",
                        "股價": 0.0,
                        "建議掛單": 0.0,
                        "成本": 0,
                        "市值": 0,
                        "損益": 0,
                        "報酬率": 0.0,
                        "佔比": 0.0,
                    }
                    for c in codes
                ]
            )
            with st.spinner("分析中..."):
                adv_manual = run_advanced_analysis(manual_df)
                if not adv_manual.empty:
                    for _, res in adv_manual.iterrows():
                        with st.expander(
                            f"📈 {res['名稱']} ({res['代碼']}) 報告", expanded=True
                        ):
                            render_advanced_analysis_ui(res)


def render_plotly_pie_charts(df, exchange_rates):
    """使用 Plotly 渲染互動式圓餅圖 (橫向並排，圖例在右側)"""
    import plotly.express as px
    import streamlit as st

    # c1, c2 = st.columns(2)

    # 1. 市場別
    market_df = df.groupby("市場")["市值"].sum().reset_index()
    fig_market = px.pie(
        market_df,
        values="市值",
        names="市場",
        title="資產分析-市場別",
        hole=0.0,
        color_discrete_sequence=px.colors.qualitative.Pastel,
    )
    fig_market.update_layout(
        showlegend=True,
        legend=dict(orientation="v", yanchor="top", y=-2.5, xanchor="left", x=0.0),
        margin=dict(t=40, b=40, l=0, r=80),
        height=280,
    )
    # with c1:
    st.plotly_chart(fig_market, width="stretch")

    # 2. 項目別
    item_df = df.copy()
    item_df["顯示名稱"] = (
        item_df["名稱"].astype(str).str.replace(r"[🏆🚩]", "", regex=True)
    )
    fig_item = px.pie(
        item_df,
        values="市值",
        names="顯示名稱",
        title="資產分析-項目別",
        hole=0.5,
        color_discrete_sequence=px.colors.qualitative.Set3,
    )
    fig_item.update_layout(
        showlegend=True,
        legend=dict(orientation="v", yanchor="top", y=-10.0, xanchor="right", x=1.05),
        margin=dict(t=40, b=40, l=0, r=80),
        height=400,
    )
    # with c2:
    st.plotly_chart(fig_item, width="stretch")


def render_inline_metric(label, value, delta):
    """自定義橫向排列的指標組件"""
    import streamlit as st

    color = "#ff4b4b" if "+" in delta else "#00c853"
    st.markdown(
        f"""
        <div style='margin-bottom: 12px;'>
            <div style='font-size: 0.85rem; color: #8b949e; margin-bottom: 4px;'>{label}</div>
            <div style='display: flex; align-items: baseline;'>
                <span style='font-size: 1.6rem; font-weight: 600; color: white; margin-right: 10px;'>{value}</span>
                <span style='font-size: 0.85rem; color: {color}; background-color: {color}22; padding: 2px 8px; border-radius: 6px; font-weight: 500;'>{delta}</span>
            </div>
        </div>
    """,
        unsafe_allow_html=True,
    )


def show_streamlit(df, radar_data, exchange_rates):
    import streamlit as st

    # 1. 注入自定義 CSS (營造區塊感與深色背景卡片)
    st.markdown(
        """
        <style>
        /* 全域卡片容器樣式 */
        [data-testid="stVerticalBlock"] > div > div[data-testid="stVerticalBlockBorder"] {
            background-color: #1e2130;
            padding: 1.2rem;
            border-radius: 12px;
            border: 1px solid #2d323e;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            margin-bottom: 1rem;
        }
        /* 隱藏預設標題間距 */
        .block-container { padding-top: 2rem; }

        /* 進階分析區 (c1) 字體縮小規則 */
        .small-metric [data-testid="stMetricValue"] { font-size: 1.1rem !important; }
        .small-metric [data-testid="stMetricLabel"] { font-size: 0.75rem !important; }
        .small-metric p, .small-metric b { font-size: 0.8rem !important; }
        </style>
    """,
        unsafe_allow_html=True,
    )

    # 2. 佈局：[左欄指標, 中欄內容]
    col_left, col_mid = st.columns([0.5, 2])

    with col_left:
        with st.container(border=True):
            total_pl = df["損益"].sum()
            roi = total_pl / df["成本"].sum() * 100
            render_inline_metric("💰 總損益", f"${total_pl:+,.0f}", f"{roi:+.2f}%")

        st.markdown(
            "<div style='font-size: 0.9rem; font-weight: 600; color: white; margin-bottom: 10px;'>📊 資產權重分佈</div>",
            unsafe_allow_html=True,
        )
        with st.container(border=True):
            render_plotly_pie_charts(df, exchange_rates)

    with col_mid:
        # 3. 市場指數與匯率監控
        m_col1, m_col2 = st.columns([3, 1])
        with m_col1:
            st.markdown(
                "<div style='font-size: 0.9rem; font-weight: 600; color: white; margin-bottom: 10px;'>📉 指數</div>",
                unsafe_allow_html=True,
            )
            with st.container(border=True, height=100):
                # 市場指數：非匯率代碼 (不以 =X 結尾)
                indices = [
                    item for item in radar_data if not item["代碼"].endswith("=X")
                ]
                # 動態計算列數，最多每行 4 個
                display_indices = indices
                n_cols = min(len(display_indices), 4) if display_indices else 1
                idx_cols = st.columns(n_cols)
                for i, item in enumerate(display_indices):
                    with idx_cols[i % n_cols]:
                        render_inline_metric(
                            item["名稱"],
                            f"{item['數值']:,.2f}",
                            f"{item['漲跌幅']:+.2f}%",
                        )

        with m_col2:
            st.markdown(
                "<div style='font-size: 0.9rem; font-weight: 600; color: white; margin-bottom: 10px;'>💱 匯率</div>",
                unsafe_allow_html=True,
            )
            with st.container(border=True, height=100):
                # 匯率：代碼以 =X 結尾
                major_rates = [
                    item for item in radar_data if item["代碼"].endswith("=X")
                ]
                # 匯率橫向排列，最多每行 3 個
                n_rate_cols = min(len(major_rates), 3) if major_rates else 1
                rate_cols = st.columns(n_rate_cols)
                for i, item in enumerate(major_rates):
                    with rate_cols[i % n_rate_cols]:
                        color = "#ff4b4b" if item["漲跌幅"] > 0 else "#00c853"
                        st.markdown(
                            f"""
                            <div style='text-align: left; margin-bottom: 5px;'>
                                <div style='font-size: 0.75rem; color: #8b949e; line-height: 1.2;'>{item["名稱"]}</div>
                                <div style='font-size: 1.1rem; font-weight: 600; color: white; margin: 2px 0;'>{item["數值"]:.2f}</div>
                                <div style='font-size: 0.75rem; color: {color}; font-weight: 500;'>{item["漲跌幅"]:+.2f}%</div>
                            </div>
                        """,
                            unsafe_allow_html=True,
                        )

        # st.markdown(
        #     "<div style='font-size: 0.9rem; font-weight: 600; color: white; margin-bottom: 10px;'>📋 持倉明細</div>",
        #     unsafe_allow_html=True,
        # )
        # with st.container(border=True):
        df_view = df.copy()
        df_view["標的 (名稱)"] = df_view["代碼"] + "\n(" + df_view["名稱"] + ")"
        cols_display = [
            "標的 (名稱)",
            "市場",
            "單位數",
            "平均成本",
            "股價",
            "漲跌",
            # "成本",
            "市值",
            "損益",
            "報酬率",
            "佔比",
        ]

        event = st.dataframe(
            df_view[cols_display]
            .style.format(
                {
                    "單位數": "{:,.0f}",
                    "平均成本": "{:,.2f}",
                    "股價": "{:,.2f}",
                    "漲跌": "{:+,.2f}",
                    # "成本": "${:,.0f}",
                    "市值": "${:,.0f}",
                    "損益": "${:+,.0f}",
                    "報酬率": "{:+.2f}%",
                    "佔比": "{:.1f}%",
                }
            )
            .map(
                lambda x: (
                    "color: #ff4b4b"
                    if (pd.notnull(x) and x > 0)
                    else ("color: #00c853" if (pd.notnull(x) and x < 0) else "")
                ),
                subset=["損益", "報酬率", "漲跌"],
            ),
            width="stretch",
            on_select="rerun",
            selection_mode="single-row",
            hide_index=True,
            column_config={},
        )

        if event and event.selection and event.selection.rows:
            idx = event.selection.rows[0]
            selected_row = df.iloc[idx]
            st.markdown(f"#### 🔍 {selected_row['名稱']} 進階分析")
            with st.container(border=True):
                from dashboard_logic import run_advanced_analysis

                with st.spinner("分析中..."):
                    adv_results = run_advanced_analysis(pd.DataFrame([selected_row]))
                    if not adv_results.empty:
                        render_advanced_analysis_ui(adv_results.iloc[0])


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
            if is_list_mode:
                val_alpha = (
                    str(row.get("月度 Alpha", "-"))
                    .replace("[red]", "")
                    .replace("[green]", "")
                    .replace("[/]", "")
                )
                metrics = [
                    f"  > 股價: {row.get('股價', '-')} | RS%: {row.get('RS 百分位', '-')} | RSI: {row.get('RSI', 0):.1f}",
                    f"  > Alpha勝率: {row.get('Alpha 勝率', '-')} | 月度Alpha: {val_alpha} | 夏普值: {row.get('夏普值', '-')}",
                    f"  > 建議位階: 波段 {row.get('日常波段', '-')} / 回測 {row.get('技術回測', '-')} / 狙擊 {row.get('狙擊位', '-')}",
                ]
                for line in metrics:
                    console.print(line)
            else:
                mini_table = Table(box=box.SIMPLE, show_header=True)
                cols = [
                    "股價",
                    "RS",
                    "RS%",
                    "RSI",
                    # "RSI狀態",
                    "α勝率",
                    "月度α",
                    "夏普值",
                    "乖離率",
                    "MA20",
                    "MA60",
                    "MA120",
                    "MA250",
                    "日常波段",
                    "技術回測",
                    "狙擊目標",
                ]
                for col in cols:
                    mini_table.add_column(col, justify="right")
                mini_table.add_row(
                    str(row.get("股價", "-")),
                    str(row.get("RS", "-")),
                    str(row.get("RS%", "-")),
                    f"{row.get('RSI', 0):.1f}",
                    # str(row.get("RSI狀態", "-")),
                    str(row.get("Alpha 勝率", "-")),
                    str(row.get("月度 Alpha", "-")),
                    str(row.get("夏普值", "-")),
                    str(row.get("乖離率", "-")),
                    str(row.get("MA20", "-")),
                    str(row.get("MA60", "-")),
                    str(row.get("MA120", "-")),
                    str(row.get("MA250", "-")),
                    str(row.get("日常波段", "-")),
                    str(row.get("技術回測", "-")),
                    str(row.get("狙擊位", "-")),
                )
                console.print(mini_table)
            console.print(
                f"{' '.join(row.get('tags', []))}\n{row.get('技術診斷', '-')}"
            )
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
                "股價": "{:,.2f}",
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
    plot_asset_allocation(df, exchange_rates)
    plt.show()
