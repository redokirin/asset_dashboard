# -*- coding: utf-8 -*-
import pandas as pd
import streamlit as st

from core import dashboard_logic
from core.columns import (
    COL_CURRENCY,
    COL_MARKET_VALUE,
    COL_NAME,
    COL_SETTLEMENT,
    COL_TICKER,
    COL_UNITS,
    COL_WEIGHT,
)
from ui.streamlit.advanced_analysis import render_advanced_analysis_ui
from ui.streamlit.components import (
    render_cost_component,
    render_title_component,
    render_tracking_metrics_row,
    render_vertical_value_tag_component,
)


CASH_MARKETS = {"bank", "cash", "現金"}


def _cash_mask(df):
    if "市場" not in df.columns:
        return pd.Series(False, index=df.index)
    market_names = df["市場"].astype(str).str.strip().str.lower()
    return market_names.isin(CASH_MARKETS)


def render_profit_and_loss_component(df, radar_data):
    cash_mask = _cash_mask(df)
    investment_df = df[~cash_mask]

    with st.container():
        total_pl = investment_df["損益"].sum()
        total_cost = investment_df["成本"].sum()
        roi = (total_pl / total_cost * 100) if total_cost != 0 else 0

        st.markdown(
            f"""<div class='inline-metric-label'>💰 投資資產</div>
                <div class='total-pl-wrapper'>
                    <div class='inline-metric-row'>
                        <span class='inline-metric-value'>${df["市值"].sum():,}</span>
                    </div>
                    {render_vertical_value_tag_component(f"{total_pl:+,.0f}", roi)}
                </div>
            """,
            unsafe_allow_html=True,
        )
        render_liquidity_component(df)

    # with st.container(border=True):
    #     col_market, col_total = st.columns([0.5, 0.5])
    #     with col_market:
    with st.container(border=True, gap="xxsmall"):
        market_stats = investment_df.groupby("市場").agg({"損益": "sum", "成本": "sum"})
        market_stats = market_stats.sort_values("損益", ascending=False)

        market_items = []
        for market, row in market_stats.iterrows():
            market_pl = row["損益"]
            market_roi = market_pl / row["成本"] * 100 if row["成本"] != 0 else 0
            market_items.append(
                {"名稱": market, "數值": market_pl, "漲跌幅": market_roi}
            )

        for i in range(0, len(market_items), 4):
            st.markdown(
                render_tracking_metrics_row(market_items[i : i + 4]),
                unsafe_allow_html=True,
            )
        indices = [item for item in radar_data]
        for i in range(0, len(indices), 3):
            st.markdown(
                render_tracking_metrics_row(indices[i : i + 3]),
                unsafe_allow_html=True,
            )
    # with col_total:


def _settlement_values(frame):
    if COL_SETTLEMENT not in frame.columns:
        return pd.Series("", index=frame.index)
    return frame[COL_SETTLEMENT].fillna("").astype(str).str.strip()


