import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import platform
import sys
import math

try:
    from rich.console import Console

    HAS_RICH = True
except ImportError:
    HAS_RICH = False


# --- 環境偵測 ---
def get_env():
    if "streamlit" in sys.modules or "streamlit.runtime" in sys.modules:
        return "streamlit"
    try:
        from IPython.core.getipython import get_ipython

        if get_ipython().__class__.__name__ == "ZMQInteractiveShell":
            return "jupyter"
    except Exception:
        pass
    return "console"


CURRENT_ENV = get_env()


def set_chinese_font():
    system = platform.system()
    if system == "Darwin":
        plt.rcParams["font.sans-serif"] = ["Arial Unicode MS"]
    elif system == "Windows":
        plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei"]
    plt.rcParams["axes.unicode_minus"] = False


def plot_rs_analysis(ticker_a="1306.T", ticker_b="0050.TW", period="1y"):
    """
    計算並繪製 A 相對於 B 的相對強度指標 (RS)
    """
    try:
        # 1. 抓取歷史數據
        df_a = yf.download(ticker_a, period=period, progress=False)
        df_b = yf.download(ticker_b, period=period, progress=False)
        df_rate = yf.download("JPYTWD=X", period=period, progress=False)

        close_col = "Close"

        # Safely extract Series, returning empty Series if data is missing
        data_a_series = pd.Series(dtype="float64")
        if not df_a.empty and close_col in df_a.columns:
            data_a_series = df_a[close_col]
        else:
            print(f"⚠️ 無法取得 {ticker_a} 的 {close_col} 數據。")

        data_b_series = pd.Series(dtype="float64")
        if not df_b.empty and close_col in df_b.columns:
            data_b_series = df_b[close_col]
        else:
            print(f"⚠️ 無法取得 {ticker_b} 的 {close_col} 數據。")

        rate_series = pd.Series(dtype="float64")
        if not df_rate.empty and close_col in df_rate.columns:
            rate_series = df_rate[close_col]
        else:
            print(f"⚠️ 無法取得 JPYTWD=X 的 {close_col} 數據。")

        # 2. 將 1306.T 轉換為台幣計價
        combined = pd.DataFrame(
            {"A_JPY": data_a_series, "B_TWD": data_b_series, "Rate": rate_series}
        ).dropna()
        combined["A_TWD"] = combined["A_JPY"] * combined["Rate"]

        # 3. 計算 RS 比率
        combined["RS"] = combined["A_TWD"] / combined["B_TWD"]

        # 4. 計算 RS 的 20 日均線
        combined["RS_MA20"] = combined["RS"].rolling(window=20).mean()

        # 確保 combined 不為空
        if combined.empty:
            print(f"⚠️ 數據處理後為空，無法進行 RS 分析。")
            return

        if CURRENT_ENV == "streamlit":
            import streamlit as st

            st.subheader(f"📊 台日資金流向觀察 (RS): {ticker_a} vs {ticker_b}")
            set_chinese_font()
            fig, ax = plt.subplots(figsize=(10, 5))
            ax.set_title("Relative Strength: Japan TOPIX vs Taiwan Top 50")
            ax.plot(
                combined.index,
                combined["RS"],
                label="RS Ratio (JPY-TWD adjusted)",
                color="blue",
                alpha=0.5,
            )
            ax.plot(
                combined.index,
                combined["RS_MA20"],
                label="RS 20MA Trend",
                color="red",
                linewidth=2,
            )
            ax.legend()
            st.pyplot(fig)

            current_rs = combined["RS"].iloc[-1]
            prev_rs_ma = combined["RS_MA20"].iloc[-1]
            status = (
                "🟢 資金流向日本 (日股強)"
                if current_rs > prev_rs_ma
                else "🔴 資金流向台灣 (台股強)"
            )
            st.info(f"當前趨勢診斷：{status}")

        elif CURRENT_ENV == "jupyter":
            print(f"\n--- 📊 台日資金流向觀察 (RS): {ticker_a} vs {ticker_b} ---")
            set_chinese_font()
            plt.figure(figsize=(10, 4))
            plt.plot(
                combined.index,
                combined["RS"],
                label="RS Ratio",
                color="blue",
                alpha=0.5,
            )
            plt.plot(
                combined.index,
                combined["RS_MA20"],
                label="RS 20MA Trend",
                color="red",
                linewidth=2,
            )
            plt.title("Relative Strength: Japan TOPIX vs Taiwan Top 50")
            plt.legend()
            plt.show()
            current_rs = combined["RS"].iloc[-1]
            prev_rs_ma = combined["RS_MA20"].iloc[-1]
            status = (
                "🟢 資金流向日本 (日股強)"
                if current_rs > prev_rs_ma
                else "🔴 資金流向台灣 (台股強)"
            )
            print(f"當前趨勢診斷：{status}")

        elif HAS_RICH:
            current_rs = combined["RS"].iloc[-1]
            prev_rs_ma = combined["RS_MA20"].iloc[-1]
            status = (
                "🟢 資金流向日本 (日股強)"
                if current_rs > prev_rs_ma
                else "🔴 資金流向台灣 (台股強)"
            )
            Console().print(
                f"\n[bold yellow]📊 台日資金流向觀察 (RS): {ticker_a} vs {ticker_b}[/bold yellow]\n當前趨勢診斷：{status}"
            )

        else:  # Plain console output
            current_rs = combined["RS"].iloc[-1]
            prev_rs_ma = combined["RS_MA20"].iloc[-1]
            status = (
                "🟢 資金流向日本 (日股強)"
                if current_rs > prev_rs_ma
                else "🔴 資金流向台灣 (台股強)"
            )
            print(f"\n--- 📊 台日資金流向觀察 (RS): {ticker_a} vs {ticker_b} ---")
            print(f"當前趨勢診斷：{status}")

    except Exception as e:
        print(f"RS 分析時發生錯誤: {e}")


