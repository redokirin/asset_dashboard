import yfinance as yf
import pandas as pd
import numpy as np
import math
import logging
import importlib.util
import requests_cache
from assets_config import ASSETS, RADAR_TICKERS

# 設定 1 小時 (3600 秒) 的 Requests 快取，減輕 API 負擔並加速執行
requests_cache.install_cache("asset_tracking_cache", expire_after=3600)

logging.basicConfig(
    level=logging.WARNING, format="%(asctime)s - [%(levelname)s] - %(message)s"
)

try:
    from scipy import stats

    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


# 定義資料抓取器註冊表，允許從外部注入 (例如 Streamlit 快取版本)
FETCHERS = {
    "historical": lambda *args, **kwargs: yf.download(
        list(args[0]),
        period=kwargs.get("period", "2y"),
        progress=kwargs.get("progress", False),
        group_by=kwargs.get("group_by", "ticker"),
    ),
    "common": lambda *args, **kwargs: yf.download(
        list(args[0]),
        period=kwargs.get("period", "2y"),
        progress=kwargs.get("progress", False),
    ),
}


def fetch_historical_data(tickers, period="2y", group_by="ticker"):
    return FETCHERS["historical"](tickers, period=period, group_by=group_by)


def fetch_common_data(tickers, period="2y"):
    return FETCHERS["common"](tickers, period=period)


def get_market_radar_data():
    """抓取市場雷達數據"""
    data = []
    for ticker, name in RADAR_TICKERS.items():
        try:
            t = yf.Ticker(ticker)
            last_price = t.fast_info["last_price"]
            hist = t.history(period="2d")
            change_pct = (
                ((last_price - hist["Close"].iloc[0]) / hist["Close"].iloc[0] * 100)
                if not hist.empty
                else 0.0
            )
            data.append(
                {"代碼": ticker, "名稱": name, "數值": last_price, "漲跌幅": change_pct}
            )
        except Exception as e:
            logging.warning(f"無法獲取雷達數據 [{ticker}]: {e}")
    return data


def calculate_tick_price(target_price, market_type):
    """計算符合市場規則的跳動價位 (Tick Size)"""
    if market_type == "TW_STOCK":
        ticks = [(10, 0.01), (50, 0.05), (100, 0.1), (500, 0.5), (1000, 1.0)]
        tick = 5.0
        for limit, t in ticks:
            if target_price < limit:
                tick = t
                break
        return math.floor(round(target_price / tick, 8)) * tick
    elif market_type in ["TW_ETF", "TW_ETF_HIGH"]:
        tick = 0.01 if target_price < 50 else 0.05
        return math.floor(round(target_price / tick, 8)) * tick
    return round(target_price, 2)


def exchange_rate(radar):
    jpy_rate = next(
        (item["數值"] for item in radar if item["代碼"] == "JPYTWD=X"), None
    )
    usd_rate = next(
        (item["數值"] for item in radar if item["代碼"] == "USDTWD=X"), None
    )

    if jpy_rate is None:
        logging.warning("無法取得 JPY 匯率，啟用預設值 0.215！")
        jpy_rate = 0.215

    if usd_rate is None:
        logging.warning("無法取得 USD 匯率，啟用預設值 32.0！")
        usd_rate = 32.0

    return {
        "JPY": jpy_rate,
        "USD": usd_rate,
        "TWD": 1.0,
    }


