import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import platform
import sys


# --- 貨幣偵測輔助函式 ---
def get_ticker_currency(ticker_name):
    """
    根據後綴或 yfinance 資訊判斷標的幣別
    """
    # 1. 優先透過後綴快速判斷，減少 API 請求
    if ticker_name.endswith(".T"):
        return "JPY"
    if ticker_name.endswith(".TW"):
        return "TWD"
    if "." not in ticker_name:
        return "USD"  # 通常美股無後綴

    # 2. 若無法判斷，則抓取 yfinance 的 fast_info (較快)
    try:
        t = yf.Ticker(ticker_name)
        return t.fast_info.get("currency", "USD")
    except:
        return "USD"  # 預設回傳美金


def get_exchange_rate(from_ccy, to_ccy, period="2y"):
    """
    自動抓取對應匯率，若幣別相同則回傳 1
    """
    if from_ccy == to_ccy:
        return pd.Series(1.0, name="Rate")

    pair = f"{from_ccy}{to_ccy}=X"
    print(f"🔄 偵測到跨幣別交易，正在抓取匯率: {pair}")
    try:
        df = yf.download(pair, period=period, progress=False)
        # 處理 yfinance 可能回傳的 MultiIndex 或不同格式
        if isinstance(df.columns, pd.MultiIndex):
            return df["Close"][pair]
        return df["Close"]
    except:
        print(f"⚠️ 無法取得匯率 {pair}，預設比率為 1")
        return pd.Series(1.0, name="Rate")


# --- 修改後的分析核心邏輯 ---
def analyze_rs_smart(ticker_a, ticker_b, period="2y"):
    """
    自動偵測幣別並計算相對強度
    """
    # 偵測幣別
    ccy_a = get_ticker_currency(ticker_a)
    ccy_b = get_ticker_currency(ticker_b)

    print(f"🔍 標的分析: {ticker_a} ({ccy_a}) vs {ticker_b} ({ccy_b})")

    # 1. 抓取股價數據
    data_a = yf.download(ticker_a, period=period, progress=False)
    data_b = yf.download(ticker_b, period=period, progress=False)

    # 2. 處理跨幣別轉換 (統一換算成 ticker_b 的幣別)
    rate_series = get_exchange_rate(ccy_a, ccy_b, period=period)

    # 3. 資料清洗與對齊
    # 提取 Close
    def extract_close(df, name):
        if isinstance(df.columns, pd.MultiIndex):
            return df["Close"][name]
        return df["Close"]

    close_a = extract_close(data_a, ticker_a)
    close_b = extract_close(data_b, ticker_b)

    combined = pd.DataFrame({"A": close_a, "B": close_b, "Rate": rate_series}).dropna()

    # 4. 計算 RS ( A * Rate / B )
    combined["RS"] = (combined["A"] * combined["Rate"]) / combined["B"]
    combined["RS_MA20"] = combined["RS"].rolling(window=20).mean()

    # 5. 輸出統計 (P20/P10 門檻)
    p20 = combined["RS"].quantile(0.20)
    p10 = combined["RS"].quantile(0.10)
    current_rs = combined["RS"].iloc[-1]

    print(f"\n--- 歷史區間分析 ---")
    print(f"當前 RS: {current_rs:.4f} | P20 深水區: {p20:.4f} | P10 大掃把: {p10:.4f}")

    # 繪圖與診斷邏輯 (略，與原腳本相同)
    return current_rs, p20, p10


if __name__ == "__main__":
    t_a = sys.argv[1] if len(sys.argv) > 1 else "1306.T"
    t_b = sys.argv[2] if len(sys.argv) > 2 else "0050.TW"

    analyze_rs_smart(t_a, t_b)
