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
def fetch_single_ticker_historical_flat(ticker, period="2y"):
    """單獨抓取並快取單一標的的歷史數據 (單層索引)"""
    # 傳入字串 ticker (不帶 list) 以確保返回單層 Index
    df = yf.download(ticker, period=period, progress=False, auto_adjust=True)
    # 強制轉換索引為無時區的 DatetimeIndex
    if not df.empty:
        df.index = pd.to_datetime(df.index)
        if hasattr(df.index, "tz") and df.index.tz is not None:
            df.index = df.index.tz_localize(None)
    return df


@st.cache_data(ttl=3600)
def fetch_single_ticker_common_flat(ticker, period="2y"):
    """單獨抓取並快取單一標的的共用數據 (單層索引)"""
    df = yf.download(
        ticker,
        period=period,
        progress=False,
        auto_adjust=True,
    )
    if not df.empty:
        df.index = pd.to_datetime(df.index)
        if hasattr(df.index, "tz") and df.index.tz is not None:
            df.index = df.index.tz_localize(None)
    return df


def streamlit_historical_fetcher(tickers, period="2y", group_by="ticker"):
    """封裝層：將單層快取數據組合成 MultiIndex 結構"""
    if isinstance(tickers, str):
        return fetch_single_ticker_historical_flat(tickers, period)

    ticker_list = list(tickers)
    dfs = []
    for t in ticker_list:
        df = fetch_single_ticker_historical_flat(t, period)
        if not df.empty:
            # 在快取之外手動建立 MultiIndex
            df_m = df.copy()
            if isinstance(df_m.columns, pd.MultiIndex):
                # 如果已經是 MultiIndex (yfinance 0.2.40+)，先降維再接起來
                df_m.columns = df_m.columns.get_level_values(0)
            df_m.columns = pd.MultiIndex.from_product([[t], df_m.columns])
            dfs.append(df_m)

    if not dfs:
        return pd.DataFrame()
    return pd.concat(dfs, axis=1)


def streamlit_common_fetcher(tickers, period="2y"):
    """封裝層：將單層快取數據組合"""
    if isinstance(tickers, str):
        return fetch_single_ticker_common_flat(tickers, period)

    ticker_list = list(tickers)
    dfs = []
    for t in ticker_list:
        df = fetch_single_ticker_common_flat(t, period)
        if not df.empty:
            df_m = df.copy()
            if isinstance(df_m.columns, pd.MultiIndex):
                df_m.columns = df_m.columns.get_level_values(0)
            df_m.columns = pd.MultiIndex.from_product([[t], df_m.columns])
            dfs.append(df_m)

    if not dfs:
        return pd.DataFrame()

    if len(dfs) == 1:
        res = dfs[0].copy()
        res.columns = res.columns.get_level_values(1)
        return res

    return pd.concat(dfs, axis=1)


# 替換邏輯層中的抓取器
dashboard_logic.FETCHERS["historical"] = streamlit_historical_fetcher
dashboard_logic.FETCHERS["common"] = streamlit_common_fetcher


def clear_ticker_cache(ticker):
    """清除特定 Ticker 的快取，確保重新抓取最新數據"""
    # 清除不同 period 的快取 (與業務邏輯中使用的參數一致)
    fetch_single_ticker_historical_flat.clear(ticker, period="2y")
    fetch_single_ticker_historical_flat.clear(ticker, period="1mo")
    # fetch_single_ticker_common_flat.clear(ticker, period="2y")


# 注入清除快取的函式到邏輯層，供 UI 層調用
dashboard_logic.clear_ticker_cache = clear_ticker_cache

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