def render_liquidity_component(df):
    if COL_MARKET_VALUE not in df.columns:
        return

    total_value = df[COL_MARKET_VALUE].sum()
    if total_value == 0:
        return

    cash_mask = _cash_mask(df)
    cash_df = df[cash_mask].copy()
    investment_df = df[~cash_mask].copy()
    settlement_values = _settlement_values(investment_df)

    bank_rows = {
        str(row[COL_TICKER]).strip(): row
        for _, row in cash_df.iterrows()
        if str(row.get(COL_TICKER, "")).strip()
    }
    settlement_keys = [key for key in settlement_values.unique() if key]
    group_keys = list(bank_rows.keys())
    group_keys.extend(key for key in settlement_keys if key not in bank_rows)
    if settlement_values.eq("").any():
        group_keys.append("")

    with st.container(border=True):
        bar_palettes = [
            ("#4f8cff", "#f5c542"),
            ("#00a878", "#ff8a3d"),
            ("#8b5cf6", "#f472b6"),
            ("#14b8a6", "#eab308"),
        ]
        for idx, bank_key in enumerate(group_keys):
            investment_color, cash_color = bar_palettes[idx % len(bar_palettes)]
            if bank_key:
                bank_row = bank_rows.get(bank_key)
                bank_name = (
                    str(bank_row.get(COL_NAME, bank_key))
                    if bank_row is not None
                    else bank_key
                )
                title = f"{bank_name}"  # ({bank_key})"
                matched_investments = investment_df[settlement_values == bank_key]
                matched_cash = cash_df[
                    cash_df[COL_TICKER].fillna("").astype(str).str.strip() == bank_key
                ]
            else:
                title = "未指定交割銀行"
                matched_investments = investment_df[settlement_values == ""]
                matched_cash = cash_df.iloc[0:0]

            investment_value = matched_investments[COL_MARKET_VALUE].sum()
            cash_value = matched_cash[COL_MARKET_VALUE].sum()
            bank_total = investment_value + cash_value
            if bank_total == 0:
                continue

            investment_pct = investment_value / bank_total * 100
            cash_pct = cash_value / bank_total * 100

            st.markdown(
                f"""
                <div style="padding-left: 0.5rem;padding-right: 0.5rem;">
                <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:10px; margin-top:6px;">
                        <div>
                            <div class="asset-value-label">投資
                            <span class="asset-price-main">${investment_value:,.0f}</span>
                            ({investment_pct:.1f}%)
                            </div>
                        </div>
                        <div class="asset-price-main" style="text-align: center;">{title}</div>
                        <div style="text-align: right;">
                            <div class="asset-value-label">現金
                            <span class="asset-price-main">${cash_value:,.0f}</span>
                            ({cash_pct:.1f}%)
                            </div>
                        </div>
                    </div>
                    <div style="display:flex; height:16px; width:100%; overflow:hidden; border-radius:6px; background:rgba(255,255,255,0.08);">
                        <div title="投資 {investment_pct:.1f}%" style="width:{investment_pct:.4f}%; background:{investment_color};"></div>
                        <div title="現金 {cash_pct:.1f}%" style="width:{cash_pct:.4f}%; background:{cash_color};"></div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # if not cash_df.empty:
        #     with st.expander("銀行現金明細", expanded=False):
        #         cash_df = cash_df.sort_values(COL_MARKET_VALUE, ascending=False)
        #         cash_df["餘額"] = cash_df[COL_UNITS]
        #         view_df = cash_df[
        #             [
        #                 COL_NAME,
        #                 COL_TICKER,
        #                 COL_CURRENCY,
        #                 "餘額",
        #                 COL_MARKET_VALUE,
        #                 COL_WEIGHT,
        #             ]
        #         ]
        #         st.dataframe(
        #             view_df.style.format(
        #                 {
        #                     "餘額": "{:,.0f}",
        #                     COL_MARKET_VALUE: "${:,.0f}",
        #                     COL_WEIGHT: "{:.1f}%",
        #                 },
        #                 na_rep="0",
        #             ),
        #             width="stretch",
        #             hide_index=True,
        #         )


# def render_liquidity_component(df):
#     return _render_liquidity_by_bank(df)


def render_cash_component(df):
    render_liquidity_component(df)


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
    cols_to_use = [col for col in cols_display if col in df_view.columns]

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
    investment_df = df[~_cash_mask(df)]

    for idx, row in investment_df.iterrows():
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
                    st.markdown(
                        f"""<div class='asset-value-container'>
                        <div class='asset-value-label'>損益 / 報酬</div>
                        {render_vertical_value_tag_component(f"{pl:+,.0f}", roi)}
                        </div>""",
                        unsafe_allow_html=True,
                    )

            if st.session_state.get(f"analyze_{row['代碼']}", False):
                ticker = row["代碼"]

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
