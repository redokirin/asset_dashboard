# -*- coding: utf-8 -*-
"""Compatibility facade and Streamlit page composition."""

import streamlit as st

from core import dashboard_logic
from ui.streamlit.advanced_analysis import (
    render_advanced_analysis_ui,
    show_manual_analysis_page,
)
from ui.streamlit.charts import render_plotly_pie_charts, render_price_chart
from ui.streamlit.components import (
    get_color_class,
    get_tag_class,
    load_css,
    render_analysis_metrics_row,
    render_cost_component,
    render_horizontal_component,
    render_horizontal_value_tag_component,
    render_inline_metric,
    render_title_component,
    render_tracking_metrics_row,
    render_vertical_component,
    render_vertical_value_tag_component,
)
from ui.streamlit.filters import render_asset_filter
from ui.streamlit.portfolio import (
    render_dataframe_component,
    render_cash_component,
    render_liquidity_component,
    render_market_card,
    render_profit_and_loss_component,
    render_schedule_of_assets,
    render_shareholding_component,
)


def _split_cash_and_investments(df):
    if "市場" not in df.columns:
        return df, df.iloc[0:0]
    market_names = df["市場"].astype(str).str.strip().str.lower()
    cash_mask = market_names.isin({"cash", "現金"})
    return df[~cash_mask], df[cash_mask]


def show_streamlit(df, radar_data, exchange_rates):
    load_css()

    col_mid, col_right = st.columns([0.7, 1.3])
    with col_mid:
        summary_container = st.container(border=False)
        filter_container = st.container(border=False)

        with filter_container:
            filtered_df = render_asset_filter(df)
        investment_df, _ = _split_cash_and_investments(filtered_df)

        with summary_container:
            render_schedule_of_assets(filtered_df, investment_df)

        render_liquidity_component(filtered_df)
        render_market_card(investment_df, radar_data)

        with st.container(border=False, gap="xxsmall"):
            if not investment_df.empty:
                render_plotly_pie_charts(investment_df)
            else:
                st.info("無符合條件的資產可供分析")

        with st.container(border=False):
            if st.button("📋 產生 AI 分析報告", use_container_width=True):
                with st.spinner("正在產生完整 AI 分析報告..."):
                    from core import exporters
                    adv_res = dashboard_logic.run_advanced_analysis(df)
                    st.session_state["ai_report"] = exporters.export_for_ai(df, adv_res)

            if "ai_report" in st.session_state:
                from datetime import date
                st.download_button(
                    label="⬇️ 下載 AI 報告 (.md)",
                    data=st.session_state["ai_report"],
                    file_name=f"ai_report_{date.today().strftime('%Y%m%d')}.md",
                    mime="text/markdown",
                    use_container_width=True,
                )

    with col_right:
        with st.container(border=False):
            render_shareholding_component(investment_df)
