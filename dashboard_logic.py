import yfinance as yf
import pandas as pd
import numpy as np
import math
import logging
import importlib.util
import requests_cache
import streamlit as st
import tomllib
from pathlib import Path
import gspread
from google.oauth2.service_account import Credentials
import os


# --- 配置讀取邏輯 ---
# 優先從 Secrets 讀取 ID，否則使用預設值
SPREADSHEET_ID = st.secrets.get("spreadsheet_id", "1xiuVw0fuuIdqVX0a-gGf0MkEZWmwWGnsRndCoNEc-4A")
CREDENTIALS_PATH = Path(__file__).parent / "credentials.json"

@st.cache_data(ttl=600)  # 每 10 分鐘快取一次
def get_config_from_gsheets():
    """從 Google Sheets 讀取資產配置，支援本地檔案與 Streamlit Secrets"""
    creds = None
    
    # 1. 優先嘗試從 Streamlit Secrets 讀取 (適合 Cloud 部署)
    if "gcp_service_account" in st.secrets:
        try:
            creds_info = st.secrets["gcp_service_account"]
            # 確保是標準 dict
            if hasattr(creds_info, "to_dict"):
                creds_info = creds_info.to_dict()
            else:
                creds_info = dict(creds_info)
            
            scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
            creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
            logging.info("使用 Streamlit Secrets 載入 Google 憑證")
        except Exception as e:
            logging.error(f"從 Secrets 載入憑證失敗: {e}")

    # 2. 如果 Secrets 沒有，嘗試讀取本地檔案 (適合本地開發)
    if not creds and CREDENTIALS_PATH.exists():
        try:
            scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
            creds = Credentials.from_service_account_file(str(CREDENTIALS_PATH), scopes=scopes)
            logging.info("使用本地 credentials.json 載入 Google 憑證")
        except Exception as e:
            logging.error(f"從本地檔案載入憑證失敗: {e}")

    if not creds:
        logging.warning("找不到有效的 Google 憑證 (Secrets 或本地檔案)")
        return None

    try:
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(SPREADSHEET_ID)

        config = {}

        # 1. 讀取 radar_tickers
        try:
            ws_radar = sh.worksheet("radar_tickers")
            radar_data = ws_radar.get_all_records()
            config["radar_tickers"] = {row["Ticker"]: row["Name"] for row in radar_data if row["Ticker"]}
        except Exception as e:
            logging.error(f"讀取 radar_tickers 分頁失敗: {e}")

        # 2. 讀取 funds (以 Key 為索引)
        try:
            ws_funds = sh.worksheet("funds")
            funds_data = ws_funds.get_all_records()
            funds_dict = {}
            numeric_cols = ["nav", "units", "cost"]
            for row in funds_data:
                key = str(row.pop("Key", ""))
                if key:
                    cleaned_row = {}
                    for k, v in row.items():
                        if k in numeric_cols:
                            try:
                                # 處理空值、逗號分隔的數字或字串格式
                                if v == "" or v is None:
                                    cleaned_row[k] = 0.0
                                else:
                                    cleaned_row[k] = float(str(v).replace(",", ""))
                            except (ValueError, TypeError):
                                cleaned_row[k] = 0.0
                        elif v != "":
                            cleaned_row[k] = v
                    funds_dict[key] = cleaned_row
            config["funds"] = funds_dict
        except Exception as e:
            logging.error(f"讀取 funds 分頁失敗: {e}")

        # 3. 讀取 etfs (以 Ticker 為索引)
        try:
            ws_etfs = sh.worksheet("etfs")
            etfs_data = ws_etfs.get_all_records()
            etfs_dict = {}
            numeric_cols = ["shares", "cost", "discount"]
            for row in etfs_data:
                ticker = str(row.pop("Ticker", ""))
                if ticker:
                    cleaned_row = {}
                    for k, v in row.items():
                        if k in numeric_cols:
                            try:
                                if v == "" or v is None:
                                    cleaned_row[k] = 0.0
                                else:
                                    cleaned_row[k] = float(str(v).replace(",", ""))
                            except (ValueError, TypeError):
                                cleaned_row[k] = 0.0
                        elif v != "":
                            cleaned_row[k] = v
                    etfs_dict[ticker] = cleaned_row
            config["etfs"] = etfs_dict
        except Exception as e:
            logging.error(f"讀取 etfs 分頁失敗: {e}")

        return config
    except Exception as e:
        logging.error(f"Google Sheets 讀取失敗: {e}")
        return None