def analyze_rs_thresholds():
    # 1. 下載過去兩年數據
    tickers = ["1306.T", "0050.TW", "JPYTWD=X"]
    try:
        all_data = yf.download(tickers, period="2y", progress=False)
    except Exception as e:
        print(f"⚠️ 無法取得 {', '.join(tickers)} 的歷史數據: {e}")
        return None, None

    if all_data.empty:
        print(f"⚠️ 抓取數據失敗或數據為空，無法進行 RS 閾值分析。")
        return None, None

    # Extract 'Close' prices for each ticker
    close_prices = pd.DataFrame()
    for ticker in tickers:
        if (ticker, "Close") in all_data.columns:
            close_prices[ticker] = all_data[(ticker, "Close")]
        else:
            print(f"⚠️ 無法取得 {ticker} 的 'Close' 數據，跳過。")
            return None, None  # If any critical ticker is missing, return None

    # 2. 計算以台幣為基準的相對強度 (RS)
    rs_series = (close_prices["1306.T"] * close_prices["JPYTWD=X"]) / close_prices[
        "0050.TW"
    ]
    rs_series = rs_series.dropna()  # 移除計算後的 NaN 值

    if rs_series.empty:
        print(f"⚠️ RS 系列數據為空，無法進行 RS 閾值分析。")
        return None, None

    # 3. 計算統計區間
    mean_rs = rs_series.mean()
    p20 = rs_series.quantile(0.20)  # 20% 分位數 (進入深水區)
    p10 = rs_series.quantile(0.10)  # 10% 分位數 (極度超跌)
    current_rs = rs_series.iloc[-1]

    print(f"\n--- 1306.T vs 0050 RS 兩年數據分析 ---")
    print(f"平均 RS 值: {mean_rs:.4f}")
    print(f"目前 RS 值: {current_rs:.4f}")
    print(f"【深水區】門檻 (P20): {p20:.4f}")
    print(f"【大掃把】門檻 (P10): {p10:.4f}")

    return p20, p10


if __name__ == "__main__":
    print("--- 執行 RS 分析 ---")
    plot_rs_analysis()
    print("\n--- 執行 RS 閾值分析 ---")
    analyze_rs_thresholds()
