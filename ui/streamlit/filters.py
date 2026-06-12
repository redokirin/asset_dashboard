# -*- coding: utf-8 -*-
import streamlit as st


def render_asset_filter(df):
    """資產篩選器組件，返回過濾後的 DataFrame"""
    with st.expander("🔍 資產篩選", expanded=False):
        c1, c2 = st.columns(2)

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

    filtered_df = df.copy()
    if "市場" in filtered_df.columns and selected_markets is not None:
        filtered_df = filtered_df[filtered_df["市場"].isin(selected_markets)]
    if "類型" in filtered_df.columns and selected_types is not None:
        filtered_df = filtered_df[filtered_df["類型"].isin(selected_types)]

    return filtered_df
