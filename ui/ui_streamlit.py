# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import os
import plotly.graph_objects as go
from core import dashboard_logic
from ui import ui_common


def render_price_chart(ticker):
    """渲染股價折線圖與均線"""
    try:
        # 使用 session_state 紀錄每個 ticker 的選中區間，預設為 6mo
        period_key = f"chart_period_{ticker}"
        if period_key not in st.session_state:
            st.session_state[period_key] = "6mo"

        # 區間選擇按鈕
        periods = ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y"]
        
        # 建立一個容器放置選擇器
        c1, c2 = st.columns([0.3, 0.7])
        with c1:
            st.markdown("<div style='padding-top: 5px; font-size: 0.8rem; color: #888;'>📅 走勢區間</div>", unsafe_allow_html=True)
        with c2:
            selected_period = st.segmented_control(
                "選擇區間",
                options=periods,
                default=st.session_state[period_key],
                key=f"selector_{ticker}",
                label_visibility="collapsed"
            )
        
        if selected_period and selected_period != st.session_state[period_key]:
            st.session_state[period_key] = selected_period
            st.rerun()

        current_period = st.session_state[period_key]

        # 根據 period 設定時間軸格式
        tick_map = {
            "1d": "%H:%M",
            "5d": "%m-%d",
            "1mo": "%m-%d",
            "3mo": "%m-%d",
            "6mo": "%Y-%m",
            "1y": "%Y-%m",
            "2y": "%Y-%m",
        }
        current_tick_format = tick_map.get(current_period, "%Y-%m")

        # 使用選定的 period 抓取數據
        df = dashboard_logic.fetch_historical_data(ticker, period=current_period)

        if df is None or df.empty:
            st.warning(f"⚠️ 無法取得 {ticker} 的歷史數據 ({current_period})")
            return

        # --- 強健處理 MultiIndex ---
        if isinstance(df.columns, pd.MultiIndex):
            # 嘗試 1: 如果第一層是 Ticker，選取它
            if ticker in df.columns.get_level_values(0):
                df = df.xs(ticker, axis=1, level=0)
            # 嘗試 2: 如果第二層是 Ticker
            elif ticker in df.columns.get_level_values(1):
                df = df.xs(ticker, axis=1, level=1)
            else:
                # 嘗試 3: 尋找包含 'Close' 的那一層
                for i in range(df.columns.nlevels):
                    if "Close" in df.columns.get_level_values(i):
                        df.columns = df.columns.get_level_values(i)
                        break

        # 確保 Close 欄位存在
        if "Close" not in df.columns:
            # 嘗試找尋 Adj Close
            if "Adj Close" in df.columns:
                df = df.rename(columns={"Adj Close": "Close"})
            else:
                # 嘗試模糊匹配
                cols_map = {str(c).lower().replace(" ", ""): c for c in df.columns}
                if "close" in cols_map:
                    df = df.rename(columns={cols_map["close"]: "Close"})
                else:
                    st.error(f"❌ 數據格式異常，缺少收盤價欄位: {df.columns.tolist()}")
                    return

        # 清洗數據
        df = df[df["Close"].notnull()].copy()
        if len(df) < (1 if current_period == "1d" else 5): # 1d 數據可能很少
            st.warning(f"⚠️ {ticker} 歷史數據量不足")
            return

        # 計算均線 (MA20, MA60)
        # 確保數據是 float
        df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
        df["MA20"] = df["Close"].rolling(window=20, min_periods=1).mean()
        df["MA60"] = df["Close"].rolling(window=60, min_periods=1).mean()

        # 繪圖
        fig = go.Figure()

        # MA60
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["MA60"],
                name="MA60",
                line=dict(color="rgba(0, 200, 83, 0.4)", width=1.2),
                hoverinfo="skip",
            )
        )

        # MA20
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["MA20"],
                name="MA20",
                line=dict(color="rgba(255, 75, 75, 0.5)", width=1.2),
                hoverinfo="skip",
            )
        )

        # 收盤價
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["Close"],
                name="收盤價",
                line=dict(color="#FFFFFF", width=2),
                hovertemplate="日期: %{x}<br>價格: %{y:.2f}<extra></extra>",
            )
        )

        fig.update_layout(
            height=250,
            margin=dict(l=10, r=10, t=30, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            hovermode="x unified",
            xaxis=dict(
                showgrid=True,
                gridcolor="rgba(255,255,255,0.05)",
                tickformat=current_tick_format,
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor="rgba(255,255,255,0.05)",
                side="right",
                tickformat=".1f",
            ),
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
                font=dict(size=10),
            ),
        )

        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    except Exception as e:
        st.error(f"📉 繪圖失敗 ({ticker}): {str(e)}")


