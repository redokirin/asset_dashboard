import streamlit as st
import pandas as pd
import yfinance as yf
import dashboard_logic
from dashboard_ui import show_streamlit
from dashboard_logic import get_config

# --- 讀取配置 ---
_config = get_config()
APP_PASSWORD = _config.get("app_password", "")
USE_PASSWORD = _config.get("use_password", False)

# --- 1. Streamlit 頁面初步設定 (必須是第一個 st 指令) ---
st.set_page_config(page_title="全球資產看板", layout="wide")


def login_form():
    """顯示登入介面"""
    if not USE_PASSWORD:
        st.session_state["is_authenticated"] = True
        st.rerun()
        return

    st.title("🔐 財務數據存取驗證")
    st.info("「全球資產即時監控」包含敏感財務資訊，請輸入密碼以繼續。")

    with st.form("login_form"):
        pwd = st.text_input("輸入密碼", type="password")
        submit = st.form_submit_button(label="解鎖看板")
        if submit:
            if pwd == APP_PASSWORD:
                st.session_state["is_authenticated"] = True
                st.rerun()
            else:
                st.error("密碼錯誤，請再試一次。")

    # if st.sidebar.button("🧪 先去手動分析頁面"):
    #     st.session_state.page = "manual"
    #     st.rerun()


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
    if "is_authenticated" not in st.session_state:
        # 如果不使用密碼，預設為已驗證
        st.session_state.is_authenticated = not USE_PASSWORD

    # 使用 st.tabs 進行分頁導覽
    tab_manual, tab_dashboard = st.tabs(["🧪 自選代碼量化分析", "📈 全球資產即時監控"])

    with tab_manual:
        from dashboard_ui import show_manual_analysis_page

        show_manual_analysis_page()

    with tab_dashboard:
        if not st.session_state.is_authenticated:
            login_form()
        else:
            radar = dashboard_logic.get_market_radar_data()
            exchange_rates = dashboard_logic.exchange_rate(radar)
            df_res, market_share_data = dashboard_logic.calculate_assets_data(
                exchange_rates
            )

            # 渲染主儀表板
            show_streamlit(df_res, radar, exchange_rates)
