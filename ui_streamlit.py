# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import os
import dashboard_logic
import ui_common


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
        items_html += (
            f'<div class="analysis-metric-box">'
            f'<div class="analysis-metric-value">{value}</div>'
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


def render_advanced_analysis_ui(res):

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

    fund_dic = {"EPS": res["EPS"], "P/E": f"{res['PE']:.1f}", "量比": res["量比"]}

    analyze_1_dic = {
        "RS%": res["RS 百分位"],
        "RSI": f"{res.get('RSI', 0):.1f}",
        "Sharpe": res["夏普值"],
    }

    analyze_2_dic = {
        "α勝率": res["Alpha 勝率"],
        "月度α": res["月度 Alpha"],
        "Bias%": res["乖離率 (Bias)"],
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
                c1, c2, c3, c4 = st.columns([0.65, 2.5, 2.2, 2.2])
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
                        st.session_state[f"analyze_{row['代碼']}"] = True

                with c2:
                    st.markdown(
                        f"""<div class='asset-info-container'>
                        <div class='asset-info-meta'>{row["市場"]} | {row["代碼"]} ({row["佔比"]:.1f}%)</div>
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
                if hasattr(dashboard_logic, "clear_ticker_cache"):
                    dashboard_logic.clear_ticker_cache(ticker)
                with st.spinner("正在進行深度數據穿透..."):
                    adv_results = dashboard_logic.run_advanced_analysis(
                        pd.DataFrame([row])
                    )
                    if not adv_results.empty:
                        with st.container():
                            # with st.expander(
                            #     f"📈 {row['名稱']} ({row['代碼']}) 報告", expanded=True
                            # ):
                            render_advanced_analysis_ui(adv_results.iloc[0])
                # if st.button("收合報告", key=f"close_{row['代碼']}"):
                #     st.session_state[f"analyze_{row['代碼']}"] = False
                #     st.rerun()


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


def show_streamlit(df, radar_data, exchange_rates):
    load_css()
    # col_left, col_mid, col_right = st.columns([0.5, 1.2, 0.5])
    col_mid, col_right = st.columns([1.6, 0.5])
    # with col_left:
    # with st.container(border=False):
    # with st.container(border=False):
    # indices = [item for item in radar_data if not item["代碼"].endswith("=X")]

    with col_mid:
        with st.container(border=False):
            # 總損益
            render_profit_and_loss_component(df)
        with st.container(border=False):
            # 持股明細
            render_shareholding_component(df)
    with col_right:
        with st.container(border=False):
            # 指數
            indices = [item for item in radar_data]
            for i in range(0, len(indices), 3):
                st.markdown(
                    render_tracking_metrics_row(indices[i : i + 3]),
                    unsafe_allow_html=True,
                )
        with st.container(border=False, gap="xxsmall"):
            # 圓餅圖
            render_plotly_pie_charts(df)