@st.cache_data
def get_config():
    """
    讀取資產配置。優先從 Google Sheets 讀取，其次本地 assets_config.toml，
    最後為 Streamlit Secrets。
    """
    # 1. 優先從 Google Sheets 讀取
    gs_config = get_config_from_gsheets()
    if gs_config:
        return gs_config

    # 2. 偵測本地檔案是否存在
    current_dir = Path(__file__).parent
    toml_path = current_dir / "assets_config.toml"
    if toml_path.exists():
        try:
            with open(toml_path, "rb") as f:
                config = tomllib.load(f)
                return config.get("my_assets", {})
        except Exception as e:
            logging.error(f"本地配置讀取失敗: {e}")

    # 2. 檔案不存在或讀取失敗，嘗試從 Streamlit Secrets 讀取
    try:
        if "my_assets" in st.secrets:
            # 轉換為標準 dict 以避免序列化時的 RecursionError
            secrets_data = st.secrets["my_assets"]
            if hasattr(secrets_data, "to_dict"):
                return secrets_data.to_dict()
            return dict(secrets_data)
    except Exception as e:
        logging.error(f"Secrets 讀取失敗: {e}")

    logging.error("🚨 配置缺失：未偵測到 assets_config.toml 或 st.secrets['my_assets']")
    return {}


# 初始化配置
_config = get_config()
RADAR_TICKERS = _config.get("radar_tickers", {})


# 實際上原有的 ASSETS 是 {"funds": {...}, "etfs": {...}}
# 增加防呆機制：如果項目中沒有定義 id，則以 Key 為預設 id
def _ensure_id(config_dict):
    result = {}
    if not isinstance(config_dict, dict):
        return result
    for key, val in config_dict.items():
        if not isinstance(val, dict):
            continue
        if "id" not in val:
            val["id"] = key
        result[key] = val
    return result


ASSETS = {
    "funds": _ensure_id(_config.get("funds", {})),
    "etfs": _ensure_id(_config.get("etfs", {})),
}

# 使用 lru_cache 進行簡單的記憶體快取，配合 requests_cache 達成雙重效能優化
from functools import lru_cache

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


@lru_cache(maxsize=128)
def get_ticker_fundamental_info(ticker_symbol):
    """獲取 Ticker 的基本面與即時數據，並提供安全性處理"""
    try:
        t = yf.Ticker(ticker_symbol)
        info = t.info
        # 由於台日股數據常缺失，使用 get 確保安全性
        return {
            "eps": info.get("trailingEps", 0) or 0,
            "pe": info.get("trailingPE", 0) or 0,
            "dividendYield": info.get("dividendYield", 0) or 0,
            "pegRatio": info.get("trailingPegRatio", 0) or info.get("pegRatio", 0) or 0,
            "volume": info.get("volume", 0) or 0,
            "avg_volume": info.get("averageVolume", 1) or 1,  # 避免除以 0
        }
    except Exception:
        return {
            "eps": 0,
            "pe": 0,
            "dividendYield": 0,
            "pegRatio": 0,
            "volume": 0,
            "avg_volume": 1,
        }


# 定義資料抓取器註冊表，允許從外部注入 (例如 Streamlit 快取版本)
FETCHERS = {
    "historical": lambda *args, **kwargs: yf.download(
        list(args[0]),
        period=kwargs.get("period", "2y"),
        progress=kwargs.get("progress", False),
        group_by=kwargs.get("group_by", "ticker"),
        auto_adjust=True,  # 自動處理股票拆分與除息，確保技術指標不失真
    ),
    "common": lambda *args, **kwargs: yf.download(
        list(args[0]),
        period=kwargs.get("period", "2y"),
        progress=kwargs.get("progress", False),
        auto_adjust=True,  # 確保 Benchmark 與匯率同樣經過調整
    ),
}