def calculate_assets_data(exchange_rates):
    """資產價值核心計算"""
    results = []

    def process_asset(asset, category, price=None, change_val=None):
        rate = exchange_rates.get(asset["ccy"], 1.0)
        units = float(asset.get("units", asset.get("shares", 0)))
        if units == 0 and "investment" in asset:
            units = sum(i.get("units", i.get("shares", 0)) for i in asset["investment"])

        cost_origin = float(asset.get("cost", 0))
        if cost_origin == 0 and "investment" in asset:
            cost_origin = sum(i.get("cost", 0) for i in asset["investment"])

        avg_cost = cost_origin / units if units > 0 else 0
        current_price = price if price is not None else asset.get("nav", 0)

        val_twd, cost_twd = (current_price * units * rate), (cost_origin * rate)
        pl_val = val_twd - cost_twd

        suggested_bid = 0.0
        if price is not None and asset.get("market_type"):
            target = min(
                price * asset.get("discount", 0.985),
                avg_cost * 0.998 if avg_cost > 0 else 999999,
            )
            suggested_bid = calculate_tick_price(target, asset["market_type"])

        return {
            "市場": asset["market"],
            "類型": category,
            "名稱": asset["name"],
            "代碼": asset["id"],
            "幣別": asset["ccy"],
            "單位數": units,
            "平均成本": avg_cost,
            "漲跌": change_val,
            "股價": current_price,
            "建議掛單": suggested_bid,
            "成本": round(cost_twd),
            "市值": round(val_twd),
            "損益": round(pl_val),
            "報酬率": (pl_val / cost_twd * 100) if cost_twd != 0 else 0,
        }

    # 批次下載價格與歷史資料
    tickers_to_fetch = []
    for cat_key in ["funds", "etfs"]:
        for asset in ASSETS[cat_key].values():
            if asset.get("enabled", True) and asset.get("get_value"):
                tickers_to_fetch.append(asset["id"])

    batch_prices = {}
    batch_changes = {}
    if tickers_to_fetch:
        try:
            # 獲取近兩天資料以計算昨日收盤
            hist_data = fetch_historical_data(tuple(tickers_to_fetch), period="2d")
            for ticker in tickers_to_fetch:
                try:
                    df = (
                        hist_data[ticker]
                        if isinstance(hist_data.columns, pd.MultiIndex)
                        else hist_data
                    )
                    if df is not None and not df.empty and "Close" in df.columns:
                        df_clean = df.dropna(subset=["Close"])
                        if len(df_clean) >= 1:
                            current_price = float(df_clean["Close"].iloc[-1])
                            change_val = 0.0
                            if len(df_clean) >= 2:
                                prev_close = float(df_clean["Close"].iloc[-2])
                                change_val = current_price - prev_close

                            batch_prices[ticker] = current_price
                            batch_changes[ticker] = change_val
                except Exception as e:
                    logging.warning(f"解析 {ticker} 歷史資料失敗: {e}")
        except Exception as e:
            logging.error(f"批次下載價格資料失敗: {e}")

    for cat_key, cat_name in [("funds", "基金"), ("etfs", "ETF")]:
        for asset in ASSETS[cat_key].values():
            if not asset.get("enabled", True):
                continue

            price, change_val = None, None
            if asset.get("get_value"):
                price = batch_prices.get(asset["id"])
                if cat_key == "etfs":
                    change_val = batch_changes.get(asset["id"])

            res = process_asset(asset, cat_name, price, change_val)
            if res:
                results.append(res)

    df = pd.DataFrame(results)
    if df.empty:
        return df, pd.Series(dtype=float)

    total_val = df["市值"].sum()
    df["佔比"] = df["市值"] / total_val * 100
    market_sum = df.groupby("市場")["市值"].sum()
    market_share = pd.DataFrame(
        {"市值": market_sum, "佔比": (market_sum / total_val * 100).round(1)}
    ).to_dict(orient="index")
    return df, market_share


def calculate_buffered_entries(df, ma20, current_price, rs_p10_price):
    if "High" not in df.columns or "Low" not in df.columns:
        return None

    # 1. 計算 ATR (取 14 天平均波動)
    high_low = df["High"] - df["Low"]
    atr = high_low.rolling(window=14).mean().iloc[-1]
    if pd.isna(atr):
        return None

    # 2. 計算加入成交緩衝區 (Execution Buffer) 的建議買價
    BUFFER_PERCENT = 0.005  # 0.5%

    # 1. 日常波段位 (ATR 支撐線) -> 稍微往上墊高，增加日常掛單成交率
    raw_daily_swing = current_price - (1.0 * atr)
    buffered_daily_swing = raw_daily_swing * (1 + BUFFER_PERCENT)

    # 2. 技術回測位 (MA20 負乖離區) -> 避免差一元沒買到的遺憾
    raw_technical_retracement = ma20 * 0.97
    buffered_technical_retracement = raw_technical_retracement * (1 + BUFFER_PERCENT)

    # 3. 狙擊位 (大掃把 / RS 地核區) -> 即使是極端低點，也要稍微讓利確保入袋
    raw_sniper_entry = min(ma20 * 0.95, rs_p10_price)
    buffered_sniper_entry = raw_sniper_entry * (1 + BUFFER_PERCENT)

    # 安全檢查：確保緩衝後的建議買價「絕對不會」高於當前市價 (避免變成追高)
    # 我們設定建議價至少要比現價低 0.5%
    MAX_ALLOWED_PRICE = current_price * 0.995

    final_daily = min(buffered_daily_swing, MAX_ALLOWED_PRICE)
    final_tech = min(buffered_technical_retracement, MAX_ALLOWED_PRICE)
    final_sniper = min(buffered_sniper_entry, MAX_ALLOWED_PRICE)

    return {
        "日常波段": round(final_daily, 2),
        "技術回測": round(final_tech, 2),
        "狙擊位": round(final_sniper, 2),
    }


