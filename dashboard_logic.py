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
# 安全地讀取 Secrets，避免本地端報錯
def get_secret(key, default=None):
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default


SPREADSHEET_ID = get_secret(
    "spreadsheet_id", "1xiuVw0fuuIdqVX0a-gGf0MkEZWmwWGnsRndCoNEc-4A"
)
CREDENTIALS_PATH = Path(__file__).parent / "credentials.json"


@st.cache_data(ttl=600)  # 每 10 分鐘快取一次
def get_config_from_gsheets():
    """從 Google Sheets 讀取資產配置，支援本地檔案與 Streamlit Secrets"""
    creds = None

    # 1. 優先嘗試從 Streamlit Secrets 讀取 (適合 Cloud 部署)
    gcp_info = get_secret("gcp_service_account")
    if gcp_info:
        try:
            creds_info = gcp_info
            # 確保是標準 dict
            if hasattr(creds_info, "to_dict"):
                creds_info = creds_info.to_dict()
            else:
                creds_info = dict(creds_info)

            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ]
            creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
            logging.info("使用 Streamlit Secrets 載入 Google 憑證")
        except Exception as e:
            logging.error(f"從 Secrets 載入憑證失敗: {e}")

    # ... (其餘讀取邏輯)

    # 2. 如果 Secrets 沒有，嘗試讀取本地檔案 (適合本地開發)
    if not creds and CREDENTIALS_PATH.exists():
        try:
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ]
            creds = Credentials.from_service_account_file(
                str(CREDENTIALS_PATH), scopes=scopes
            )
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
            config["radar_tickers"] = {
                row["Ticker"]: row["Name"] for row in radar_data if row["Ticker"]
            }
        except Exception as e:
            logging.error(f"讀取 radar_tickers 分頁失敗: {e}")

        # 2. 讀取 funds (以 Key 為索引)
        try:
            ws_funds = sh.worksheet("funds")
            funds_data = ws_funds.get_all_records()
            funds_dict = {}
            numeric_cols = ["nav", "units", "cost", "shares"]
            bool_cols = ["enabled", "get_value"]
            for row in funds_data:
                key = str(row.pop("Key", "") or row.pop("key", "")).strip()
                if key:
                    cleaned_row = {}
                    cleaned_row["id"] = key
                    for k, v in row.items():
                        low_k = k.lower()
                        if low_k in numeric_cols:
                            try:
                                cleaned_row[low_k] = (
                                    float(str(v).replace(",", "")) if v != "" else 0.0
                                )
                            except:
                                cleaned_row[low_k] = 0.0
                        elif low_k in bool_cols:
                            # 強制轉為布林值 (處理 "TRUE", "FALSE", 1, 0, True, False)
                            val_str = str(v).upper()
                            cleaned_row[low_k] = val_str in ["TRUE", "1", "YES", "T"]
                        elif v != "":
                            cleaned_row[low_k] = v
                    funds_dict[key] = cleaned_row
            config["funds"] = funds_dict
        except Exception as e:
            logging.error(f"讀取 funds 分頁失敗: {e}")

        # 3. 讀取 etfs (以 Ticker 為索引)
        try:
            ws_etfs = sh.worksheet("etfs")
            etfs_data = ws_etfs.get_all_records()
            etfs_dict = {}
            numeric_cols = ["shares", "cost", "discount", "units"]
            bool_cols = ["enabled", "get_value"]
            for row in etfs_data:
                ticker_key = str(row.pop("Ticker", "") or row.pop("ticker", "")).strip()
                if ticker_key:
                    cleaned_row = {}
                    cleaned_row["id"] = ticker_key
                    for k, v in row.items():
                        low_k = k.lower()
                        if low_k in numeric_cols:
                            try:
                                cleaned_row[low_k] = (
                                    float(str(v).replace(",", "")) if v != "" else 0.0
                                )
                            except:
                                cleaned_row[low_k] = 0.0
                        elif low_k in bool_cols:
                            val_str = str(v).upper()
                            cleaned_row[low_k] = val_str in ["TRUE", "1", "YES", "T"]
                        elif v != "":
                            cleaned_row[low_k] = v
                    etfs_dict[ticker_key] = cleaned_row
            config["etfs"] = etfs_dict
        except Exception as e:
            logging.error(f"讀取 etfs 分頁失敗: {e}")

        return config
    except Exception as e:
        logging.error(f"Google Sheets 讀取失敗: {e}")
        return None


