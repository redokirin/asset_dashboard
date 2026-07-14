# -*- coding: utf-8 -*-
import gspread
import tomllib
import logging
from pathlib import Path
from google.oauth2.service_account import Credentials

# --- 配置與路徑 ---
# 修正：指向根目錄 (core 的上一層)
ROOT_DIR = Path(__file__).parent.parent
CREDENTIALS_PATH = ROOT_DIR / "credentials.json"
TOML_PATH = ROOT_DIR / "assets_config.toml"


def get_secret(key, default=None):
    """安全地讀取 Secrets，避免本地端報錯"""
    try:
        import streamlit as st
        return st.secrets.get(key, default)
    except Exception:
        return default


SPREADSHEET_ID = get_secret(
    "spreadsheet_id", "1xiuVw0fuuIdqVX0a-gGf0MkEZWmwWGnsRndCoNEc-4A"
)


def _parse_numeric(value) -> float:
    if value == "":
        return 0.0
    try:
        return float(str(value).replace(",", ""))
    except Exception:
        return 0.0


def _parse_bool(value) -> bool:
    return str(value).upper() in ["TRUE", "1", "YES", "T"]


def _clean_asset_rows(rows, key_candidates, numeric_cols, bool_cols):
    cleaned_assets = {}
    numeric_set = {col.lower() for col in numeric_cols}
    bool_set = {col.lower() for col in bool_cols}

    for raw_row in rows:
        row = dict(raw_row)
        key = ""
        for candidate in key_candidates:
            key = str(row.pop(candidate, "")).strip()
            if key:
                break
        if not key:
            continue

        cleaned_row = {"id": key}
        for column_name, value in row.items():
            low_key = column_name.lower()
            if low_key in numeric_set:
                cleaned_row[low_key] = _parse_numeric(value)
            elif low_key in bool_set:
                cleaned_row[low_key] = _parse_bool(value)
            elif value != "":
                cleaned_row[low_key] = value

        cleaned_assets[key] = cleaned_row

    return cleaned_assets


def _get_spreadsheet():
    """建立 gspread 連線並開啟主要試算表，支援本地檔案與 Streamlit Secrets，失敗回傳 None。"""
    creds = None

    # 1. 優先嘗試從 Streamlit Secrets 讀取 (適合 Cloud 部署)
    gcp_info = get_secret("gcp_service_account")
    if gcp_info:
        try:
            creds_info = gcp_info
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
        return gc.open_by_key(SPREADSHEET_ID)
    except Exception as e:
        logging.error(f"開啟 Google Sheets 失敗: {e}")
        return None


def get_config_from_gsheets():
    """從 Google Sheets 讀取資產配置，支援本地檔案與 Streamlit Secrets"""
    sh = _get_spreadsheet()
    if sh is None:
        return None

    try:
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
            config["funds"] = _clean_asset_rows(
                funds_data,
                key_candidates=["Key", "key"],
                numeric_cols=["nav", "units", "cost", "shares", "value"],
                bool_cols=["enabled", "get_value"],
            )
        except Exception as e:
            logging.error(f"讀取 funds 分頁失敗: {e}")

        # 3. 讀取 etfs (以 Ticker 為索引)
        try:
            ws_etfs = sh.worksheet("etfs")
            etfs_data = ws_etfs.get_all_records()
            config["etfs"] = _clean_asset_rows(
                etfs_data,
                key_candidates=["Ticker", "ticker"],
                numeric_cols=["shares", "cost", "discount", "units", "value"],
                bool_cols=["enabled", "get_value"],
            )
        except Exception as e:
            logging.error(f"讀取 etfs 分頁失敗: {e}")

        # 4. 讀取 stocks (以 Ticker 為索引)
        try:
            ws_stocks = sh.worksheet("stocks")
            stocks_data = ws_stocks.get_all_records()
            config["stocks"] = _clean_asset_rows(
                stocks_data,
                key_candidates=["Ticker", "ticker"],
                numeric_cols=["shares", "cost", "discount", "units", "value"],
                bool_cols=["enabled", "get_value"],
            )
        except Exception as e:
            logging.error(f"讀取 stocks 分頁失敗: {e}")

        try:
            ws_banks = sh.worksheet("Bank")
            banks_data = ws_banks.get_all_records()
            config["banks"] = _clean_asset_rows(
                banks_data,
                key_candidates=["Key", "key"],
                numeric_cols=["balance", "keep"],
                bool_cols=["enabled"],
            )
        except Exception as e:
            logging.error(f"讀取 Bank 分頁失敗: {e}")

        return config
    except Exception as e:
        logging.error(f"Google Sheets 讀取失敗: {e}")
        return None


