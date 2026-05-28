# -*- coding: utf-8 -*-
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import dashboard_logic


CASH_MARKETS = {"cash", "現金"}


def _investment_df(df):
    if "市場" not in df.columns:
        return df
    market_names = df["市場"].astype(str).str.strip().str.lower()
    return df[~market_names.isin(CASH_MARKETS)]


def render_price_chart(ticker):
    """渲染股價折線圖與均線"""
    try:
        period_key = f"chart_period_{ticker}"
        if period_key not in st.session_state:
            st.session_state[period_key] = "6mo"

        periods = ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y"]

        c1, c2 = st.columns([0.3, 0.7])
        with c1:
            st.markdown(
                "<div style='padding-top: 5px; font-size: 0.8rem; color: #888;'>📅 走勢區間</div>",
                unsafe_allow_html=True,
            )
        with c2:
            selected_period = st.segmented_control(
                "選擇區間",
                options=periods,
                default=st.session_state[period_key],
                key=f"selector_{ticker}",
                label_visibility="collapsed",
            )

        if selected_period and selected_period != st.session_state[period_key]:
            st.session_state[period_key] = selected_period
            st.rerun()

        current_period = st.session_state[period_key]
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

        df = dashboard_logic.fetch_historical_data(ticker, period=current_period)

        if df is None or df.empty:
            st.warning(f"⚠️ 無法取得 {ticker} 的歷史數據 ({current_period})")
            return

        if isinstance(df.columns, pd.MultiIndex):
            if ticker in df.columns.get_level_values(0):
                df = df.xs(ticker, axis=1, level=0)
            elif ticker in df.columns.get_level_values(1):
                df = df.xs(ticker, axis=1, level=1)
            else:
                for i in range(df.columns.nlevels):
                    if "Close" in df.columns.get_level_values(i):
                        df.columns = df.columns.get_level_values(i)
                        break

        if "Close" not in df.columns:
            if "Adj Close" in df.columns:
                df = df.rename(columns={"Adj Close": "Close"})
            else:
                cols_map = {str(c).lower().replace(" ", ""): c for c in df.columns}
                if "close" in cols_map:
                    df = df.rename(columns={cols_map["close"]: "Close"})
                else:
                    st.error(f"❌ 數據格式異常，缺少收盤價欄位: {df.columns.tolist()}")
                    return

        df = df[df["Close"].notnull()].copy()
        if len(df) < (1 if current_period == "1d" else 5):
            st.warning(f"⚠️ {ticker} 歷史數據量不足")
            return

        df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
        df["MA20"] = df["Close"].rolling(window=20, min_periods=1).mean()
        df["MA60"] = df["Close"].rolling(window=60, min_periods=1).mean()

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["MA60"],
                name="MA60",
                line=dict(color="rgba(0, 200, 83, 0.4)", width=1.2),
                hoverinfo="skip",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["MA20"],
                name="MA20",
                line=dict(color="rgba(255, 75, 75, 0.5)", width=1.2),
                hoverinfo="skip",
            )
        )
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


def render_plotly_pie_charts(df):
    import plotly.express as px

    df = _investment_df(df)
    if df.empty:
        st.info("無投資標的可供分析")
        return

    market_colors = {
        "美股": px.colors.sequential.Tealgrn,
        "台股": px.colors.sequential.Sunset,
        "日股": px.colors.sequential.Peach,
    }
    default_colors = px.colors.sequential.Greys

    market_df = df.groupby("市場")["市值"].sum().reset_index()
    market_color_map = {}
    for market in market_df["市場"]:
        color_scale = market_colors.get(market, default_colors)
        safe_colors = (
            color_scale[2:][::-1] if len(color_scale) > 2 else color_scale[::-1]
        )
        market_color_map[market] = safe_colors[0] if safe_colors else "#808080"

    fig_market = px.pie(
        market_df,
        values="市值",
        names="市場",
        title="投資分析-市場別",
        color="市場",
        hole=0.5,
        color_discrete_map=market_color_map,
    )
    fig_market.update_layout(
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.5, xanchor="center", x=0.5),
        margin=dict(t=40, b=80, l=0, r=0),
        height=400,
    )
    with st.container(border=True):
        st.plotly_chart(fig_market, width="stretch")

    item_df = df.copy()
    item_df["顯示名稱"] = (
        item_df["名稱"].astype(str).str.replace(r"[🏆🚩]", "", regex=True)
    )
    item_df = item_df.groupby(["市場", "顯示名稱"], as_index=False)["市值"].sum()
    item_df = item_df.sort_values(by=["市場", "市值"], ascending=[True, False])

    colors_seq = []
    market_indices = {}
    for market in item_df["市場"]:
        if market not in market_indices:
            market_indices[market] = 0

        color_scale = market_colors.get(market, default_colors)
        safe_colors = (
            color_scale[2:][::-1] if len(color_scale) > 2 else color_scale[::-1]
        )

        idx = market_indices[market]
        colors_seq.append(safe_colors[idx % len(safe_colors)])
        market_indices[market] += 1

    fig_item = px.pie(
        item_df,
        values="市值",
        names="顯示名稱",
        title="投資分析-項目別",
        hole=0.5,
        color_discrete_sequence=colors_seq,
    )
    fig_item.update_traces(sort=False)
    fig_item.update_layout(
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.5, xanchor="center", x=0.5),
        margin=dict(t=40, b=80, l=0, r=0),
        height=400,
    )
    with st.container(border=True):
        st.plotly_chart(fig_item, width="stretch")