def fetch_historical_data(tickers, period="2y", group_by="ticker"):
    df_all = FETCHERS["historical"](tickers, period=period, group_by=group_by)

    # --- 1306.T 特殊數據修正邏輯 (Yahoo Finance 暫時性錯誤 Patch) ---
    # 當 1306.T 發生乖離率絕對值超過 50% 的異常時，自動除以 10 修正
    target_ticker = "1306.T"
    has_target = False
    if isinstance(df_all.columns, pd.MultiIndex):
        has_target = target_ticker in df_all.columns.get_level_values(0)
    else:
        # 如果不是 MultiIndex，檢查單一 Ticker 是否匹配
        check_list = [tickers] if isinstance(tickers, str) else list(tickers)
        if target_ticker in check_list and "Close" in df_all.columns:
            has_target = True

    if has_target:
        try:
            target_df = (
                df_all[target_ticker]
                if isinstance(df_all.columns, pd.MultiIndex)
                else df_all
            )
            current_price = target_df["Close"].iloc[-1]
            if pd.notnull(current_price):
                # 修正邏輯：1306.T 在 2024/07 執行 1:10 分割。
                # Yahoo Finance 偶發回傳未調整數據，導致歷史價格比現價高 10 倍。
                # 1. 檢測全域單位錯誤 (若連現價都 > 10000，代表整個序列都錯了)
                if current_price > 10000:
                    print(
                        f"\n[bold red]偵測到 {target_ticker} 全域單位異常 (價格 {current_price:.0f})，執行 1:10 修正...[/]"
                    )
                    cols_to_fix = ["Open", "High", "Low", "Close"]
                    if isinstance(df_all.columns, pd.MultiIndex):
                        for col in cols_to_fix:
                            if col in df_all[target_ticker].columns:
                                df_all.loc[:, (target_ticker, col)] /= 10
                        if "Volume" in df_all[target_ticker].columns:
                            df_all.loc[:, (target_ticker, "Volume")] *= 10
                    else:
                        df_all.loc[:, cols_to_fix] /= 10
                        if "Volume" in df_all.columns:
                            df_all["Volume"] *= 10
                # 2. 檢測局部調整異常 (現價正常，但歷史中有極高值，會嚴重扭曲 MA 與乖離率)
                else:
                    # 只要歷史中存在高於現價 5 倍以上的數值，就判定為未調整部分並進行 1:10 修正
                    threshold = current_price * 5
                    high_price_dates = target_df.index[target_df["Close"] > threshold]

                    if not high_price_dates.empty:
                        print(
                            f"\n[bold red]偵測到 {target_ticker} 歷史分割數據未對齊，修正 {len(high_price_dates)} 筆異常資料...[/]"
                        )
                        cols_to_scale = ["Open", "High", "Low", "Close"]
                        if isinstance(df_all.columns, pd.MultiIndex):
                            for col in cols_to_scale:
                                if (target_ticker, col) in df_all.columns:
                                    df_all.loc[
                                        high_price_dates, (target_ticker, col)
                                    ] /= 10
                            if "Volume" in df_all[target_ticker].columns:
                                # 分割後股數增加，故歷史成交量需乘以 10 以維持對齊
                                df_all.loc[
                                    high_price_dates, (target_ticker, "Volume")
                                ] *= 10
                        else:
                            df_all.loc[high_price_dates, cols_to_scale] /= 10
                            if "Volume" in df_all.columns:
                                df_all.loc[high_price_dates, "Volume"] *= 10
        except Exception:
            pass
    return df_all


def fetch_common_data(tickers, period="2y"):
    return FETCHERS["common"](tickers, period=period)