def generate_advanced_diagnosis(bias, sharpe, rs_percentile, ticker):
    """
    綜合判斷：技術乖離 (Bias) + 資產效率 (Sharpe) + RS 強度
    """
    # 1. 首先檢查是否為「過熱強勢股」
    if rs_percentile > 80:
        # return "強勢股\n不宜掛單\n(RS過熱)"
        return "⚠️ 強勢股 不宜掛單(RS過熱)"

    # 2. 檢查資產品質 (夏普值)
    is_low_quality = sharpe < 0.5  # 設定夏普值門檻，低於 0.5 視為低效率資產

    # 3. 技術面：極端負乖離 (🔵 燈)
    if bias <= -7:
        if is_low_quality:
            # return f"🔵 極端負乖離\n，夏普值極低({sharpe:.2f})\n，僅限極短線反彈\n，勿長抱！"
            return "🔵 極端負乖離，夏普值極低，僅限極短線反彈，勿長抱！"
        else:
            return "🔥 技術性低點，買入勝率極高，(高效率資產優選)"

    # 4. 技術面：一般負乖離 (🌊 燈)
    elif bias <= -4:
        if is_low_quality:
            return "🌊 短線跌深，但長期效率差，不建議在此建立主要倉位"
        else:
            return "🌊 短線跌深，優質資產分批進場點"

    # 5. 一般區間 (🟡 燈)
    else:
        # 特別針對 2409 這類資產在區間震盪時的警示
        # if is_low_quality and ticker == "2409.TW":
        #     return "⚪ 區間震盪\n，資產效率負值\n，建議將資金轉向 1306.T / 1655.T"
        return "⚪ 區間震盪價值回歸中"