def _parse_transaction_row(row: dict, currency: str, current_price: float | None = None) -> dict | None:
    """
    row 為 get_all_records() 單列 dict；ticker 空白（如累計/空白列）時回傳 None。
    pnl：優先用 current_price（App 即時股價）現算 shares * current_price - total，
    避免吃到 Google Sheets 的 P&L 公式格（該格靠 GOOGLEFINANCE 之類的機制，只有人打開試算表才會重新計算，
    透過 API 讀到的常是舊快照）。current_price 缺值時（如標的已從投組移除）才退回 sheet 原始 P&L。
    """
    ticker = str(row.get("ticker", "")).strip()
    if not ticker:
        return None
    shares = _parse_numeric(row.get("shares", ""))
    total = _parse_numeric(row.get("total", ""))
    pnl = (
        shares * current_price - total
        if current_price is not None
        else _parse_numeric(row.get("P&L", ""))
    )
    return {
        "ticker": ticker,
        "settlement": str(row.get("Settlement", "")).strip(),
        "type": str(row.get("type", "")).strip(),
        "date": str(row.get("date", "")).strip(),
        "shares": shares,
        "price": _parse_numeric(row.get("price", "")),
        "cost": _parse_numeric(row.get("cost", "")),
        "fee": _parse_numeric(row.get("fee", "")),
        "total": total,
        "pnl": pnl,
        "currency": currency,
    }


def get_etf_transactions(price_map: dict[str, float] | None = None) -> dict[str, list[dict]]:
    """
    讀取 JPY / TWD 分頁的 ETF 交易紀錄，依 ticker 分組回傳（沿用表單原本新到舊的排序）。
    找不到 ticker 的列（空白列、累計 summary 列）自動略過。
    price_map：{ticker: 現價}，用來現算 pnl；不傳則退回 sheet 原始 P&L 欄位。
    """
    sh = _get_spreadsheet()
    if sh is None:
        return {}

    price_map = price_map or {}
    result: dict[str, list[dict]] = {}
    for tab, currency in [("JPY", "JPY"), ("TWD", "TWD")]:
        try:
            ws = sh.worksheet(tab)
            for raw_row in ws.get_all_records():
                ticker = str(raw_row.get("ticker", "")).strip()
                record = _parse_transaction_row(raw_row, currency, price_map.get(ticker))
                if record:
                    result.setdefault(record["ticker"], []).append(record)
        except Exception as e:
            logging.error(f"讀取 {tab} 交易紀錄分頁失敗: {e}")

    return result


def get_config():
    """
    讀取資產配置。
    邏輯：優先載入本地或 Secrets 的基礎設定（如 app_password），
    再由 Google Sheets 更新資產與雷達清單。
    """
    config = {}

    # 1. 嘗試讀取本地 assets_config.toml
    if TOML_PATH.exists():
        try:
            with open(TOML_PATH, "rb") as f:
                toml_data = tomllib.load(f)
                config = dict(toml_data.get("my_assets", {}))
        except Exception as e:
            logging.error(f"本地配置讀取失敗: {e}")

    # 2. 如果本地沒讀到關鍵設定，嘗試從 Streamlit Secrets 讀取
    if not config.get("app_password"):
        try:
            secrets_data = get_secret("my_assets")
            if secrets_data:
                if hasattr(secrets_data, "to_dict"):
                    config.update(secrets_data.to_dict())
                else:
                    config.update(dict(secrets_data))
        except Exception as e:
            logging.error(f"Secrets 讀取失敗: {e}")

    # 3. 嘗試從 Google Sheets 讀取資產數據並合併
    gs_config = get_config_from_gsheets()
    if gs_config:
        # 用 GS 的內容更新資產清單與雷達清單，保留基礎設定
        config.update(gs_config)

    if not config:
        logging.error(
            "🚨 配置缺失：未偵測到 assets_config.toml 或 st.secrets['my_assets']"
        )

    return config


def _ensure_id(config_dict):
    """增加防呆機制：如果項目中沒有定義 id，則以 Key 為預設 id"""
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
        "etfs": _ensure_id(config.get("etfs", {})),
        "stocks": _ensure_id(config.get("stocks", {})),
        "funds": _ensure_id(config.get("funds", {})),
        "banks": _ensure_id(config.get("banks", {})),
    }


def get_radar_tickers():
    """獲取最新的雷達標的"""
    return get_config().get("radar_tickers", {})