@st.cache_data(ttl=600)
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


def get_assets():
    """獲取最新的資產配置"""
    config = get_config()
    return {
        "funds": _ensure_id(config.get("funds", {})),
        "etfs": _ensure_id(config.get("etfs", {})),
    }


def get_radar_tickers():
    """獲取最新的雷達標的"""
    return get_config().get("radar_tickers", {})


# 使用 lru_cache 進行簡單的記憶體快取，配合 requests_cache 達成雙重效能優化
from functools import lru_cache

# 設定 10 分鐘 (600 秒) 的 Requests 快取，減輕 API 負擔並加速執行
requests_cache.install_cache("asset_tracking_cache", expire_after=600)

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
            "name": info.get("shortName") or info.get("longName") or ticker_symbol,
            "eps": info.get("trailingEps", 0) or 0,
            "pe": info.get("trailingPE", 0) or 0,
            "dividendYield": info.get("dividendYield", 0) or 0,
            "pegRatio": info.get("trailingPegRatio", 0) or info.get("pegRatio", 0) or 0,
            "volume": info.get("volume", 0) or 0,
            "avg_volume": info.get("averageVolume", 1) or 1,  # 避免除以 0
        }
    except Exception:
        return {
            "name": ticker_symbol,
            "eps": 0,
            "pe": 0,
            "dividendYield": 0,
            "pegRatio": 0,
            "volume": 0,
            "avg_volume": 1,
        }


# 定義資料抓取器註冊表，允許從外部注入 (例如 Streamlit 快取版本)
FETCHERS = {
    "historical": lambda tickers, **kwargs: yf.download(
        list(tickers),
        period=kwargs.get("period", "2y"),
        progress=kwargs.get("progress", False),
        group_by=kwargs.get("group_by", "ticker"),
        auto_adjust=True,  # 自動處理股票拆分與除息，確保技術指標不失真
    ),
    "common": lambda tickers, **kwargs: yf.download(
        list(tickers),
        period=kwargs.get("period", "2y"),
        progress=kwargs.get("progress", False),
        auto_adjust=True,  # 確保 Benchmark 與匯率同樣經過調整
    ),
}