def load_css():
    """載入外部 CSS 檔案樣式"""
    css_file = os.path.join(os.path.dirname(__file__), "style.css")
    if os.path.exists(css_file):
        with open(css_file, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def get_color_class(val):
    """獲取數值文字顏色 (紅漲綠跌)"""
    if val > 0:
        return "text-red"
    elif val < 0:
        return "text-green"
    return ""


def get_tag_class(val):
    """獲取漲跌標籤背景色 (紅漲綠跌)"""
    if isinstance(val, str):
        if "+" in val:
            return "bg-red-tag"
        elif "-" in val:
            # 排除只有 "-" 沒有數字的情況
            if val.strip() == "-":
                return "bg-grey-tag"
            return "bg-green-tag"
        return "bg-grey-tag"

    if val > 0:
        return "bg-red-tag"
    elif val < 0:
        return "bg-green-tag"
    return "bg-grey-tag"


def render_analysis_metrics_row(metrics_dict, title=None):
    """根據傳入的 dictionary 迴圈產生 analysis-metric-box DIV tag"""
    title_html = f'<div class="analysis-report-title">{title}</div>' if title else ""
    items_html = ""
    for label, value in metrics_dict.items():
        color_style = ""
        # 支援顯示特定顏色 (value, color)
        if isinstance(value, tuple) and len(value) == 2:
            display_val, color = value
            if color:
                color_style = f" style='color: {color};'"
        else:
            display_val = value

        items_html += (
            f'<div class="analysis-metric-box">'
            f'<div class="analysis-metric-value"{color_style}>{display_val}</div>'
            f'<div class="analysis-metric-label">{label}</div>'
            f"</div>"
        )
    return f'{title_html}<div class="analysis-metrics-flex">{items_html}</div>'


def render_tracking_metrics_row(items, title=None):
    """根據傳入的 list 迴圈產生 analysis-metric-box DIV tag"""
    title_html = f'<div class="analysis-report-title">{title}</div>' if title else ""
    items_html = ""

    for item in items:
        label = item.get("名稱", "")
        val = item.get("數值", 0)
        delta = item.get("漲跌幅", 0)
        items_html += (
            f'<div class="analysis-metric-box">'
            f"{render_horizontal_value_tag_component(val, delta)}"
            f'<div class="analysis-metric-label">{label}</div>'
            f"</div>"
        )
    # 移除換行以避免 Markdown 誤解析
    return f'{title_html}<div class="analysis-metrics-flex">{items_html}</div>'


def render_cost_component(row):
    cost_dic = {
        "單位數": row["單位數"],
        "平均成本": f"${row['平均成本']:,.2f}",
        "成本": f"${row['成本']:,}",
        "市值": f"${row['市值']:,}",
    }

    cost_row = render_analysis_metrics_row(cost_dic)  # , "💰 成本分析")

    st.markdown(
        f"""<div class="analysis-report-row">
                    <div class="analysis-report-col">
                    {cost_row}
                    </div>
                    </div>""",
        unsafe_allow_html=True,
    )


def render_advanced_analysis_ui(res):
    # 渲染股價走勢圖
    render_price_chart(res["代碼"])

    def get_anomaly_color(value, metric_type):
        if value is None or str(value).strip() in ["-", ""]:
            return ""

        try:
            val = float(str(value).replace("%", "").replace(",", ""))
        except ValueError:
            return ""

        thresholds = {
            "yield": lambda x: x > 20.0,  # 20% 以上標紅
            "vol_ratio": lambda x: x > 50,  # 量比過大標紅
            "pe": lambda x: x > 500 or x < 0,  # PE 異常
        }

        if metric_type == "bias":
            if val > 15:
                return "#FF4500"  # 橘紅色 (提醒技術面溢價)
            elif val < -10:
                return "#00FF00"  # 亮綠色 (跌深超賣折價)
            elif abs(val) > 50:
                return "#FF4B4B"  # 乖離過大標紅

        if metric_type in thresholds and thresholds[metric_type](val):
            return "#FF4B4B"  # 亮紅色

        return ""

    price_levels_dic = {
        "股價": res["股價"],
        "日常波段": res["日常波段"],
        "技術回測": res["技術回測"],
        "狙擊防守": res["狙擊位"],
    }
    ma_dic = {
        "MA20": res["MA20"],
        "MA60": res["MA60"],
        "MA120": res["MA120"],
        "MA250": res["MA250"],
    }

    fund_dic = {
        "EPS": res.get("EPS", "-"),
        "P/E": (f"{res['PE']:.1f}", get_anomaly_color(res["PE"], "pe")),
        "殖利率": (
            res.get("殖利率", "-"),
            get_anomaly_color(res.get("殖利率", "-"), "yield"),
        ),
        "PEG": res.get("PEG", "-"),
    }

    analyze_1_dic = {
        "量比": (res["量比"], get_anomaly_color(res["量比"], "vol_ratio")),
        "RS%": res["RS 百分位"],
        "RSI": f"{res.get('RSI', 0):.1f}",
        "Sharpe": res["夏普值"],
    }

    analyze_2_dic = {
        "α勝率": res["Alpha 勝率"],
        "月度α": res["月度 Alpha"],
        "Bias%": (
            res["乖離率 (Bias)"],
            get_anomaly_color(res["乖離率 (Bias)"], "bias"),
        ),
        "": "",
    }

    # 使用自定義 DIV 代替 st.columns，移除縮排以避免 Markdown 誤解析
    analysis_row_1 = render_analysis_metrics_row(price_levels_dic, "🎯 建議掛單位階")

    analysis_row_2 = render_analysis_metrics_row(ma_dic, "📊 均線參考")

    analysis_row_3 = render_analysis_metrics_row(fund_dic, "📊 財務與核心指標")

    analysis_row_4 = render_analysis_metrics_row(analyze_1_dic)

    analysis_row_5 = render_analysis_metrics_row(analyze_2_dic)

    """合併後的進階量化分析渲染組件"""
    if "tags" in res and res["tags"]:
        tag_html = "".join(
            [f'<span class="light_tags">{tag}</span>' for tag in res["tags"]]
        )
        st.markdown(
            f"<div class='tag-report-row'>{tag_html}</div>", unsafe_allow_html=True
        )
        st.info(f"{res['技術診斷']}")

    st.markdown(
        f"""<div class="analysis-report-row">
            <div class="analysis-report-col">
            {analysis_row_1}
            {analysis_row_2}
            </div>
            <div class="analysis-report-col">
            {analysis_row_3}
            {analysis_row_4}
            {analysis_row_5}
            </div>
            </div>""",
        unsafe_allow_html=True,
    )


def show_manual_analysis_page():
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
                if hasattr(dashboard_logic, "clear_ticker_cache"):
                    for c in codes:
                        dashboard_logic.clear_ticker_cache(c)
                adv_manual = dashboard_logic.run_advanced_analysis(manual_df)
                if not adv_manual.empty:
                    for _, res in adv_manual.iterrows():
                        with st.expander(
                            f"📈 {res['名稱']} ({res['代碼']}) 報告", expanded=True
                        ):
                            render_advanced_analysis_ui(res)


def render_title_component(title):
    st.markdown(f"<div class='section-title'>{title}</div>", unsafe_allow_html=True)


def render_horizontal_value_tag_component(value, tag):
    """橫向組件 -> 依照使用者要求改為 垂直排列 (Value above Tag)"""
    className_tag = get_tag_class(tag)

    # 處理 value 格式
    if isinstance(value, str):
        display_val = value
    else:
        # 如果是純數字則加上 $ 與正負號格式
        display_val = f"{value:+,.0f}" if value != 0 else f"{value:,.0f}"

    # 處理 tag 格式
    display_tag = f"{tag:+,.2f}%" if isinstance(tag, (int, float)) else str(tag)

    return f"""<div class='asset-value-container' style='align-items: center;'>
                <div class='asset-metric-value'>{display_val}</div>
                <div class='asset-change-tag {className_tag}' style='font-size: 0.75rem; margin-top: 2px;'>{display_tag}</div>
                </div>"""


def render_vertical_value_tag_component(value, tag):
    """縱向組件 -> 依照使用者要求改為 水平排列 (Value next to Tag)"""
    className_tag = get_tag_class(tag)

    # 處理 value 格式
    if isinstance(value, str):
        display_val = value
    else:
        # 股價通常不帶 $，且保留兩位小數
        display_val = f"{value:,.2f}"

    # 處理 tag 格式
    display_tag = f"{tag:+,.2f}%" if isinstance(tag, (int, float)) else str(tag)

    return f"""<div class='asset-value-row'>
                <span class='asset-price-main'>{display_val}</span>
                <span class='asset-change-tag {className_tag}'>{display_tag}</span>
                </div>"""


def render_profit_and_loss_component(df):
    # 顯示整合型卡片
    with st.container(border=True):
        col_total, col_market = st.columns([0.5, 0.5])
        with col_total:
            with st.container():
                # 計算總體數據
                total_pl = df["損益"].sum()
                total_cost = df["成本"].sum()
                roi = (total_pl / total_cost * 100) if total_cost != 0 else 0

                # value = f"${total_pl:+,.0f}"

                st.markdown(
                    f"""<div class='inline-metric-label'>💰 帳戶總損益</div>
                        <div class='total-pl-wrapper'>
                            <div class='inline-metric-row'>
                                <span class='inline-metric-value'>${df["市值"].sum():,}</span>
                            </div>
                            {render_vertical_value_tag_component(f"{total_pl:+,.0f}", roi)}
                        </div>
                    """,
                    unsafe_allow_html=True,
                )
        with col_market:
            with st.container(gap="xxsmall"):
                # 計算各市場損益明細
                market_stats = df.groupby("市場").agg({"損益": "sum", "成本": "sum"})
                market_stats = market_stats.sort_values("損益", ascending=False)

                market_items = []
                for m, row in market_stats.iterrows():
                    m_pl = row["損益"]
                    m_roi = (m_pl / row["成本"] * 100) if row["成本"] != 0 else 0
                    market_items.append({"名稱": m, "數值": m_pl, "漲跌幅": m_roi})

                # 3 個為一列顯示 (使用既有的 render_tracking_metrics_row)
                for i in range(0, len(market_items), 3):
                    st.markdown(
                        render_tracking_metrics_row(market_items[i : i + 3]),
                        unsafe_allow_html=True,
                    )


def render_vertical_component(indices):
    for i, item in enumerate(indices):
        # with st.container(border=True, gap="xxsmall"):
        render_inline_metric(
            item["名稱"], f"{item['數值']:,.2f}", f"{item['漲跌幅']:+.2f}%"
        )


def render_horizontal_component(major_rates):
    n_rate_cols = min(len(major_rates), 2) if major_rates else 1
    rate_cols = st.columns(n_rate_cols)
    for i, item in enumerate(major_rates):
        with rate_cols[i % n_rate_cols]:
            # with st.container(border=True, gap="xxsmall"):
            render_inline_metric(
                item["名稱"], f"{item['數值']:,.2f}", f"{item['漲跌幅']:+.2f}%"
            )


def render_dataframe_component(df):
    df_view = df.copy()
    numeric_cols = [
        "單位數",
        "平均成本",
        "股價",
        "漲跌",
        "市值",
        "損益",
        "報酬率",
        "佔比",
    ]
    for col in numeric_cols:
        if col in df_view.columns:
            df_view[col] = pd.to_numeric(df_view[col], errors="coerce").fillna(0.0)

    for col in ["代碼", "名稱", "市場"]:
        if col in df_view.columns:
            df_view[col] = df_view[col].astype(str)

    df_view["標的"] = df_view["代碼"]
    cols_display = [
        "市場",
        "標的",
        "股價",
        "漲跌",
        "損益",
        "報酬率",
        "單位數",
        "平均成本",
        "市值",
        "佔比",
    ]
    cols_to_use = [c for c in cols_display if c in df_view.columns]

    event = st.dataframe(
        df_view[cols_to_use]
        .style.format(
            {
                "單位數": "{:,.0f}",
                "平均成本": "{:,.2f}",
                "股價": "{:,.2f}",
                "漲跌": "{:+,.2f}",
                "市值": "${:,.0f}",
                "損益": "${:+,.0f}",
                "報酬率": "{:+.2f}%",
                "佔比": "{:.1f}%",
            },
            na_rep="0",
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
        column_config={
            "標的": st.column_config.TextColumn(
                "標的", help="顯示代碼 (點選可看完整名稱與分析)"
            )
        },
    )

    if event and event.selection and event.selection.rows:
        idx = event.selection.rows[0]
        selected_row = df.iloc[idx]
        title = f"🔍 {selected_row['名稱']} ({selected_row['代碼']}) 進階分析"
        render_title_component(title)
        with st.container(border=True):
            with st.spinner("分析中..."):
                adv_results = dashboard_logic.run_advanced_analysis(
                    pd.DataFrame([selected_row])
                )
                if not adv_results.empty:
                    render_advanced_analysis_ui(adv_results.iloc[0])


def render_shareholding_component(df):
    for idx, row in df.iterrows():
        with st.container(border=True):
            with st.container():
                c1, c2, c3, c4 = st.columns([0.65, 2.2, 1, 1])
                with c1:
                    st.markdown(
                        '<div class="asset-card-beacon" style="display:none;"></div>',
                        unsafe_allow_html=True,
                    )
                    if st.button(
                        "🔍",
                        key=f"btn_{row['代碼']}_{idx}",
                        help="點擊執行進階量化分析",
                    ):
                        # 切換顯示狀態 (Toggle)
                        state_key = f"analyze_{row['代碼']}"
                        st.session_state[state_key] = not st.session_state.get(
                            state_key, False
                        )
                        st.rerun()

                with c2:
                    update_time_str = (
                        f"⏳ {row.get('更新時間', '')} | "
                        if row.get("更新時間")
                        else ""
                    )
                    st.markdown(
                        f"""<div class='asset-info-container'>
                        <div class='asset-info-meta'>{update_time_str}{row["市場"]} | {row["代碼"]} ({row["佔比"]:.1f}%) </div>
                        <div class='asset-info-name'>{row["名稱"]} </div>
                        </div>""",
                        unsafe_allow_html=True,
                    )

                with c3:
                    price, change = row["股價"], row["漲跌"]
                    change_val = (
                        float(change) if pd.notnull(change) and change != "-" else 0.0
                    )
                    st.markdown(
                        f"""<div class='asset-value-container'>
                        <div class='asset-value-label'>現價 / 漲跌</div>
                        {render_vertical_value_tag_component(price, change_val)}
                        </div>""",
                        unsafe_allow_html=True,
                    )

                with c4:
                    pl, roi = row["損益"], row["報酬率"]
                    # 也將損益（c4）改為調用 render_vertical_value_tag_component 以維持視覺一致性（水平排列）
                    st.markdown(
                        f"""<div class='asset-value-container'>
                        <div class='asset-value-label'>損益 / 報酬</div>
                        {render_vertical_value_tag_component(f"{pl:+,.0f}", roi)}
                        </div>""",
                        unsafe_allow_html=True,
                    )

            if st.session_state.get(f"analyze_{row['代碼']}", False):
                ticker = row["代碼"]
                # render_title_component(f"📈 {row['名稱']} ({ticker}) 深度量化診斷")
                # with st.container(border=True):
                render_cost_component(row)
                if hasattr(dashboard_logic, "clear_ticker_cache"):
                    dashboard_logic.clear_ticker_cache(ticker)

                with st.spinner("正在進行深度數據穿透..."):
                    adv_results = dashboard_logic.run_advanced_analysis(
                        pd.DataFrame([row])
                    )
                    if not adv_results.empty:
                        with st.container():
                            render_advanced_analysis_ui(adv_results.iloc[0])


def render_plotly_pie_charts(df):
    import plotly.express as px

    market_df = df.groupby("市場")["市值"].sum().reset_index()
    fig_market = px.pie(
        market_df,
        values="市值",
        names="市場",
        title="資產分析-市場別",
        color_discrete_sequence=px.colors.qualitative.Pastel,
    )
    fig_market.update_layout(
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.5, xanchor="center", x=0.5),
        margin=dict(t=40, b=80, l=0, r=0),
        height=300,
    )
    with st.container(border=True):
        st.plotly_chart(fig_market, width="stretch")

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
        legend=dict(orientation="h", yanchor="bottom", y=-0.5, xanchor="center", x=0.5),
        margin=dict(t=40, b=80, l=0, r=0),
        height=480,
    )
    with st.container(border=True):
        st.plotly_chart(fig_item, width="stretch")


