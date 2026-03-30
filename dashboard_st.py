import streamlit as st
import pandas as pd
import yfinance as yf
import dashboard_logic
from dashboard_ui import show_streamlit

# --- 1. Streamlit 頁面初步設定 (必須是第一個 st 指令) ---
st.set_page_config(page_title="全球資產看板", layout="wide")

# --- 2. 注入受 Streamlit 管理的快取抓取器 ---
@st.cache_data(ttl=3600)
def streamlit_historical_fetcher(tickers, period="2y", group_by="ticker"):
    return yf.download(list(tickers), period=period, progress=False, group_by=group_by)

@st.cache_data(ttl=3600)
def streamlit_common_fetcher(tickers, period="2y"):
    return yf.download(list(tickers), period=period, progress=False)

# 替換邏輯層中的抓取器
dashboard_logic.FETCHERS["historical"] = streamlit_historical_fetcher
dashboard_logic.FETCHERS["common"] = streamlit_common_fetcher

# --- 3. 執行主程式邏輯 ---
if __name__ == "__main__":
    # 解析任何必要的選項 (目前 ST 模式主要使用預設顯示)
    radar = dashboard_logic.get_market_radar_data()
    exchange_rates = dashboard_logic.exchange_rate(radar)
    df_res, market_share_data = dashboard_logic.calculate_assets_data(exchange_rates)
    
    # 渲染介面
    show_streamlit(df_res, radar)