def fetch_historical_data(tickers, period="2y", group_by="ticker"):
    try:
        df_all = FETCHERS["historical"](tickers, period=period, group_by=group_by)
    except Exception as e:
        logging.error(f"資料抓取器執行失敗: {e}")
        return pd.DataFrame()

    if df_all is None or df_all.empty:
        return pd.DataFrame()

    # --- 歷史數據修正邏輯 (Yahoo Finance 數據錯誤 Patch) ---
    # 註：yfinance 的 auto_adjust=True 有時會失效 (特別是長線數據)，需手動校正
    fix_configs = {
        "1306.T": {
            "ratio": 10.0,
            "threshold_factor": 5.0,
            "bug_price": 10000,
            "desc": "日本 1306.T (1:10 分割)"
        },
        "0052.TW": {
            "ratio": 7.0,
            "threshold_factor": 3.0,
            "bug_price": 200,
            "desc": "富邦科技 0052.TW (1:7 分割)"
        }
    }

    target_tickers_list = [tickers] if isinstance(tickers, str) else list(tickers)
    for t_id, cfg in fix_configs.items():
        if t_id in target_tickers_list:
            try:
                # 提取特定標的的數據進行檢查
                if isinstance(df_all.columns, pd.MultiIndex):
                    t_df = df_all[t_id].copy()
                else:
                    t_df = df_all.copy()

                if not t_df.empty and "Close" in t_df.columns:
                    clean_close = t_df["Close"].dropna()
                    if not clean_close.empty:
                        current_p = float(clean_close.iloc[-1])
                        ratio = cfg["ratio"]
                        
                        # 修正判斷：若現價過高 (全局未調整) 或 歷史數據有異常突波 (局部未對齊)
                        threshold = current_p * cfg["threshold_factor"]
                        is_global_bug = current_p > cfg["bug_price"]
                        high_price_dates = (
                            t_df.index[t_df["Close"] > threshold]
                            if not is_global_bug
                            else t_df.index
                        )

                        if is_global_bug or not high_price_dates.empty:
                            msg = "全局未調整" if is_global_bug else f"歷史分割未對齊 ({len(high_price_dates)} 筆)"
                            logging.info(f"⚡ 偵測到 {cfg['desc']} {msg}，執行 1:{int(ratio)} 修正...")

                            cols_to_fix = ["Open", "High", "Low", "Close"]
                            if isinstance(df_all.columns, pd.MultiIndex):
                                for col in cols_to_fix:
                                    if (t_id, col) in df_all.columns:
                                        if is_global_bug:
                                            df_all.loc[:, (t_id, col)] /= ratio
                                        else:
                                            df_all.loc[high_price_dates, (t_id, col)] /= ratio
                                if (t_id, "Volume") in df_all.columns:
                                    if is_global_bug:
                                        df_all.loc[:, (t_id, "Volume")] *= ratio
                                    else:
                                        df_all.loc[high_price_dates, (t_id, "Volume")] *= ratio
                            else:
                                available_cols = [c for c in cols_to_fix if c in df_all.columns]
                                if is_global_bug:
                                    df_all.loc[:, available_cols] /= ratio
                                    if "Volume" in df_all.columns:
                                        df_all["Volume"] *= ratio
                                else:
                                    df_all.loc[high_price_dates, available_cols] /= ratio
                                    if "Volume" in df_all.columns:
                                        df_all.loc[high_price_dates, "Volume"] *= ratio
            except Exception as e:
                logging.debug(f"{t_id} 數據修正失敗: {e}")

    # --- 全域降維防禦 (避開 MultiIndex 內部方法) ---
    is_mi = False
    try:
        is_mi = isinstance(df_all.columns, pd.MultiIndex)
    except:
        pass

    if is_mi:
        try:
            # 暴力提取所有第一層標的名稱，不使用 get_level_values
            all_cols = df_all.columns.tolist()
            tickers_in_df = list(
                set([c[0] if isinstance(c, tuple) else c for c in all_cols])
            )

            # 如果只有一個標的，直接降維成單層 DataFrame
            if len(tickers_in_df) == 1:
                t_name = tickers_in_df[0]
                df_all = df_all[t_name].copy()
        except Exception as e:
            logging.debug(f"降維處理跳過: {e}")

    return df_all


def fetch_common_data(tickers, period="2y"):
    return FETCHERS["common"](tickers, period=period)