def render_inline_metric(label, value, delta):

    with st.container(border=True, gap="xxsmall"):
        st.markdown(
            f"""<div class='inline-metric-container'>
                <div class='inline-metric-label'>{label}</div>
                {render_horizontal_value_tag_component(value, delta)}
            </div>""",
            unsafe_allow_html=True,
        )


def render_asset_filter(df):
    """資產篩選器組件，返回過濾後的 DataFrame"""
    with st.expander("🔍 資產篩選器", expanded=False):
        c1, c2 = st.columns(2)

        # 獲取選項 (確保存在該欄位)
        market_options = (
            sorted(df["市場"].dropna().unique().tolist())
            if "市場" in df.columns
            else []
        )
        type_options = (
            sorted(df["類型"].dropna().unique().tolist())
            if "類型" in df.columns
            else []
        )

        with c1:
            selected_markets = st.multiselect(
                "選擇市場", options=market_options, default=market_options
            )
        with c2:
            selected_types = st.multiselect(
                "選擇類型", options=type_options, default=type_options
            )

    # 進行資料過濾
    filtered_df = df.copy()
    if "市場" in filtered_df.columns and selected_markets is not None:
        filtered_df = filtered_df[filtered_df["市場"].isin(selected_markets)]
    if "類型" in filtered_df.columns and selected_types is not None:
        filtered_df = filtered_df[filtered_df["類型"].isin(selected_types)]

    return filtered_df


def show_streamlit(df, radar_data, exchange_rates):
    load_css()

    col_mid, col_right = st.columns([1.3, 0.7])
    with col_mid:
        with st.container(border=False):
            # 篩選器
            filtered_df = render_asset_filter(df)
            # 總損益
            render_profit_and_loss_component(filtered_df)
        with st.container(border=False):
            # 持股明細
            render_shareholding_component(filtered_df)
    with col_right:
        with st.container(border=False):
            # with st.expander("🔍 指數", expanded=False):
            # 指數
            indices = [item for item in radar_data]
            for i in range(0, len(indices), 3):
                st.markdown(
                    render_tracking_metrics_row(indices[i : i + 3]),
                    unsafe_allow_html=True,
                )
        with st.container(border=False, gap="xxsmall"):
            # 圓餅圖
            if not filtered_df.empty:
                render_plotly_pie_charts(filtered_df)
            else:
                st.info("無符合條件的資產可供分析")
