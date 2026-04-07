import numpy as np
import pandas as pd
import yfinance as yf
import streamlit as st
from scipy import stats
from dashboard_logic import ASSETS


@st.cache_data(ttl=3600)  # 每小時更新一次數據
def get_rs_percentile_rank(tickers_list, benchmark="0050.TW"):
    """
    計算所有標的相對於 benchmark 的 RS 百分位數
    """
    results = []
    # 預先下載 Benchmark 與匯率數據以節省時間
    common_tickers = [benchmark, "JPYTWD=X", "USDTWD=X"]
    common_data = yf.download(common_tickers, period="2y", progress=False)["Close"]

    for ticker in tickers_list:
        try:
            # 1. 抓取標的數據
            data = yf.download(ticker, period="2y", progress=False)["Close"]
            if data.empty:
                continue

            # 2. 自動判斷幣別與匯率 (使用之前優化的邏輯)
            ccy = (
                "JPY"
                if ticker.endswith(".T")
                else "TWD"
                if ticker.endswith(".TW")
                else "USD"
            )
            rate = (
                common_data["JPYTWD=X"]
                if ccy == "JPY"
                else common_data["USDTWD=X"]
                if ccy == "USD"
                else 1.0
            )

            # 3. 計算 RS 系列
            rs_series = (data * rate) / common_data[benchmark]
            rs_series = rs_series.dropna()

            if len(rs_series) < 20:
                continue

            # 4. 計算百分位數排名 (Percentile Rank)
            current_rs = rs_series.iloc[-1]
            percentile = stats.percentileofscore(rs_series, current_rs)

            results.append(
                {
                    "代碼": ticker,
                    "當前 RS": round(current_rs, 4),
                    "RS 百分位數": f"{percentile:.1f}%",
                    "狀態": "🔵 深水區"
                    if percentile <= 20
                    else "🔥 大掃把"
                    if percentile <= 10
                    else "⚪ 正常",
                    "score": percentile,  # 用於排序
                }
            )
        except:
            continue

    return pd.DataFrame(results).sort_values("score")


# --- 在 Streamlit UI 顯示 ---
def show_rs_ranking_table():
    st.subheader("📊 跨市場 RS 強度排行榜 (相對於 0050)")

    # 從 ASSETS 取得所有已啟動的標的代碼
    all_tickers = []
    for category in ASSETS.values():
        for item in category.values():
            if item.get("get_value") and item.get("id"):
                all_tickers.append(item["id"])

    if st.button("🔄 更新 RS 排名數據"):
        st.cache_data.clear()

    with st.spinner("正在掃描全球市場偏差值..."):
        df_rs = get_rs_percentile_rank(list(set(all_tickers)))

    # 顯示表格
    df_display = df_rs.drop(columns=["score"]).copy()
    if "代碼" in df_display.columns:
        df_display["代碼"] = df_display["代碼"].astype(str)

    st.dataframe(
        df_display,
        column_config={
            "RS 百分位數": st.column_config.ProgressColumn(
                "RS 強度位置",
                help="越低代表相對於台股越便宜",
                format="%f",
                min_value=0,
                max_value=100,
            )
        },
        width="stretch",
    )