def get_market_radar_data():
    """抓取市場雷達數據"""
    data = []
    radar_tickers = get_radar_tickers()
    for ticker, name in radar_tickers.items():
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
    assets = get_assets()

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

    # 分開處理基金與 ETF 的價格抓取，避免相互干擾
    batch_prices = {}
    batch_changes = {}

    def fetch_batch_prices(cat_key):
        tickers = []
        for asset in assets[cat_key].values():
            # 強制檢查 enabled 和 get_value (相容布林值與字串)
            is_enabled = asset.get("enabled") is True or str(
                asset.get("enabled")
            ).upper() in ["TRUE", "1", "YES", "T"]
            is_get_val = asset.get("get_value") is True or str(
                asset.get("get_value")
            ).upper() in ["TRUE", "1", "YES", "T"]

            if is_enabled and is_get_val:
                tickers.append(asset["id"])

        if not tickers:
            return

        try:
            logging.info(f"正在抓取 {cat_key} 價格: {tickers}")
            hist_data = fetch_historical_data(tuple(tickers), period="1mo")

            for t in tickers:
                try:
                    df = None
                    if isinstance(hist_data.columns, pd.MultiIndex):
                        if t in hist_data.columns.get_level_values(0):
                            df = hist_data[t].copy()
                        else:
                            # 如果只有一個 ticker 但還是 MultiIndex
                            if len(tickers) == 1:
                                df = hist_data.copy()
                                df.columns = df.columns.get_level_values(1)
                    else:
                        df = hist_data.copy()

                    if df is not None and not df.empty and "Close" in df.columns:
                        # 避開 dropna，改用 notnull 過濾
                        close_s = df["Close"]
                        df_clean = close_s[close_s.notnull()].copy()

                        if not df_clean.empty:
                            last_val = df_clean.iloc[-1]
                            batch_prices[t] = (
                                float(last_val.iloc[0])
                                if isinstance(last_val, pd.Series)
                                else float(last_val)
                            )

                            if len(df_clean) >= 2:
                                prev_val = df_clean.iloc[-2]
                                p_val = (
                                    float(prev_val.iloc[0])
                                    if isinstance(prev_val, pd.Series)
                                    else float(prev_val)
                                )
                                batch_changes[t] = float(batch_prices[t] - p_val)
                except Exception as e:
                    logging.warning(f"解析 {t} 價格失敗: {e}")
        except Exception as e:
            logging.error(f"批次抓取 {cat_key} 失敗: {e}")

    # 執行抓取
    fetch_batch_prices("funds")
    fetch_batch_prices("etfs")

    for cat_key, cat_name in [("funds", "基金"), ("etfs", "ETF")]:
        for asset in assets[cat_key].values():
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
# │ ma20             │ 月線 (20日均線)       │ 定義「短線動能」與計算「乖離率」的核心指標。          │
# │ ma250            │ 年線 (250日均線)       │ 定義「長線格局」多空的分水嶺。                        │
# │ vol_ratio        │ 量比 (成交量比率)      │ 偵測異常動能（如爆量、窒息量）與驗證價格真偽。        │
# │ price_change_pct │ 今日漲跌幅            │ 結合量比進行「量價驗證」判斷。                        │
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
        # 取得共通數據 (Benchmark, 匯率)
        common_raw = fetch_common_data((benchmark, "JPYTWD=X", "USDTWD=X"), period="2y")

        # 針對 MultiIndex 欄位提取特定數據列，並確保返回的是乾淨的 Series
        def get_clean_col(df, ticker_name, col_name):
            try:
                if isinstance(df.columns, pd.MultiIndex):
                    if ticker_name in df.columns.get_level_values(0):
                        s = df.xs(ticker_name, axis=1, level=0)[col_name]
                    else:
                        s = df[col_name]
                else:
                    s = df[col_name]

                # 強制轉換索引為單層 DatetimeIndex
                if isinstance(s.index, pd.MultiIndex):
                    s.index = s.index.get_level_values(0)
                s.index = pd.to_datetime(s.index)
                if hasattr(s.index, "tz") and s.index.tz is not None:
                    s.index = s.index.tz_localize(None)

                # 確保返回的是 Series 而非 DataFrame
                if isinstance(s, pd.DataFrame):
                    s = s.iloc[:, 0]
                return s
            except:
                return pd.Series()

        # 處理 Benchmark 數據
        b_series_final = get_clean_col(common_raw, benchmark, "Close")
        if b_series_final.empty:
            return pd.DataFrame()

        t_data_all_raw = fetch_historical_data(
            tuple(active_tickers), period="2y", group_by="ticker"
        )

        for ticker in active_tickers:
            try:
                # 1. 提取特定 Ticker 的數據
                if isinstance(t_data_all_raw.columns, pd.MultiIndex):
                    if ticker in t_data_all_raw.columns.get_level_values(0):
                        t_df = t_data_all_raw.xs(ticker, axis=1, level=0).copy()
                    else:
                        t_df = t_data_all_raw.copy()
                else:
                    t_df = t_data_all_raw.copy()

                if t_df is None or t_df.empty:
                    continue

                # 2. 強制簡化結構：移除任何剩餘的 MultiIndex
                if isinstance(t_df.columns, pd.MultiIndex):
                    t_df.columns = t_df.columns.get_level_values(-1)
                if isinstance(t_df.index, pd.MultiIndex):
                    t_df.index = t_df.index.get_level_values(0)

                # 確保日期格式一致
                t_df.index = pd.to_datetime(t_df.index)
                if hasattr(t_df.index, "tz") and t_df.index.tz is not None:
                    t_df.index = t_df.index.tz_localize(None)

                if "Close" not in t_df.columns:
                    continue

                # 現在執行過濾
                t_df_clean = t_df[t_df["Close"].notnull()].copy()
                if len(t_df_clean) == 0:
                    continue

                # 計算技術燈號與均線
                ma20_str, ma60_str, ma120_str = "-", "數據不足", "數據不足"
                bias_str = "-"
                bias_numeric = 0.0
                ma20_val = None

                # 強制轉換為 float 避免 Series 傳入 metric
                last_close_val = t_df_clean["Close"].iloc[-1]
                price_val = (
                    float(last_close_val.iloc[0])
                    if isinstance(last_close_val, pd.Series)
                    else float(last_close_val)
                )

                # 計算漲幅
                if len(t_df_clean) >= 2:
                    prev_close_val = t_df_clean["Close"].iloc[-2]
                    prev_close = (
                        float(prev_close_val.iloc[0])
                        if isinstance(prev_close_val, pd.Series)
                        else float(prev_close_val)
                    )
                else:
                    prev_close = price_val

                day_change_pct = ((price_val - prev_close) / prev_close) * 100

                if len(t_df_clean) >= 20:
                    ma20_series = t_df_clean["Close"].rolling(20).mean()
                    ma20_last = ma20_series.iloc[-1]
                    ma20_val = (
                        float(ma20_last.iloc[0])
                        if isinstance(ma20_last, pd.Series)
                        else float(ma20_last)
                    )

                    if pd.notnull(ma20_val) and ma20_val > 0:
                        ma20_str = f"{ma20_val:.2f}"
                        bias_numeric = ((price_val - ma20_val) / ma20_val) * 100
                        bias_str = f"{bias_numeric:.2f}%"

                if len(t_df_clean) >= 60:
                    ma60_last = t_df_clean["Close"].rolling(60).mean().iloc[-1]
                    ma60_val = (
                        float(ma60_last.iloc[0])
                        if isinstance(ma60_last, pd.Series)
                        else float(ma60_last)
                    )
                    if pd.notnull(ma60_val):
                        ma60_str = f"{ma60_val:.2f}"

                if len(t_df_clean) >= 120:
                    ma120_last = t_df_clean["Close"].rolling(120).mean().iloc[-1]
                    ma120_val = (
                        float(ma120_last.iloc[0])
                        if isinstance(ma120_last, pd.Series)
                        else float(ma120_last)
                    )
                    if pd.notnull(ma120_val):
                        ma120_str = f"{ma120_val:.2f}"

                ma250_val = None
                ma250_str = "-"
                if len(t_df_clean) >= 250:
                    ma250_last = t_df_clean["Close"].rolling(250).mean().iloc[-1]
                    ma250_v = (
                        float(ma250_last.iloc[0])
                        if isinstance(ma250_last, pd.Series)
                        else float(ma250_last)
                    )
                    if pd.notnull(ma250_v):
                        ma250_val = ma250_v
                        ma250_str = f"{ma250_val:.2f}"

                # 由於 FETCHERS 已設定 auto_adjust=True，Close 即為調整後價格
                t_col = "Close"

                # 強制轉換為單一 Series 並移除索引中的 MultiIndex
                p_series = t_df_clean[t_col].copy()
                if isinstance(p_series, pd.DataFrame):
                    p_series = p_series.iloc[:, 0]

                # 確保索引是乾淨的 DatetimeIndex
                if isinstance(p_series.index, pd.MultiIndex):
                    p_series.index = p_series.index.get_level_values(0)
                p_series.index = pd.to_datetime(p_series.index)
                if hasattr(p_series.index, "tz") and p_series.index.tz is not None:
                    p_series.index = p_series.index.tz_localize(None)

                # 自動判斷幣別
                ccy = (
                    "JPY"
                    if ticker.endswith(".T")
                    else "USD"
                    if ".US" in ticker or ticker.isupper()
                    else "TWD"
                )

                # 處理匯率 Series
                if ccy == "JPY":
                    r_series = get_clean_col(common_raw, "JPYTWD=X", "Close")
                elif ccy == "USD":
                    r_series = get_clean_col(common_raw, "USDTWD=X", "Close")
                else:
                    r_series = 1.0

                # 建立合併後的 DataFrame
                # 在合併前確保所有參與者的索引都是乾淨的對齊
                comb_dict = {"p": p_series, "b": b_series_final}
                if isinstance(r_series, (pd.Series, pd.DataFrame)):
                    comb_dict["r"] = r_series
                else:
                    # 如果是常數，則在合併後補齊
                    pass

                comb = pd.DataFrame(comb_dict).ffill()
                if "r" not in comb.columns:
                    comb["r"] = (
                        1.0
                        if not isinstance(r_series, (pd.Series, pd.DataFrame))
                        else r_series
                    )

                # 避開 dropna，改用 notnull 過濾
                comb = comb[comb["p"].notnull() & comb["b"].notnull()]

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
                # 優先使用 yfinance 抓取到的官方名稱
                asset_name = fundamentals.get("name", ticker)

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