def get_market_radar_data():
    """抓取市場雷達數據"""
    data = []
    for ticker, name in RADAR_TICKERS.items():
        try:
            t = yf.Ticker(ticker)
            # 優先從 fast_info 獲取
            try:
                last_price = t.fast_info["last_price"]
            except Exception:
                # 備援方案：從歷史數據獲取最後收盤價
                hist_1d = t.history(period="1d")
                if not hist_1d.empty:
                    last_price = hist_1d["Close"].iloc[-1]
                else:
                    logging.warning(f"無法獲取雷達數據價格 [{ticker}]")
                    continue

            hist = t.history(period="2d")
            change_pct = (
                ((last_price - hist["Close"].iloc[0]) / hist["Close"].iloc[0] * 100)
                if not hist.empty and len(hist) >= 2
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
            # 獲取近一月資料以確保昨日收盤計算正確，並支援 1306.T 的乖離率數據檢查
            hist_data = fetch_historical_data(tuple(tickers_to_fetch), period="1mo")
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
        # 建立一個有預期欄位的空 DataFrame
        columns = [
            "市場",
            "類型",
            "名稱",
            "代碼",
            "幣別",
            "單位數",
            "平均成本",
            "漲跌",
            "股價",
            "建議掛單",
            "成本",
            "市值",
            "損益",
            "報酬率",
            "佔比",
        ]
        return pd.DataFrame(columns=columns), {}

    total_val = df["市值"].sum()
    df["佔比"] = df["市值"] / total_val * 100
    market_sum = df.groupby("市場")["市值"].sum()
    market_share = pd.DataFrame(
        {"市值": market_sum, "佔比": (market_sum / total_val * 100).round(1)}
    ).to_dict(orient="index")
    return df, market_share


def calculate_buffered_entries(df, ma20, ma250, current_price, rs_p10_price):
    if "High" not in df.columns or "Low" not in df.columns or len(df) < 14:
        return None

    # 1. 計算 ATR (加入數據長度檢查)
    high_low = df["High"] - df["Low"]
    atr = high_low.rolling(window=14).mean().iloc[-1]
    if pd.isna(atr):
        return None

    # 定義參考基準價 (Reference Price)：錨定昨日收盤，避免買點隨今日開盤跳空而追高
    # 註：因 df.iloc[-1] 為包含今日變動的現價，故取 iloc[-2] 作為昨日靜態收盤基準
    prev_close = df["Close"].iloc[-2] if len(df) >= 2 else current_price

    # 2. 設定參數
    BUFFER_PERCENT = 0.005  # 0.5% 讓利緩衝
    MIN_GAP = 0.015  # 1.5% 強制價格階梯間隔

    # --- 原始價位計算 ---
    # 日常位：改以「昨日收盤」為計算基準，確保支撐位階不隨今日跳空而上移
    raw_daily = prev_close - (1.0 * atr)

    # 技術位與狙擊位：以均線為基準 (反應趨勢)
    raw_tech = ma20 * 0.97

    # --- 終極地板 Fallback 邏輯 ---
    # 若無 MA250 (掛牌未滿一年)，則不強制引入長線地板，回歸 MA20 與 RS 評價
    long_term_floor = ma250 * 0.98 if ma250 is not None else 999999.0
    raw_sniper = min(ma20 * 0.95, rs_p10_price, long_term_floor)

    # --- 強制階梯邏輯 (The Fix) ---
    # 安全天花板：建議價最高不得超過現價的 99.5%
    ceiling = current_price * 0.995

    # 1. 最終日常位
    final_daily = min(raw_daily * (1 + BUFFER_PERCENT), ceiling)

    # 2. 最終技術位：必須低於日常位至少一個 MIN_GAP
    final_tech = min(raw_tech * (1 + BUFFER_PERCENT), final_daily * (1 - MIN_GAP))

    # 3. 最終狙擊位：必須低於技術位至少一個 MIN_GAP
    final_sniper = min(raw_sniper * (1 + BUFFER_PERCENT), final_tech * (1 - MIN_GAP))

    return {
        "日常波段": round(final_daily, 2),
        "技術回測": round(final_tech, 2),
        "狙擊位": round(final_sniper, 2),
    }


# ┌──────────────────┬──────────────────────┬───────────────────────────────────────────────────────┐
# │ 參數名稱          │ 中文名稱               │ 診斷用途說明                                          │
# ├──────────────────┼──────────────────────┼───────────────────────────────────────────────────────┤
# │ price            │ 現價                  │ 作為所有技術位階計算的基礎基準。                      │
# │ ma20             │ 月線 (20日均線)      │ 定義「短線動能」與計算「乖離率」的核心指標。          │
# │ ma250            │ 年線 (250日均線)     │ 定義「長線格局」多空的分水嶺。                        │
# │ vol_ratio        │ 量比 (成交量比率)    │ 偵測異常動能（如爆量、窒息量）與驗證價格真偽。        │
# │ price_change_pct │ 今日漲跌幅           │ 結合量比進行「量價驗證」判斷。                        │
# │ rs_percentile    │ RS 百分位 (相對強度)   │ 判斷標的在市場中的強度位階（如過熱區、深水區）。      │
# │ sharpe           │ 夏普值 (風險效率)      │ 衡量資產的報酬/風險比，篩選高效率標的。               │
# │ eps              │ 每股盈餘              │ 判斷企業基本面是否具備實質獲利支撐。                  │
# │ pe_ratio         │ 本益比                │ 評估股價目前的「估值高低」區位。                      │
# │ dividend_yield   │ 股息殖利率            │ 偵測是否具備「🛡️ 息收護城河」防禦屬性。               │
# │ peg_ratio        │ PEG 比例             │ 結合成長性與估值的平衡指標（💎 PEG < 1 為超值成長）。 │
# │ bias             │ 乖離率                │ 衡量股價偏離月線的程度，判斷「極度價值」或「過熱」。  │
# │ rsi              │ RSI (相對強弱指數)     │ 輔助判斷短線的超買或超賣狀態。                        │
# └──────────────────┴──────────────────────┴───────────────────────────────────────────────────────┘
#   🔍 診斷邏輯中的標籤 (Tags) 說明：
#    * 🛡️ 息收護城河：低位階且具備 3.5% 以上高殖利率。
#    * 💎 估值極具吸引力：PEG < 1，代表成長性優於估值擴張。
#    * 📊 盈利穩健：具備正向 EPS 支撐。
#    * ⚠️ 成長溢價過高：PEG > 2，代表股價已透支未來成長。
#    * 🔥 極致強勢：長、短線趨勢處於多頭共振狀態。


def generate_objective_diagnosis(
    price,
    ma20,
    ma250,
    vol_ratio,
    price_change_pct,
    rs_percentile,
    sharpe,
    eps=None,
    pe_ratio=None,
    dividend_yield=None,
    peg_ratio=None,
):
    """
    核心客觀診斷邏輯 (基本面 + 技術位階 + 股息護城河 + PEG 成長平衡器)
    """
    tags = []
    # 1. 長線格局 (Long-term Context)
    if ma250 is None or math.isnan(ma250):
        lt_context = "LONG_UNKNOWN"
        lt_desc = "長線趨勢數據不足"
    elif price > ma250:
        lt_context = "BULLISH"
        lt_desc = "長線多頭格局"
    else:
        lt_context = "BEARISH"
        lt_desc = "長線空頭排列"

    # 2. 短線動能 (Short-term Momentum)
    if ma20 is None or math.isnan(ma20):
        st_momentum = "MOM_UNKNOWN"
    elif price > ma20:
        st_momentum = "STRONG"
    else:
        st_momentum = "WEAK"

    # 3. 綜合格局標籤 (Professional Research Tone)
    match (lt_context, st_momentum):
        case ("BULLISH", "STRONG"):
            tags.append("🔥 極致強勢")
            advice_base = "標的處於長短線多頭共振，向上動能極強。"
        case ("BULLISH", "WEAK"):
            tags.append("🟢 長線多頭")
            advice_base = "標的維持長線多頭格局，但短線動能出現技術性背離（跌破月線），目前正進行結構性回測。"
        case ("BEARISH", "STRONG"):
            tags.append("💧 弱勢反彈")
            advice_base = "長線空頭趨勢未變，當前價格運動僅屬超跌後的短線乖離修正。"
        case ("BEARISH", "WEAK"):
            tags.append("🔵 長線偏弱")
            advice_base = "長短線均受制於下行均線，技術面承壓，尚未見止跌訊號。"
        case _:
            tags.append("⚪ 中性整理")
            advice_base = "趨勢動能不明，建議於關鍵支撐位階觀察。"

    # 4. 基本面、股息護城河與 PEG 診斷
    fund_advice = ""

    # 4.1 估值診斷
    if eps is not None and not math.isnan(eps) and eps > 0:
        tags.append("📊 盈利穩健")
        if pe_ratio is not None and not math.isnan(pe_ratio) and pe_ratio > 0:
            pe_desc = (
                "低估值"
                if pe_ratio < 15
                else "合理估值"
                if pe_ratio <= 30
                else "高成長溢價"
            )
            fund_advice += f"基本面 EPS 正向，反映{pe_desc}。"

    # 4.2 股息護城河 (Dividend Moat)
    if (
        dividend_yield is not None
        and not math.isnan(dividend_yield)
        and dividend_yield > 0.035
    ):
        if rs_percentile < 20 or lt_context == "BEARISH":
            tags.append("🛡️ 息收護城河")
            fund_advice += (
                f"具備高股息殖利率({dividend_yield:.1%})，在深水區提供強大下行支撐。\n"
            )

    # 4.3 PEG Validator
    if peg_ratio is not None and not math.isnan(peg_ratio) and peg_ratio > 0:
        if peg_ratio < 1.0:
            tags.append("💎 估值極具吸引力 (PEG < 1)")
            fund_advice += "成長估值極其便宜 (PEG < 1)。"
        elif peg_ratio > 2.0:
            tags.append("⚠️ 成長溢價過高 (PEG > 2)")
            if lt_context == "BULLISH":
                fund_advice += "雖然趨勢向上，但成長估值已顯過熱 (PEG > 2)。"

    if sharpe > 1.2:
        tags.append("💎 高效率資產")

    # 5. 量價驗證與結構性換手偵測
    vp_advice = ""
    if price_change_pct > 1.5:
        if vol_ratio > 1.5:
            vp_advice = "今日價量齊揚，主動性買盤積極介入。"
        elif vol_ratio < 0.75:
            vp_advice = "⚠️ 注意價漲量縮現象，反彈動能缺乏量能支撐，慎防追高風險。"
    elif price_change_pct < -1.5:
        if vol_ratio > 2.0:
            vp_advice = "😱 偵測到結構性換手或恐慌拋售（異常爆量 2.0x+），\n技術支撐可能失效，建議暫緩接單，優先觀察更深層的防守位。"
        elif vol_ratio > 1.5:
            vp_advice = "😱 帶量下殺，恐慌性賣壓持續湧現，建議先觀察狙擊防守位。"
        elif vol_ratio < 0.8:
            vp_advice = "量縮下跌，顯示賣壓已出現竭盡跡象，利於短線止跌企穩。"

    # 組合最終建議
    fund_display = f"\n{fund_advice}" if fund_advice else ""
    vp_advice_display = f"\n{vp_advice}" if vp_advice else ""
    advice_base_display = f"\n{advice_base}" if advice_base else ""
    full_advice = f"{lt_desc}。{advice_base_display}{fund_display}{vp_advice_display}"

    return tags, full_advice


def generate_advanced_diagnosis(
    bias,
    sharpe,
    rs_percentile,
    ticker,
    price_change_pct=0,
    vol_ratio=1.0,
    rsi=0,
    price=None,
    ma20=None,
    ma250=None,
    eps=None,
    pe_ratio=None,
    dividend_yield=None,
    peg_ratio=None,
):
    """
    綜合診斷：調用客觀診斷函式並整合原有邏輯
    """
    # 預設值，防止 NameError
    obj_summary = "⚪ 正常"
    obj_advice = "『數據分析中...』"

    # 調用核心診斷
    try:
        tags, obj_advice = generate_objective_diagnosis(
            price,
            ma20,
            ma250,
            vol_ratio,
            price_change_pct,
            rs_percentile,
            sharpe,
            eps,
            pe_ratio,
            dividend_yield,
            peg_ratio,
        )
    except Exception as e:
        logging.warning(f"Objective diagnosis failed for {ticker}: {e}")

    tech_signal_text = "  "
    rs_status_text = "⚪ 正常區"

    # RS 狀態判斷
    if rs_percentile > 85:
        rs_status_text = "🔥 過熱區"
    elif rs_percentile <= 15:
        rs_status_text = "🔵 深水區"

    tags.append(rs_status_text)

    if rsi > 70:
        tags.append("🟢 超買")
    elif rsi < 30:
        tags.append("🔴 超賣")

    # 技術燈號判斷
    if bias is not None and not math.isnan(bias):
        if bias <= -7:
            tech_signal_text = "🟠 極度價值區 (低於月線 -7%，強力加碼)"
        elif -7 < bias <= -4:
            tech_signal_text = "💧 跌深反彈區 (低於月線 -4%~-7%，注意反彈)"
        elif bias >= 7:
            tech_signal_text = "🔴 過熱區 (高於月線 +7%，注意獲利了結)"
        else:
            tech_signal_text = (
                "🟢 趨勢區 (沿月線上漲，定期定額)"
                if bias >= 0
                else "🟡 價值區 (低於月線，二線買點)"
            )

    tags.append(tech_signal_text)

    return obj_advice, tags


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
            logging.warning("沒有找到適合進行進階分析的標的代碼")
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
                bias_str = "-"
                bias_numeric = 0.0
                ma20_val = None
                price_val = float(t_df_clean["Close"].iloc[-1])

                # 計算漲幅
                prev_close = (
                    float(t_df_clean["Close"].iloc[-2])
                    if len(t_df_clean) >= 2
                    else price_val
                )
                day_change_pct = ((price_val - prev_close) / prev_close) * 100

                if len(t_df_clean) >= 20:
                    ma20_val = t_df_clean["Close"].rolling(20).mean().iloc[-1]
                    if pd.notnull(ma20_val) and ma20_val > 0:
                        ma20_str = f"{ma20_val:.2f}"
                        bias_numeric = ((price_val - ma20_val) / ma20_val) * 100
                        bias_str = f"{bias_numeric:.2f}%"

                if len(t_df_clean) >= 60:
                    ma60_val = t_df_clean["Close"].rolling(60).mean().iloc[-1]
                    if pd.notnull(ma60_val):
                        ma60_str = f"{ma60_val:.2f}"

                if len(t_df_clean) >= 120:
                    ma120_val = t_df_clean["Close"].rolling(120).mean().iloc[-1]
                    if pd.notnull(ma120_val):
                        ma120_str = f"{ma120_val:.2f}"

                ma250_val = None
                ma250_str = "-"
                if len(t_df_clean) >= 250:
                    ma250_val = t_df_clean["Close"].rolling(250).mean().iloc[-1]
                    if pd.notnull(ma250_val):
                        ma250_str = f"{ma250_val:.2f}"

                # 由於 FETCHERS 已設定 auto_adjust=True，Close 即為調整後價格
                t_col = "Close"

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

                # --- 1.5 RSI 計算 (14日週期) ---
                rsi_val = 0.0
                if len(t_df_clean) >= 15:
                    delta = t_df_clean[t_col].diff()
                    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                    with np.errstate(divide="ignore", invalid="ignore"):
                        rs_val = gain / loss
                        rsi_series = 100 - (100 / (1 + rs_val))
                    rsi_val = (
                        float(rsi_series.iloc[-1])
                        if not pd.isna(rsi_series.iloc[-1])
                        else 0.0
                    )

                # 計算 RS 第 10 百分位值對應的股價 (Deep Water 價格)
                # RS = (Asset_Price * Rate) / Benchmark_Price
                # Asset_Price = (RS * Benchmark_Price) / Rate
                rs_p10 = float(np.percentile(rs_series.values.flatten(), 10))
                rs_p10_price = (rs_p10 * comb["b"].iloc[-1]) / comb["r"].iloc[-1]

                # --- 建議掛單價計算 (多重位階) ---
                suggested_bid_str = "-"
                daily_wave, tech_retest, sniper_pos = "-", "-", "-"
                # if pct > 80:
                #     suggested_bid_str = "-"
                #     daily_wave, tech_retest, sniper_pos = "-", "-", "-"
                # else:
                if ma20_val is not None:
                    entries = calculate_buffered_entries(
                        t_df_clean, ma20_val, ma250_val, price_val, rs_p10_price
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

                # --- 3. 獲取基本面與量能 ---
                fundamentals = get_ticker_fundamental_info(ticker)
                vol_ratio = (
                    fundamentals["volume"] / fundamentals["avg_volume"]
                    if fundamentals["avg_volume"] > 0
                    else 1.0
                )

                # --- 3. 綜合診斷 ---
                full_diag_text, tags = generate_advanced_diagnosis(
                    bias_numeric,
                    sharpe,
                    pct,
                    ticker,
                    price_change_pct=day_change_pct,
                    vol_ratio=vol_ratio,
                    rsi=rsi_val,
                    price=price_val,
                    ma20=ma20_val,
                    ma250=ma250_val,
                    eps=fundamentals.get("eps"),
                    pe_ratio=fundamentals.get("pe"),
                    dividend_yield=fundamentals.get("dividendYield"),
                    peg_ratio=fundamentals.get("pegRatio"),
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
                        # "技術燈號": tech_signal_output,  # 使用 generate_advanced_diagnosis 的輸出
                        "乖離率 (Bias)": bias_str,  # 乖離率數值仍保留
                        "技術診斷": full_diag_text,  # 使用 generate_advanced_diagnosis 的輸出
                        "建議掛單": suggested_bid_str,
                        "日常波段": daily_wave,
                        "技術回測": tech_retest,
                        "狙擊位": sniper_pos,
                        "MA20": ma20_str,
                        "MA60": ma60_str,
                        "MA120": ma120_str,
                        "MA250": ma250_str,
                        "當前 RS": round(curr_rs, 4),
                        "RS 百分位": f"{pct:.1f}%",
                        "RSI": rsi_val,
                        # "RSI狀態": rsi_status,  # 新增 RSI 狀態欄位
                        # "狀態": rs_status_output,  # 使用 generate_advanced_diagnosis 的輸出
                        "Alpha 勝率": f"{bat_avg:.1f}%" if len(m_ret) >= 2 else "-",
                        "月度 Alpha": f"{avg_alpha:+.2f}%" if len(m_ret) >= 2 else "-",
                        "夏普值": f"{sharpe:.2f}" if len(m_ret) >= 2 else "-",
                        "EPS": fundamentals["eps"],
                        "PE": fundamentals["pe"],
                        "量比": f"{vol_ratio:.2f}",
                        "_vol_ratio_raw": vol_ratio,
                        "_score": pct,
                        "tags": tags,
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
    report = ["--- AI 分析專用數據摘要 ---"]
    for _, row in df.iterrows():
        # 使用列表方式呈現，確保數據完整不截斷
        pl_pct = f"{row['報酬率']:.2f}%" if pd.notnull(row["報酬率"]) else "0%"
        change = f"{row['漲跌']:+.2f}" if pd.notnull(row["漲跌"]) else "0"
        line = (
            f"- {row['代碼']}: 股價 {row['股價']} ({change}), "
            f"平均成本 {row['平均成本']}, 單位數 {row['單位數']}, "
            f"報酬率 {pl_pct}, 建議掛單 {row['建議掛單']}"
        )
        report.append(line)
    report.append("-" * 30)
    return "\n".join(report)