# RS & 百分位：解決了「現在相對於台股，誰便宜、誰貴？」（相對位階）
# Alpha（勝率/月度）：解決了「誰是真的有能力賺贏大盤，而不只是跟風？」（超額能力）
# 夏普值 (Sharpe Ratio)：解決了「誰的報酬是拿高風險換來的？誰賺得最穩？」（風險效率）
def run_advanced_analysis(df_res, benchmark="0050.TW"):
    """合併執行 RS (相對強度) 與 Alpha (穩定性) 進階分析"""
    if len(df_res) == 1:
        active_tickers = df_res["代碼"].tolist()
    else:
        active_tickers = df_res[df_res["類型"] == "ETF"]["代碼"].tolist()

    if not active_tickers or not HAS_SCIPY:
        if not active_tickers:
            print("警告：沒有適合進行進階分析的 ETF Ticker")
        return pd.DataFrame()

    results = []
    try:
        common = fetch_common_data((benchmark, "JPYTWD=X", "USDTWD=X"), period="2y")
        if common.empty:
            return pd.DataFrame()
        price_col = (
            "Adj Close"
            if "Adj Close" in common.columns.get_level_values(0)
            else "Close"
        )
        c_data = common[price_col]
        b_series = c_data[benchmark].squeeze()
        if hasattr(b_series.index, "tz") and b_series.index.tz is not None:
            b_series.index = b_series.index.tz_localize(None)

        jpy_rate = (
            c_data["JPYTWD=X"].squeeze() if "JPYTWD=X" in c_data.columns else 0.215
        )
        usd_rate = (
            c_data["USDTWD=X"].squeeze() if "USDTWD=X" in c_data.columns else 32.0
        )

        t_data_all = fetch_historical_data(
            tuple(active_tickers), period="2y", group_by="ticker"
        )

        # 針對單一 ticker 可能返回非 MultiIndex 的結構進行處理
        is_multi = isinstance(t_data_all.columns, pd.MultiIndex)

        for ticker in active_tickers:
            try:
                if len(active_tickers) == 1:
                    # 強制轉為 MultiIndex 結構或直接處理
                    if not is_multi:
                        t_df = t_data_all
                    else:
                        t_df = (
                            t_data_all[ticker]
                            if ticker in t_data_all.columns.get_level_values(0)
                            else t_data_all
                        )
                else:
                    t_df = (
                        t_data_all[ticker]
                        if is_multi and ticker in t_data_all.columns.get_level_values(0)
                        else t_data_all
                    )

                if t_df is None or t_df.empty or "Close" not in t_df.columns:
                    continue

                t_df_clean = t_df.dropna(subset=["Close"]).copy()
                if len(t_df_clean) == 0:
                    continue

                # 計算技術燈號與均線
                ma20_str, ma60_str, ma120_str = "-", "數據不足", "數據不足"
                tech_signal = "  "
                bias_str = "-"
                bias_numeric = 0.0
                diag_text = "數據不足"
                ma20_val = None
                price_val = float(t_df_clean["Close"].iloc[-1])

                # tech_signal 說明：
                # strong = "🟠"  # 極度價值區 (低於月線 -7%，強力加碼)
                # rebound = "💧" # 跌深反彈區 (低於月線 -4%~-7%，注意反彈)
                # buy = "🟡"     # 價值區 (低於月線，二線買點)
                # warning = "🔴"  # 過熱區 (高於月線 +7%，暫緩加碼)
                # healthy = "🟢"  # 趨勢區 (沿月線上漲，定期定額)

                if len(t_df_clean) >= 20:
                    ma20_val = t_df_clean["Close"].rolling(20).mean().iloc[-1]
                    if pd.notnull(ma20_val) and ma20_val > 0:
                        ma20_str = f"{ma20_val:.2f}"
                        bias_numeric = ((price_val - ma20_val) / ma20_val) * 100
                        bias_str = f"{bias_numeric:.2f}%"

                        if bias_numeric <= -7:
                            tech_signal = "🟠 極度價值區"
                            diag_text = "🔥 技術性低點\n，買入勝率極高"
                        elif -7 < bias_numeric <= -4:
                            tech_signal = "💧 跌深反彈區"
                            diag_text = "🌊 短線跌深\n，注意反彈機會"
                        elif bias_numeric >= 7:
                            tech_signal = "🔴 過熱區"
                            diag_text = "⚠️ 短線過熱\n，嚴禁追高"
                        else:
                            tech_signal = (
                                "🟢 趨勢區" if price_val >= ma20_val else "🟡 價值區"
                            )
                            diag_text = "區間震盪"

                if len(t_df_clean) >= 60:
                    ma60_val = t_df_clean["Close"].rolling(60).mean().iloc[-1]
                    if pd.notnull(ma60_val):
                        ma60_str = f"{ma60_val:.2f}"

                if len(t_df_clean) >= 120:
                    ma120_val = t_df_clean["Close"].rolling(120).mean().iloc[-1]
                    if pd.notnull(ma120_val):
                        ma120_str = f"{ma120_val:.2f}"

                t_col = "Adj Close" if "Adj Close" in t_df_clean.columns else "Close"

                # 自動判斷幣別
                ccy = (
                    "JPY"
                    if ticker.endswith(".T")
                    else "USD"
                    if ".US" in ticker or ticker.isupper()
                    else "TWD"
                )
                rate = jpy_rate if ccy == "JPY" else usd_rate if ccy == "USD" else 1.0

                p_series = t_df_clean[t_col].squeeze()
                if hasattr(p_series.index, "tz") and p_series.index.tz is not None:
                    p_series.index = p_series.index.tz_localize(None)

                r_series = rate.squeeze() if hasattr(rate, "squeeze") else rate
                if (
                    isinstance(r_series, pd.Series)
                    and hasattr(r_series.index, "tz")
                    and r_series.index.tz is not None
                ):
                    r_series.index = r_series.index.tz_localize(None)

                comb = (
                    pd.DataFrame({"p": p_series, "r": r_series, "b": b_series})
                    .ffill()
                    .dropna()
                )

                if comb.empty:
                    continue

                # --- 1. RS 計算 ---
                rs_series = (comb["p"] * comb["r"]) / comb["b"]
                if len(rs_series) < 20:
                    continue

                curr_rs = float(rs_series.iloc[-1])
                pct = stats.percentileofscore(rs_series.values.flatten(), curr_rs)

                # 計算 RS 第 10 百分位值對應的股價 (Deep Water 價格)
                # RS = (Asset_Price * Rate) / Benchmark_Price
                # Asset_Price = (RS * Benchmark_Price) / Rate
                rs_p10 = float(np.percentile(rs_series.values.flatten(), 10))
                rs_p10_price = (rs_p10 * comb["b"].iloc[-1]) / comb["r"].iloc[-1]

                # --- 建議掛單價計算 (多重位階) ---
                suggested_bid_str = "-"
                daily_wave, tech_retest, sniper_pos = "-", "-", "-"
                if pct > 80:
                    suggested_bid_str = "-"
                    daily_wave, tech_retest, sniper_pos = "-", "-", "-"
                else:
                    if ma20_val is not None:
                        entries = calculate_buffered_entries(
                            t_df_clean, ma20_val, price_val, rs_p10_price
                        )
                        if entries:
                            suggested_bid_str = f"{entries['日常波段']:.2f} | {entries['技術回測']:.2f} | {entries['狙擊位']:.2f}"
                            daily_wave = f"{entries['日常波段']:.2f}"
                            tech_retest = f"{entries['技術回測']:.2f}"
                            sniper_pos = f"{entries['狙擊位']:.2f}"

                # --- 2. Alpha 穩定性與夏普計算 ---
                # 在換算為 TWD 基準下重新取樣至月底
                m_price = comb.resample("ME").last()
                m_ret = pd.DataFrame(
                    {
                        "target_ret": (m_price["p"] * m_price["r"]).pct_change(),
                        "bench_ret": m_price["b"].pct_change(),
                    }
                ).dropna()

                if m_ret.empty or len(m_ret) < 2:
                    bat_avg, avg_alpha, sharpe = 0.0, 0.0, 0.0
                else:
                    m_ret["Alpha"] = m_ret["target_ret"] - m_ret["bench_ret"]
                    avg_alpha = m_ret["Alpha"].mean() * 100
                    bat_avg = (m_ret["Alpha"] > 0).mean() * 100
                    std_r = m_ret["target_ret"].std()
                    sharpe = (
                        (m_ret["target_ret"].mean() / std_r * (12**0.5))
                        if std_r != 0
                        else 0.0
                    )

                # --- 3. 綜合診斷 ---
                diag_text = generate_advanced_diagnosis(
                    bias_numeric, sharpe, pct, ticker
                )

                # --- 結合結果 ---
                asset_match = df_res[df_res["代碼"] == ticker]
                asset_name = (
                    asset_match["名稱"].iloc[0] if not asset_match.empty else ticker
                )

                results.append(
                    {
                        "代碼": ticker,
                        "名稱": asset_name,
                        "股價": f"{price_val:.2f}",
                        "技術燈號": tech_signal,
                        "乖離率 (Bias)": bias_str,
                        "技術診斷": diag_text,
                        "建議掛單": suggested_bid_str,
                        "日常波段": daily_wave,
                        "技術回測": tech_retest,
                        "狙擊位": sniper_pos,
                        "MA20": ma20_str,
                        "MA60": ma60_str,
                        "MA120": ma120_str,
                        "當前 RS": round(curr_rs, 4),
                        "RS 百分位": f"{pct:.1f}%",
                        "狀態": "🔵 深水"
                        if pct <= 15
                        else ("🔥 過熱" if pct >= 85 else "⚪ 正常"),
                        "Alpha 勝率": f"{bat_avg:.1f}%" if len(m_ret) >= 2 else "-",
                        "月度 Alpha": f"{avg_alpha:+.2f}%" if len(m_ret) >= 2 else "-",
                        "夏普值": f"{sharpe:.2f}" if len(m_ret) >= 2 else "-",
                        "_score": pct,
                    }
                )
            except Exception as e:
                logging.warning(f"進階分析計算異常 [{ticker}]: {e}")
                continue
    except Exception as e:
        logging.error(f"取得進階分析資料失敗: {e}")

    if results:
        df_rs = pd.DataFrame(results).sort_values("_score", ascending=False)
        return df_rs.drop(columns=["_score"])

    return pd.DataFrame()


def export_for_ai(df):
    """導出 AI 分析文本"""
    print("--- AI 分析專用數據摘要 ---")
    cols = ["代碼", "股價", "漲跌", "平均成本", "單位數", "報酬率", "建議掛單"]
    print(df[cols].to_markdown(index=False))
    print("-" * 30)
